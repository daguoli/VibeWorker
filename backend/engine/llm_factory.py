"""LLM 工厂 — 创建并缓存 ChatOpenAI 实例。

通过配置指纹判断是否复用实例，配置未变时直接返回缓存。
"""
import hashlib
import logging

from langchain_openai import ChatOpenAI

from config import settings

logger = logging.getLogger(__name__)

_llm_cache: dict[str, ChatOpenAI] = {}


def _config_fingerprint(scenario: str = "llm") -> str:
    """根据当前模型配置生成短哈希，用于缓存键。"""
    from model_pool import resolve_model
    cfg = resolve_model(scenario)
    raw = (f"{cfg['api_key']}|{cfg['api_base']}|{cfg['model']}"
           f"|{settings.llm_temperature}|{settings.llm_max_tokens}"
           f"|{settings.llm_request_timeout}")
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_llm(streaming: bool = True, scenario: str = "llm") -> ChatOpenAI:
    """获取或创建 ChatOpenAI 实例。配置未变时复用缓存。"""
    fp = _config_fingerprint(scenario)
    key = f"{fp}_{streaming}"
    if key not in _llm_cache:
        from model_pool import resolve_model
        cfg = resolve_model(scenario)
        _llm_cache[key] = ChatOpenAI(
            model=cfg["model"],
            api_key=cfg["api_key"],
            base_url=cfg["api_base"],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            streaming=streaming,
            timeout=settings.llm_request_timeout,
        )
        logger.info("LLM 实例已创建: model=%s, base=%s, temperature=%s, timeout=%ds",
                     cfg["model"], cfg["api_base"], settings.llm_temperature,
                     settings.llm_request_timeout)
    else:
        logger.debug("LLM 实例已复用: fingerprint=%s", fp)
    return _llm_cache[key]


def create_llm(streaming: bool = True) -> ChatOpenAI:
    """get_llm 的兼容别名（供外部调用方使用）。"""
    return get_llm(streaming=streaming)


def invalidate_llm_cache() -> None:
    """清除所有缓存的 LLM 实例。配置变更后应调用此函数。"""
    _llm_cache.clear()
    logger.info("LLM 缓存已清除")
