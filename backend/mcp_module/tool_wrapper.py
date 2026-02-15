"""Wrap MCP tools as LangChain StructuredTool instances with caching."""
import hashlib
import json
import logging
from typing import Any, TYPE_CHECKING

from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from mcp import ClientSession

logger = logging.getLogger(__name__)


def _get_mcp_tool_cache(tool_name: str):
    """Create L1 + L2 cache instances for an MCP tool.

    Returns (l1, l2) tuple, or (None, None) if caching is unavailable.
    """
    try:
        from config import settings
        from cache.memory_cache import MemoryCache
        from cache.disk_cache import DiskCache

        ttl = settings.mcp_tool_cache_ttl
        l1 = MemoryCache(
            max_size=settings.cache_max_memory_items,
            default_ttl=ttl,
        )
        l2 = DiskCache(
            cache_dir=settings.cache_dir,
            cache_type=f"tool_{tool_name}",
            default_ttl=ttl,
            max_size_mb=settings.cache_max_disk_size_mb,
        )
        return l1, l2
    except Exception as e:
        logger.warning(f"Failed to create cache for MCP tool '{tool_name}': {e}")
        return None, None


def _compute_cache_key(tool_name: str, kwargs: dict) -> str:
    """Compute SHA256 cache key from tool name + arguments."""
    cache_input = json.dumps(
        {"tool": tool_name, "args": kwargs},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(cache_input.encode("utf-8")).hexdigest()


def mcp_tool_to_langchain(
    server_name: str,
    tool_info: Any,
    session: "ClientSession",
) -> StructuredTool:
    """Convert a single MCP tool into a LangChain StructuredTool.

    Args:
        server_name: Name of the MCP server (used for tool name prefix).
        tool_info: MCP tool metadata (has .name, .description, .inputSchema).
        session: The active MCP ClientSession to forward calls through.
    """
    mcp_tool_name = tool_info.name
    lc_tool_name = f"mcp_{server_name}_{mcp_tool_name}"
    description = tool_info.description or f"MCP tool: {mcp_tool_name}"

    # Build JSON Schema for LangChain from MCP inputSchema
    input_schema = tool_info.inputSchema or {"type": "object", "properties": {}}

    # Create per-tool cache (L1 memory + L2 disk)
    l1_cache, l2_cache = _get_mcp_tool_cache(lc_tool_name)

    async def _call_mcp_tool(**kwargs: Any) -> str:
        """Forward tool call to MCP server session, with L1+L2 caching."""
        # --- Cache lookup ---
        if l1_cache and l2_cache:
            cache_key = _compute_cache_key(lc_tool_name, kwargs)

            # L1 check
            cached = l1_cache.get(cache_key)
            if cached is not None:
                logger.info(f"✓ MCP Cache L1 hit: {lc_tool_name}")
                return "[CACHE_HIT]" + cached

            # L2 check
            cached = l2_cache.get(cache_key)
            if cached is not None:
                logger.info(f"✓ MCP Cache L2 hit: {lc_tool_name}")
                l1_cache.set(cache_key, cached)  # promote to L1
                return "[CACHE_HIT]" + cached

        # --- Cache miss: call MCP server ---
        try:
            result = await session.call_tool(mcp_tool_name, arguments=kwargs)
            # Combine all content parts into a single string
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                else:
                    parts.append(str(content))
            output = "\n".join(parts) if parts else "(empty response)"

            # Store in cache
            if l1_cache and l2_cache and output:
                l1_cache.set(cache_key, output)
                l2_cache.set(cache_key, output)
                logger.debug(f"✓ MCP Cached result: {lc_tool_name}")

            return output
        except Exception as e:
            logger.error(f"MCP tool call failed ({lc_tool_name}): {e}")
            return f"Error calling MCP tool: {e}"

    tool = StructuredTool.from_function(
        coroutine=_call_mcp_tool,
        name=lc_tool_name,
        description=description,
        args_schema=None,  # We pass raw JSON schema below
    )

    # Override the args_schema with raw JSON schema dict so LangChain uses it
    # for generating the tool spec sent to the LLM.
    tool.args_schema = None
    tool.args = input_schema.get("properties", {})

    # Store the full JSON schema so LangGraph can use it
    tool.schema_ = input_schema

    return tool


def mcp_tools_to_langchain(
    server_name: str,
    tools_list: list[Any],
    session: "ClientSession",
) -> list[StructuredTool]:
    """Convert a list of MCP tools to LangChain tools."""
    lc_tools = []
    for tool_info in tools_list:
        try:
            lc_tool = mcp_tool_to_langchain(server_name, tool_info, session)
            lc_tools.append(lc_tool)
        except Exception as e:
            logger.warning(f"Failed to wrap MCP tool '{tool_info.name}': {e}")
    return lc_tools
