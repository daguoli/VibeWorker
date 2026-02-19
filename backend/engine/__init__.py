"""Engine 模块 — Agent 编排引擎。

公共 API：
    run_agent       - Agent 执行的唯一入口
    RunContext      - 每请求上下文对象
    get_llm         - LLM 工厂（带配置指纹缓存）
    create_llm      - get_llm 的兼容别名
    serialize_sse   - SSE 序列化辅助函数
    invalidate_caches - 清除所有缓存的 LLM 实例
"""
from engine.runner import run_agent
from engine.context import RunContext
from engine.llm_factory import get_llm, create_llm, invalidate_llm_cache
from engine.events import serialize_sse


def invalidate_caches():
    """清除引擎级别的所有缓存（LLM 实例等）。"""
    invalidate_llm_cache()


__all__ = [
    "run_agent",
    "RunContext",
    "get_llm",
    "create_llm",
    "serialize_sse",
    "invalidate_caches",
]
