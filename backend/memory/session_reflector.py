"""会话反思器 — 会话结束后统一反思，1 次 LLM 调用完成所有记忆工作

替代原有的 extractor + reflector + reflection_strategies + reflection_dispatcher，
将多路径、多次 LLM 调用简化为单一入口：
- reflect_on_session(): 会话结束后自动调用（1 次 LLM）

写入路径只剩两条：
1. 会话后自动反思 → 本模块
2. Agent 主动调用 memory_write → consolidator
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


async def reflect_on_session(
    session_messages: list[dict],
    tool_calls: list[dict],
    session_id: str,
) -> dict:
    """会话结束后统一反思 — 1 次 LLM 调用完成所有记忆工作

    工作流程：
    1. 从 session_messages 提取关键词，搜索 top-10 现有相关记忆
    2. 构建统一 Prompt（对话摘要 + 工具调用时间线 + 现有记忆）
    3. 1 次 LLM 调用，输出 JSON 对象：{session_summary, decisions: [{action, content, ...}]}
    4. 执行 ADD/UPDATE/NOOP 决策

    Args:
        session_messages: 最近的对话消息（建议 10 条）
        tool_calls: 本次会话工具调用记录
        session_id: 会话 ID

    Returns:
        包含 session_summary 和 decisions 的字典
    """
    if not session_messages:
        return {"decisions": [], "session_summary": ""}

    try:
        # 1. 构建对话摘要
        conversation_lines = []
        for msg in session_messages[-10:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                conversation_lines.append(f"{role}: {content[:500]}")
        conversation = "\n".join(conversation_lines)

        if not conversation.strip():
            return {"decisions": [], "session_summary": ""}

        # 2. 提取关键词并搜索现有记忆
        existing_memories = []
        try:
            # 用最后一条用户消息作为搜索查询
            query = ""
            for msg in reversed(session_messages):
                if msg.get("role") == "user" and msg.get("content"):
                    query = msg["content"][:200]
                    break
            if query:
                from memory.search import search_memories
                existing_memories = search_memories(query, top_k=10, use_decay=False)
        except Exception as e:
            logger.debug("搜索现有记忆失败（非致命）: %s", e)

        # 3. 构建工具调用时间线
        tool_timeline = ""
        if tool_calls:
            lines = []
            for i, tc in enumerate(tool_calls[:10], 1):
                tool_name = tc.get("tool", "unknown")
                output = tc.get("output", "")
                is_error = "[ERROR]" in output
                status = "失败" if is_error else "成功"
                lines.append(f"  {i}. {tool_name} → {status}")
                if is_error:
                    lines.append(f"     错误: {output[:150]}")
            tool_timeline = "\n".join(lines)

        # 4. 构建现有记忆上下文
        existing_context = ""
        if existing_memories:
            mem_lines = []
            for m in existing_memories:
                mid = m.get("id", "?")
                cat = m.get("category", "general")
                content = m.get("content", "")[:200]
                mem_lines.append(f"  - [id={mid}][{cat}] {content}")
            existing_context = "\n".join(mem_lines)

        # 5. 构建统一 Prompt
        prompt = f"""分析以下对话，提取值得长期记住的关键信息，并与现有记忆整合。

## 对话内容
{conversation}

## 工具调用记录
{tool_timeline if tool_timeline else "(无工具调用)"}

## 现有相关记忆
{existing_context if existing_context else "(无相关记忆)"}

## 要求
1. 只提取确定性的事实和偏好，不要猜测
2. 优先提取：用户偏好、重要事实、工具使用经验（尤其是失败后的教训）
3. 忽略临时性、一次性的信息（如"今天天气怎么样"）
4. 如果新信息与现有记忆重复或矛盾，使用 UPDATE（提供 target_id）
5. 如果是全新信息，使用 ADD
6. 工具执行失败的经验应记录为 procedural 分类

返回 JSON 对象，格式如下：
{{
  "session_summary": "用一句自然语言概括本次对话的核心内容，侧重用户的意图和结果。例如：'用户查询了北京到上海的火车票，获得了2月25日的车次列表'、'用户希望购买机票但因价格过高未下单'、'用户设置了周六下午3点的开会提醒'。如果对话是闲聊、打招呼、无实质内容，则设为空字符串 ''",
  "decisions": [
    {{"action": "ADD|UPDATE|NOOP", "content": "具体内容", "category": "preferences|facts|tasks|reflections|procedural|general", "salience": 0.5, "target_id": "仅 UPDATE 时提供", "reason": "简要说明"}}
  ]
}}

注意：
- decisions 数组可以为空（无值得长期记忆的信息）
- session_summary 只在对话有实际价值时才填写；闲聊、寒暄、简单问候等无实质内容的对话设为空字符串
- 如果 decisions 为空且 session_summary 为空，表示本次对话无需任何记录

返回 JSON 对象："""

        # 6. 调用 LLM（唯一的一次调用）
        from engine.llm_factory import create_llm
        llm = create_llm(streaming=False)
        response = await llm.ainvoke(prompt)
        result = response.content.strip()

        # 7. 解析 JSON
        parsed = _parse_llm_response(result)
        results = parsed.get("decisions", [])
        session_summary = parsed.get("session_summary", "")
        logger.info("会话反思完成: session=%s, 决策=%d 条, 摘要=%s", session_id, len(results), session_summary[:50])
        return {"decisions": results, "session_summary": session_summary}

    except Exception as e:
        logger.error("会话反思失败: %s", e)
        return {"decisions": [], "session_summary": ""}


async def execute_reflect_results(
    results: dict | list,
    session_id: str,
) -> None:
    """执行反思决策结果

    Args:
        results: LLM 返回的决策（新格式为 dict 含 decisions + session_summary，兼容旧格式 list）
        session_id: 会话 ID
    """
    from memory.manager import memory_manager
    from memory.models import VALID_CATEGORIES

    # 兼容新旧格式
    if isinstance(results, dict):
        decisions = results.get("decisions", [])
        session_summary = results.get("session_summary", "")
    else:
        decisions = results
        session_summary = ""

    add_count = 0
    update_count = 0

    for item in decisions:
        action = item.get("action", "NOOP").upper()
        content = item.get("content", "").strip()
        category = item.get("category", "general")
        salience = item.get("salience", 0.5)
        target_id = item.get("target_id")

        if not content:
            continue

        # 分类校验
        if category not in VALID_CATEGORIES:
            category = "general"

        # 限制 salience 范围
        salience = max(0.0, min(1.0, float(salience)))

        try:
            if action == "ADD":
                # 如果是 procedural 分类，提取可能的工具信息
                context = None
                if category == "procedural":
                    context = {"learned_from": session_id}

                memory_manager.add_entry(
                    content=content,
                    category=category,
                    salience=salience,
                    source="session_reflect",
                    context=context,
                    skip_dedup=True,  # LLM 已做决策，跳过重复检测
                )
                add_count += 1

            elif action == "UPDATE" and target_id:
                memory_manager.update_entry(
                    entry_id=target_id,
                    content=content,
                    salience=salience,
                )
                update_count += 1

            # NOOP → 跳过

        except Exception as e:
            logger.warning("执行反思决策失败 (action=%s): %s", action, e)

    # 写入对话摘要到日志（始终写入，无论是否产生新记忆）
    if session_summary:
        memory_manager.append_daily_log(
            content=session_summary,
            log_type="reflection",
        )
        logger.info("会话反思执行完毕: %s, %d 条新记忆, %d 条更新 (session=%s)",
                     session_summary, add_count, update_count, session_id)
    elif add_count > 0 or update_count > 0:
        # 兜底：如果没有摘要但有记忆变更，仍记录一条
        memory_manager.append_daily_log(
            content=f"会话产生 {add_count} 条新记忆, {update_count} 条更新",
            log_type="reflection",
        )
        logger.info("会话反思执行完毕: %d 条新记忆, %d 条更新 (session=%s)",
                     add_count, update_count, session_id)


def _extract_json(text: str) -> str:
    """从可能包含 markdown 代码块的文本中提取 JSON

    支持 ```json、``` 等多种代码块格式，以及无代码块的纯文本。
    """
    match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_llm_response(result: str) -> dict:
    """解析 LLM 返回的 JSON 对象（含 session_summary + decisions）

    兼容旧格式（纯数组）和新格式（对象），处理 markdown 代码块包裹和格式异常。
    """
    result = _extract_json(result)

    try:
        parsed = json.loads(result)

        # 新格式：{"session_summary": "...", "decisions": [...]}
        if isinstance(parsed, dict):
            session_summary = parsed.get("session_summary", "")
            decisions_raw = parsed.get("decisions", [])
        # 旧格式兼容：纯数组
        elif isinstance(parsed, list):
            session_summary = ""
            decisions_raw = parsed
        else:
            return {"session_summary": "", "decisions": []}

        # 验证和清理 decisions
        valid = []
        for item in decisions_raw:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "NOOP").upper()
            if action not in ("ADD", "UPDATE", "NOOP"):
                continue
            content = item.get("content", "")
            if not content and action != "NOOP":
                continue
            valid.append(item)

        return {"session_summary": session_summary, "decisions": valid}

    except json.JSONDecodeError:
        logger.warning("无法解析反思结果 JSON: %s", result[:200])
        return {"session_summary": "", "decisions": []}
