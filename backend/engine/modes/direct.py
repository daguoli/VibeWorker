"""DirectMode — Phase 1 ReAct Agent 执行。

统一入口，处理所有请求。当检测到 plan_create 调用时，
停止执行并将控制权交还 runner 以进入 Phase 2。
"""
import logging

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from config import settings
from engine.context import RunContext
from engine.events import TOOL_END
from engine.llm_factory import get_llm
from engine.messages import convert_history
from engine.stream_adapter import stream_agent_events
from prompt_builder import build_system_prompt
from tools import get_all_tools

logger = logging.getLogger(__name__)


class DirectMode:
    """Phase 1：拥有全部工具（含 plan_create）的 ReAct Agent。"""

    async def execute(self, ctx: RunContext):
        llm = get_llm(streaming=True)
        tools = get_all_tools()
        system_prompt = build_system_prompt()

        agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)

        messages = convert_history(ctx.session_history)
        messages.append(HumanMessage(content=ctx.message))

        input_state = {"messages": messages}
        config = {"recursion_limit": settings.agent_recursion_limit}

        async for event in stream_agent_events(
            agent, input_state, config,
            system_prompt=system_prompt,
        ):
            yield event

            # 检测 plan_create 触发 → 中断以交接 Phase 2
            if event.get("type") == TOOL_END and event.get("tool") == "plan_create":
                if ctx.plan_data:
                    return  # Runner 接管进入 PlanMode
