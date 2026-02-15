"""Terminal Tool - Execute shell commands in a sandboxed environment."""
import re
import subprocess
from typing import Optional

from langchain_core.tools import tool
from config import PROJECT_ROOT

# Dangerous command patterns blacklist
BLACKLISTED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"mkfs\.",
    r"dd\s+if=",
    r":\(\)\s*\{",       # fork bomb
    r"chmod\s+-R\s+777\s+/",
    r"shutdown",
    r"reboot",
    r"halt",
    r"init\s+0",
    r"format\s+[a-zA-Z]:",   # Windows format
    r"del\s+/[sfq]",         # Windows dangerous delete
]


def _is_command_safe(command: str) -> bool:
    """Check if a command is safe to execute."""
    for pattern in BLACKLISTED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False
    return True


@tool
def terminal(command: str, timeout: Optional[int] = 30) -> str:
    """Execute a shell command in a sandboxed environment.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        Command output (stdout + stderr).
    """
    if not _is_command_safe(command):
        return "❌ Error: This command has been blocked for security reasons. It matches a dangerous pattern."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=None,  # Use current environment
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code]: {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"❌ Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"❌ Error executing command: {str(e)}"


def create_terminal_tool():
    """Factory function to create the terminal tool."""
    return terminal
