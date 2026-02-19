"""流适配器 — 统一的 LangGraph 事件循环。

将 LangGraph astream_events 翻译为标准化的 AgentEvent dict。
这是处理 LangGraph 原始事件的唯一位置。
Phase 1 (DirectMode) 和 Phase 2 (PlanMode) 均调用此函数。
"""
import logging
import time
from typing import AsyncGenerator, Optional

from engine import events

logger = logging.getLogger(__name__)


def _serialize_debug_messages(input_data) -> str:
    """序列化 LLM 输入消息，用于调试显示。"""
    messages = input_data.get("messages", [])
    if messages and isinstance(messages[0], list):
        messages = messages[0]
    parts = []
    for msg in messages:
        role = type(msg).__name__
        content = str(msg.content) if hasattr(msg, "content") else str(msg)
        parts.append(f"[{role}]\n{content}")
    return "\n---\n".join(parts)


def _format_debug_input(system_prompt: str, messages_str: str, instruction: str = None) -> str:
    """格式化调试输入，保持统一结构。"""
    parts = [f"[System Prompt]\n{system_prompt}"]
    if instruction:
        parts.append(f"[Instruction]\n{instruction}")
    parts.append(f"[Messages]\n{messages_str}")
    return "\n\n".join(parts)


async def stream_agent_events(
    agent,
    input_state: dict,
    config: dict,
    *,
    system_prompt: str = "",
    node_label: Optional[str] = None,
    motivation: Optional[str] = None,
    instruction: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """LangGraph astream_events → 标准化 AgentEvent dict 流。

    DirectMode 和 PlanMode 共享的唯一事件循环。

    Args:
        agent: LangGraph agent（由 create_react_agent 创建）
        input_state: {"messages": [...]}
        config: {"recursion_limit": N}
        system_prompt: 用于调试输入格式化
        node_label: 覆盖 langgraph_node（PlanMode 使用 "executor"）
        motivation: 覆盖 llm_start 动机描述
        instruction: PlanMode executor_prompt（用于调试显示）
    """
    from model_pool import resolve_model

    debug_tracking = {}

    async for event in agent.astream_events(input_state, version="v2", config=config):
        kind = event.get("event", "")
        metadata = event.get("metadata", {})

        if kind == "on_chat_model_stream":
            chunk = (event.get("data") or {}).get("chunk", None)
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield events.build_token(chunk.content)

        elif kind == "on_chat_model_start":
            run_id = event.get("run_id", "")
            node = node_label or metadata.get("langgraph_node", "")
            input_data = (event.get("data") or {}).get("input", {})
            input_messages = _serialize_debug_messages(input_data)
            full_input = _format_debug_input(system_prompt, input_messages, instruction)
            debug_tracking[run_id] = {
                "start_time": time.time(),
                "node": node,
                "input": full_input,
            }

            mot = motivation or {"agent": "调用大模型进行推理"}.get(node, "调用大模型处理请求")
            model_name = resolve_model("llm").get("model", "unknown")
            yield events.build_llm_start(run_id[:12], node, model_name, full_input[:5000], mot)

        elif kind == "on_chat_model_end":
            run_id = event.get("run_id", "")
            tracked = debug_tracking.pop(run_id, None)
            if tracked:
                yield events.build_llm_end_from_raw(event, tracked)

        elif kind == "on_tool_start":
            run_id = event.get("run_id", "")
            debug_tracking[f"tool_{run_id}"] = {"start_time": time.time()}
            yield events.build_tool_start_from_raw(event)

        elif kind == "on_tool_end":
            run_id = event.get("run_id", "")
            tracked = debug_tracking.pop(f"tool_{run_id}", None)
            duration_ms = int((time.time() - tracked["start_time"]) * 1000) if tracked else None
            yield events.build_tool_end_from_raw(event, duration_ms)
