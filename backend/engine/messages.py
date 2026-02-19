"""消息转换 — 会话历史转为 LangChain 消息格式。

关键改进：当 assistant 消息包含 tool_calls 时，生成
AIMessage(tool_calls=[...]) + 对应的 ToolMessage 序列，
确保 LLM 获得完整的工具调用上下文。
"""
import logging

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

logger = logging.getLogger(__name__)


def convert_history(session_history: list[dict]) -> list:
    """将会话历史 dict 列表转换为 LangChain 消息对象。

    处理 assistant 消息中的 tool_calls，生成正确的
    AIMessage + ToolMessage 配对以保持 LLM 上下文连续性。
    """
    messages = []
    for msg in session_history:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                # 构建带 tool_calls 元数据的 AIMessage
                lc_tool_calls = []
                for i, tc in enumerate(tool_calls):
                    call_id = tc.get("call_id", f"call_{i}_{tc.get('tool', 'unknown')}")
                    tool_input = tc.get("input", {})
                    if isinstance(tool_input, str):
                        # 尝试保持 dict 格式以兼容 LangChain
                        tool_input = {"input": tool_input}
                    lc_tool_calls.append({
                        "id": call_id,
                        "name": tc.get("tool", "unknown"),
                        "args": tool_input,
                    })
                messages.append(AIMessage(content=content, tool_calls=lc_tool_calls))
                # 对应的 ToolMessage 列表
                for i, tc in enumerate(tool_calls):
                    call_id = tc.get("call_id", f"call_{i}_{tc.get('tool', 'unknown')}")
                    messages.append(ToolMessage(
                        content=tc.get("output", ""),
                        tool_call_id=call_id,
                    ))
            else:
                messages.append(AIMessage(content=content))

    return messages
