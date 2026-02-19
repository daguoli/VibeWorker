"""执行模式的基础协议定义。"""
from __future__ import annotations

from typing import AsyncGenerator, Protocol, runtime_checkable

from engine.context import RunContext


@runtime_checkable
class ExecutionMode(Protocol):
    """所有执行模式必须实现的协议。"""

    async def execute(self, ctx: RunContext) -> AsyncGenerator[dict, None]:
        """执行 Agent 并 yield 事件 dict。"""
        ...
