"""Runner — 顶层 Agent 编排器，带 Middleware 管线。

提供唯一入口 `run_agent()`：
1. 运行 DirectMode（Phase 1）
2. 检测 plan_create → 审批门 → PlanMode（Phase 2）
3. 所有事件经过 Middleware 链路由
"""
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from config import settings
from engine.context import RunContext
from engine import events
from engine.messages import convert_history
from engine.modes.direct import DirectMode
from engine.modes.plan import PlanMode

logger = logging.getLogger(__name__)


async def run_agent(
    message: str,
    session_history: list[dict],
    ctx: RunContext,
    middlewares: list = None,
) -> AsyncGenerator[dict, None]:
    """Agent 执行的唯一入口。

    编排模式执行 + Middleware 管线。
    启用 LLM 缓存时自动走缓存路径。
    """
    mws = middlewares or []

    # 通知中间件运行开始
    for mw in mws:
        await mw.on_run_start(ctx)

    try:
        if settings.enable_llm_cache:
            async for event in _cached_run(message, session_history, ctx, mws):
                yield event
        else:
            async for event in _run_uncached(message, session_history, ctx, mws):
                yield event
    finally:
        # 通知中间件运行结束
        for mw in mws:
            await mw.on_run_end(ctx)


async def _cached_run(message, session_history, ctx, mws):
    """带 LLM 缓存的执行路径。"""
    from prompt_builder import build_system_prompt
    from cache import llm_cache

    system_prompt = build_system_prompt()
    recent_history = []
    for msg in session_history[-3:]:
        recent_history.append({
            "role": msg.get("role", ""),
            "content": msg.get("content", "")[:500],
        })

    cache_key_params = {
        "system_prompt": system_prompt,
        "recent_history": recent_history,
        "current_message": message,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }

    async def generator():
        async for event in _run_uncached(message, session_history, ctx, mws):
            yield event

    async for event in llm_cache.get_or_generate(
        key_params=cache_key_params,
        generator_func=generator,
        stream=ctx.stream,
    ):
        yield event


async def _run_uncached(message, session_history, ctx, mws):
    """核心执行：DirectMode → 可选 PlanMode。"""
    ctx.message = message
    ctx.session_history = session_history

    # Phase 1: DirectMode
    direct = DirectMode()
    async for event in _pipe(direct.execute(ctx), mws, ctx):
        yield event

    # Phase 2: PlanMode（当 plan_create 被触发时）
    if ctx.plan_data:
        # 审批门
        if settings.plan_require_approval:
            from plan_approval import register_plan_approval, get_plan_approval_result

            ctx.emit_plan_event({
                "type": events.PLAN_APPROVAL_REQUEST,
                "plan_id": ctx.plan_data["plan_id"],
                "title": ctx.plan_data["title"],
                "steps": ctx.plan_data["steps"],
            })

            approval_event = register_plan_approval(ctx.plan_data["plan_id"])
            await approval_event.wait()
            approved = get_plan_approval_result(ctx.plan_data["plan_id"])

            if not approved:
                yield events.build_token("\n\n用户已拒绝计划执行。")
                yield events.build_done()
                return

        # 构建原始消息，用于 Executor 子 Agent 上下文
        original_messages = convert_history(session_history)
        original_messages.append(HumanMessage(content=message))

        plan_mode = PlanMode(ctx.plan_data, original_messages)
        async for event in _pipe(plan_mode.execute(ctx), mws, ctx):
            yield event
    else:
        yield events.build_done()


async def _pipe(events_gen, middlewares, ctx):
    """将事件流路由经过 Middleware 链。"""
    async for event in events_gen:
        processed = event
        for mw in middlewares:
            processed = await mw.on_event(processed, ctx)
            if processed is None:
                break
        if processed is not None:
            yield processed
