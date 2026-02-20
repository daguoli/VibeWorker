"""记忆提取器 — 从对话和工具结果中提取记忆

支持两种提取模式：
1. 显式提取：用户明确要求记住的内容
2. 隐式提取：从对话中自动识别值得记住的信息
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


async def extract_memories_from_conversation(
    messages: list[dict],
    recent_count: int = 6,
) -> list[dict]:
    """从对话中提取记忆

    Args:
        messages: 对话消息列表
        recent_count: 分析最近 N 条消息

    Returns:
        提取的记忆列表，每项包含 category, content, salience
    """
    if not settings.memory_auto_extract:
        return []

    try:
        # 取最近消息
        recent = messages[-recent_count:] if len(messages) > recent_count else messages
        if not recent:
            return []

        # 构建对话文本
        conversation = ""
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                conversation += f"{role}: {content[:500]}\n"

        if not conversation.strip():
            return []

        from engine.llm_factory import create_llm
        llm = create_llm()

        prompt = f"""分析以下对话，提取值得长期记住的关键信息。

提取规则：
1. 只提取确定性的事实和偏好，不要猜测
2. 优先提取用户明确表达的偏好、习惯、重要事实
3. 忽略临时性、一次性的信息
4. 评估每条信息的重要性（0.0-1.0）

如果没有值得记录的信息，返回空 JSON 数组 []

如果有，返回 JSON 数组，每项格式：
{{"category": "preferences|facts|tasks|reflections|general", "content": "具体内容", "salience": 0.5-1.0}}

对话内容：
{conversation}

提取结果（JSON 数组）："""

        response = await llm.ainvoke(prompt)
        result = response.content.strip()

        # 尝试解析 JSON
        import json
        try:
            # 移除可能的 markdown 代码块标记
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            extracted = json.loads(result)
            if not isinstance(extracted, list):
                return []

            # 验证和清理
            valid = []
            for item in extracted:
                if not isinstance(item, dict):
                    continue
                category = item.get("category", "general")
                content = item.get("content", "")
                salience = item.get("salience", 0.5)

                if not content:
                    continue

                # 限制 salience 范围
                salience = max(0.0, min(1.0, float(salience)))

                valid.append({
                    "category": category,
                    "content": content,
                    "salience": salience,
                })

            return valid

        except json.JSONDecodeError:
            # 尝试旧格式解析（兼容）
            memories = []
            for line in result.split("\n"):
                line = line.strip()
                if "|" not in line:
                    continue
                parts = line.split("|", 1)
                if len(parts) != 2:
                    continue
                cat = parts[0].strip().lower()
                content = parts[1].strip()
                if content:
                    memories.append({
                        "category": cat,
                        "content": content,
                        "salience": 0.5,
                    })
            return memories

    except Exception as e:
        logger.error(f"记忆提取失败: {e}")
        return []


def detect_explicit_memory_request(user_message: str) -> Optional[dict]:
    """检测用户显式记忆请求

    识别模式：
    - "记住..." / "请记住..."
    - "以后..." / "下次..."
    - "我喜欢..." / "我偏好..."
    - "不要忘记..."

    Args:
        user_message: 用户消息

    Returns:
        如果检测到显式请求，返回 {content, category, salience}，否则 None
    """
    import re

    patterns = [
        # "记住" 模式
        (r"(?:请)?记住[：:，,]?\s*(.+)", "general", 0.9),
        # "以后/下次" 模式
        (r"(?:以后|下次|今后)[：:，,]?\s*(.+)", "preferences", 0.8),
        # "我喜欢/偏好" 模式
        (r"我(?:喜欢|偏好|习惯)[：:，,]?\s*(.+)", "preferences", 0.8),
        # "不要忘记" 模式
        (r"(?:不要|别)忘记[：:，,]?\s*(.+)", "tasks", 0.9),
        # "提醒我" 模式
        (r"(?:提醒|记得提醒)我[：:，,]?\s*(.+)", "tasks", 0.85),
    ]

    for pattern, category, salience in patterns:
        match = re.search(pattern, user_message)
        if match:
            content = match.group(1).strip()
            if content:
                return {
                    "content": content,
                    "category": category,
                    "salience": salience,
                }

    return None


async def process_message_for_memory(
    message: str,
    role: str = "user",
    session_messages: Optional[list[dict]] = None,
) -> list[dict]:
    """处理消息，提取潜在记忆

    结合显式检测和隐式提取。

    Args:
        message: 消息内容
        role: 消息角色（user/assistant）
        session_messages: 完整会话消息（用于上下文）

    Returns:
        提取的记忆列表
    """
    memories = []

    # 1. 检测显式记忆请求
    if role == "user":
        explicit = detect_explicit_memory_request(message)
        if explicit:
            memories.append(explicit)
            logger.info(f"检测到显式记忆请求: {explicit['content'][:50]}...")

    # 2. 隐式提取（如果有会话上下文）
    if session_messages and settings.memory_auto_extract:
        extracted = await extract_memories_from_conversation(session_messages)
        for item in extracted:
            # 避免与显式请求重复
            if not any(m["content"] == item["content"] for m in memories):
                memories.append(item)

    return memories
