"""Session context - provides current session_id to tools.

Uses a module-level variable instead of contextvars.ContextVar because
LangGraph runs sync tools in thread pools where ContextVar doesn't propagate.
Agent tool calls are sequential within a request, so a simple global is safe.
"""
from pathlib import Path

from config import settings

# Module-level session_id, set per request before agent runs
_current_session_id: str = ""


def set_session_id(session_id: str) -> None:
    """Set the current session_id for this request."""
    global _current_session_id
    _current_session_id = session_id


def get_session_id() -> str:
    """Get the current session_id (empty string if not set)."""
    return _current_session_id


def get_session_tmp_dir() -> Path:
    """Get the tmp directory for the current session.

    Returns ~/.vibeworker/tmp/{session_id}/ if session_id is set,
    otherwise ~/.vibeworker/tmp/_default/.
    """
    session_id = get_session_id() or "_default"
    # Sanitize session_id for safe directory name
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "_-")
    tmp_dir = settings.get_data_path() / "tmp" / safe_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir
