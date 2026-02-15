"""Python REPL Tool - Execute Python code in an interactive environment."""
import sys
import io
import traceback

from langchain_core.tools import tool


@tool
def python_repl(code: str) -> str:
    """Execute Python code and return the output.

    This tool runs Python code in a temporary environment. Use it for
    calculations, data processing, file operations, and script execution.

    Args:
        code: Python code to execute.

    Returns:
        The output of the code execution (stdout) or error message.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_stdout = io.StringIO()
    redirected_stderr = io.StringIO()
    sys.stdout = redirected_stdout
    sys.stderr = redirected_stderr

    try:
        # Try exec first (for statements), fall back to eval (for expressions)
        try:
            exec_globals: dict = {}
            exec(code, exec_globals)
        except SyntaxError:
            # If it's an expression, eval it and print the result
            result = eval(code)
            if result is not None:
                print(result)

        stdout_output = redirected_stdout.getvalue()
        stderr_output = redirected_stderr.getvalue()

        output = ""
        if stdout_output:
            output += stdout_output
        if stderr_output:
            output += f"\n[stderr]: {stderr_output}"
        return output.strip() or "(no output)"

    except Exception as e:
        return f"❌ Error:\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def create_python_repl_tool():
    """Factory function to create the python_repl tool."""
    return python_repl
