"""会话上下文 — 为工具提供当前 session_id 和 RunContext。

使用 threading.local 实现线程安全，因为 LangGraph 在线程池中运行
同步工具，ContextVar 不会跨线程传播。
"""
import threading
from pathlib import Path
from typing import Optional

from config import settings

_thread_local = threading.local()


def set_run_context(ctx) -> None:
    """设置当前请求线程的 RunContext。"""
    _thread_local.run_ctx = ctx


def get_run_context():
    """获取当前 RunContext（未设置时返回 None）。"""
    return getattr(_thread_local, 'run_ctx', None)


def set_session_id(session_id: str) -> None:
    """设置当前请求的 session_id。"""
    _thread_local.session_id = session_id


def get_session_id() -> str:
    """获取当前 session_id（未设置时返回空字符串）。"""
    ctx = getattr(_thread_local, 'run_ctx', None)
    if ctx:
        return ctx.session_id
    return getattr(_thread_local, 'session_id', '')


def get_session_tmp_dir() -> Path:
    """获取当前会话的临时目录。

    有 session_id 时返回 ~/.vibeworker/tmp/{session_id}/，
    否则返回 ~/.vibeworker/tmp/_default/。
    """
    session_id = get_session_id() or "_default"
    # 清理 session_id 以生成安全的目录名
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "_-")
    tmp_dir = settings.get_data_path() / "tmp" / safe_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir
