"""RunContext — 每请求上下文，替代全局状态。

持有会话信息、计划状态和事件侧通道。
消除了旧架构中的 6 个全局变量。
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    session_id: str
    debug: bool = False
    stream: bool = True

    # 由 runner 在模式执行前设置
    message: str = ""
    session_history: list = field(default_factory=list)

    # 计划状态（替代 plan_tool._latest_plan）
    plan_data: Optional[dict] = None

    # 事件侧通道（替代 _sse_plan_callback + _sse_approval_callback）
    plan_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    event_loop: Optional[asyncio.AbstractEventLoop] = None

    def emit_plan_event(self, event: dict) -> None:
        """线程安全地发送计划事件到 SSE 流。"""
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.call_soon_threadsafe(self.plan_queue.put_nowait, event)
        else:
            try:
                self.plan_queue.put_nowait(event)
            except Exception:
                logger.warning("发送计划事件失败：事件循环不可用")
