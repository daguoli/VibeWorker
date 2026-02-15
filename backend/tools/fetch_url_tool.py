"""Fetch URL Tool - Retrieve web content with HTML cleaning."""
import requests
import html2text

from langchain_core.tools import tool


@tool
def fetch_url(url: str) -> str:
    """Fetch the content of a web page and return it as clean Markdown text.

    This tool retrieves web content, strips HTML tags, and returns readable
    Markdown text. Use it to access web pages, APIs, or any HTTP resources.

    Args:
        url: The URL to fetch content from.

    Returns:
        Cleaned content in Markdown format, or error message.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        # If it's JSON, return raw text
        if "application/json" in content_type:
            return response.text[:10000]  # Limit to 10k chars

        # If it's plain text, return directly
        if "text/plain" in content_type:
            return response.text[:10000]

        # For HTML, clean and convert to Markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.ignore_emphasis = False
        converter.body_width = 0  # Don't wrap lines

        markdown_content = converter.handle(response.text)

        # Limit output size to save tokens
        if len(markdown_content) > 8000:
            markdown_content = markdown_content[:8000] + "\n\n...[content truncated]"

        return markdown_content

    except requests.exceptions.Timeout:
        return f"❌ Error: Request timed out for URL: {url}"
    except requests.exceptions.HTTPError as e:
        return f"❌ HTTP Error {e.response.status_code}: {e}"
    except requests.exceptions.ConnectionError:
        return f"❌ Error: Could not connect to {url}"
    except Exception as e:
        return f"❌ Error fetching URL: {str(e)}"


def create_fetch_url_tool():
    """Factory function to create the fetch_url tool."""
    return fetch_url
