"""Wrap MCP tools as LangChain StructuredTool instances with caching."""
import hashlib
import json
import logging
from typing import Any, Optional, TYPE_CHECKING

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

if TYPE_CHECKING:
    from mcp import ClientSession

logger = logging.getLogger(__name__)


def _json_type_to_python(json_type: str) -> type:
    """将 JSON Schema 类型字符串映射到对应的 Python 类型。"""
    type_map: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, Any)


def _build_args_schema(tool_name: str, input_schema: dict) -> type[BaseModel]:
    """根据 MCP inputSchema 动态构建 Pydantic 模型，用作 StructuredTool 的 args_schema。

    将 JSON Schema 的 properties/required 转换为 Pydantic 字段定义，
    使 LangChain / LangGraph 能正确生成传给 LLM 的工具调用参数规范。
    相比事后赋值 tool.schema_ 的方式，此方法兼容 Pydantic v2 严格模式。
    """
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))

    if not properties:
        # 无参数工具：返回空模型
        return create_model(f"{tool_name}Args")

    field_definitions: dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        py_type = _json_type_to_python(field_schema.get("type", "string"))
        description = field_schema.get("description", "")

        if field_name in required_fields:
            # 必填字段：不设默认值
            field_definitions[field_name] = (py_type, Field(description=description))
        else:
            # 可选字段：默认为 None
            field_definitions[field_name] = (
                Optional[py_type],
                Field(default=None, description=description),
            )

    return create_model(f"{tool_name}Args", **field_definitions)


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

    # 从 MCP inputSchema 构建 Pydantic 模型，供 LangChain 生成工具调用参数规范
    input_schema = tool_info.inputSchema or {"type": "object", "properties": {}}
    args_schema_model = _build_args_schema(lc_tool_name, input_schema)

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

    # 通过正规 args_schema 传入动态构建的 Pydantic 模型，
    # 兼容 Pydantic v2 严格模式，避免事后赋值非标准属性导致的 AttributeError
    tool = StructuredTool.from_function(
        coroutine=_call_mcp_tool,
        name=lc_tool_name,
        description=description,
        args_schema=args_schema_model,
    )

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
