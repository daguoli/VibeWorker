"""Read File Tool - Read local file content with security restrictions."""
from pathlib import Path

from langchain_core.tools import tool
from config import PROJECT_ROOT


@tool
def read_file(file_path: str) -> str:
    """Read the content of a local file.

    This tool reads files within the project directory. It is commonly used
    to read SKILL.md files for learning new skills, or to read memory/config files.

    Args:
        file_path: Path to the file to read (relative to project root or absolute).

    Returns:
        The content of the file, or an error message.
    """
    try:
        path = Path(file_path)

        # If relative, resolve from project root
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        path = path.resolve()

        # Security check: must be within project root
        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError:
            return f"❌ Error: Access denied. Cannot read files outside the project directory: {path}"

        if not path.exists():
            return f"❌ Error: File not found: {file_path}"

        if not path.is_file():
            return f"❌ Error: Path is not a file: {file_path}"

        content = path.read_text(encoding="utf-8")

        # Limit output for very large files
        if len(content) > 20000:
            content = content[:20000] + "\n\n...[file content truncated at 20000 chars]"

        return content

    except UnicodeDecodeError:
        return f"❌ Error: File is not a text file or has encoding issues: {file_path}"
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


def create_read_file_tool():
    """Factory function to create the read_file tool."""
    return read_file
