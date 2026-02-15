"""MCP (Model Context Protocol) module.

Provides MCPManager singleton for managing external MCP server connections.
"""
from mcp_module.manager import MCPManager

# Module-level singleton
mcp_manager = MCPManager()

__all__ = ["mcp_manager", "MCPManager"]
