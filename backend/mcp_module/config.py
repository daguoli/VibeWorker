"""MCP Server configuration management.

Handles loading and saving mcp_servers.json.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent.parent / "mcp_servers.json"


def load_config() -> dict[str, Any]:
    """Load MCP server configurations from mcp_servers.json."""
    if not CONFIG_FILE.exists():
        return {"servers": {}}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if "servers" not in data:
            data["servers"] = {}
        return data
    except Exception as e:
        logger.error(f"Failed to load MCP config: {e}")
        return {"servers": {}}


def save_config(data: dict[str, Any]) -> None:
    """Save MCP server configurations to mcp_servers.json."""
    CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_server(name: str) -> dict[str, Any] | None:
    """Get a single server config by name."""
    config = load_config()
    return config["servers"].get(name)


def set_server(name: str, server_config: dict[str, Any]) -> None:
    """Add or update a server config."""
    config = load_config()
    config["servers"][name] = server_config
    save_config(config)


def delete_server(name: str) -> bool:
    """Delete a server config. Returns True if found and deleted."""
    config = load_config()
    if name not in config["servers"]:
        return False
    del config["servers"][name]
    save_config(config)
    return True
