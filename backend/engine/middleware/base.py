"""Middleware 协议 — Agent 事件管线接口定义。"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from engine.context import RunContext


@runtime_checkable
class Middleware(Protocol):
    """事件处理中间件协议。

    中间件可以检查、变换或抑制事件，
    事件从执行模式流向 SSE 输出的过程中经过中间件链。
    """

    async def on_event(self, event: dict, ctx: RunContext) -> Optional[dict]:
        """处理单个事件。

        返回 dict 传递给下游，返回 None 则抑制该事件。
        """
        ...

    async def on_run_start(self, ctx: RunContext) -> None:
        """Agent 运行开始时调用。"""
        ...

    async def on_run_end(self, ctx: RunContext) -> None:
        """Agent 运行结束时调用。"""
        ...
