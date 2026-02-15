"""Core Tools Package - 5 built-in tools for VibeWorker Agent."""
from tools.terminal_tool import create_terminal_tool
from tools.python_repl_tool import create_python_repl_tool
from tools.fetch_url_tool import create_fetch_url_tool
from tools.read_file_tool import create_read_file_tool
from tools.rag_tool import create_rag_tool

__all__ = [
    "create_terminal_tool",
    "create_python_repl_tool",
    "create_fetch_url_tool",
    "create_read_file_tool",
    "create_rag_tool",
]


def get_all_tools() -> list:
    """Create and return all 5 core tools."""
    tools = [
        create_terminal_tool(),
        create_python_repl_tool(),
        create_fetch_url_tool(),
        create_read_file_tool(),
        create_rag_tool(),
    ]
    return tools
