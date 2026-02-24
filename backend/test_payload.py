import asyncio
import json
import logging
import os
import sys

# 设置路径以便加载后端模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from engine.config_loader import load_graph_config
from engine.graph_builder import get_or_build_graph
from langchain_core.messages import HumanMessage
from tools.terminal_tool import create_terminal_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test():
    print("Building graph...")
    graph_config = load_graph_config()
    graph = get_or_build_graph(graph_config)
    
    config = {
        "configurable": {
            "thread_id": "debug-test-session",
            "session_id": "debug-test-session",
            "graph_config": graph_config,
            "agent_tools": [create_terminal_tool()]
        }
    }
    
    input_data = {
        "messages": [HumanMessage(content="Hello, do you have any tools?")]
    }

    print("Running graph...")
    try:
        async for event in graph.astream_events(input_data, version="v2", config=config):
            kind = event.get("event", "")
            if kind == "on_chat_model_start":
                data = event.get("data") or {}
                metadata = event.get("metadata") or {}
                print("\n" + "="*50)
                print("FOUND on_chat_model_start!")
                
                print("EVENT KEYS:", list(event.keys()))
                print("METADATA KEYS:", list(metadata.keys()))
                print("METADATA DUMP:", str(metadata)[:1000])

                # Print specifically the keys inside the data dict and potentially kwargs keys
                print("DATA KEYS:", list(data.keys()))
                if "kwargs" in data:
                    print("KWARGS KEYS:", list(data["kwargs"].keys()))
                    if "tools" in data["kwargs"]:
                        print("TOOLS IN KWARGS:", "Yes")
                        print("FIRST TOOL keys:", list(data["kwargs"]["tools"][0].keys()) if data["kwargs"]["tools"] else "empty list")
                    if "bind_kwargs" in data["kwargs"]:
                        print("BIND KWARGS KEYS:", list(data["kwargs"]["bind_kwargs"].keys()))
                        
                if "invocation_params" in data:
                    print("INVOCATION PARAMS KEYS:", list(data["invocation_params"].keys()))
                if "options" in data:
                    print("OPTIONS KEYS:", list(data["options"].keys()))
                    
                # Log full data for inspection
                print("FULL DATA CHUNK snippet:", str(data)[:1500] + "...")
                print("="*50 + "\n")
                
                # We stop after we find the tools to save time
                break
    except Exception as e:
        print(f"Error running graph: {e}")

if __name__ == "__main__":
    asyncio.run(test())
