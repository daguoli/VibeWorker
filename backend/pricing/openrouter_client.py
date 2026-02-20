"""OpenRouter API 客户端 — 获取模型定价数据。

OpenRouter API 端点：GET https://openrouter.ai/api/v1/models
返回所有可用模型及其定价信息。
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# OpenRouter 模型列表 API 端点
OPENROUTER_MODELS_API = "https://openrouter.ai/api/v1/models"


@dataclass
class ModelPricing:
    """模型定价信息。"""
    model_id: str              # 完整模型 ID，如 "anthropic/claude-3-opus-20240229"
    name: str                  # 显示名称
    prompt_price: float        # 输入价格（$/token）
    completion_price: float    # 输出价格（$/token）
    context_length: int        # 上下文长度
    description: str = ""      # 模型描述

    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "prompt_price": self.prompt_price,
            "completion_price": self.completion_price,
            "context_length": self.context_length,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelPricing":
        """从字典创建实例。"""
        return cls(
            model_id=data.get("model_id", ""),
            name=data.get("name", ""),
            prompt_price=float(data.get("prompt_price", 0)),
            completion_price=float(data.get("completion_price", 0)),
            context_length=int(data.get("context_length", 0)),
            description=data.get("description", ""),
        )


async def fetch_openrouter_models(timeout: float = 30.0) -> list[ModelPricing]:
    """从 OpenRouter API 获取所有模型的定价信息。

    Args:
        timeout: 请求超时时间（秒）

    Returns:
        模型定价列表

    Raises:
        httpx.HTTPError: 网络请求失败
        ValueError: 响应格式错误
    """
    logger.info("正在从 OpenRouter 获取模型定价数据...")

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(OPENROUTER_MODELS_API)
        response.raise_for_status()

    data = response.json()
    models_data = data.get("data", [])

    if not models_data:
        raise ValueError("OpenRouter API 返回空的模型列表")

    pricing_list = []
    for model in models_data:
        try:
            # OpenRouter 的 pricing 结构：
            # "pricing": {"prompt": "0.000015", "completion": "0.00006", ...}
            pricing = model.get("pricing", {})

            # 解析价格（字符串 -> float）
            # OpenRouter 返回的是 $/token，直接使用
            prompt_price_str = pricing.get("prompt", "0")
            completion_price_str = pricing.get("completion", "0")

            # 处理可能的格式问题（如 "-1" 表示不可用）
            try:
                prompt_price = float(prompt_price_str) if prompt_price_str != "-1" else 0
            except (ValueError, TypeError):
                prompt_price = 0

            try:
                completion_price = float(completion_price_str) if completion_price_str != "-1" else 0
            except (ValueError, TypeError):
                completion_price = 0

            pricing_list.append(ModelPricing(
                model_id=model.get("id", ""),
                name=model.get("name", ""),
                prompt_price=prompt_price,
                completion_price=completion_price,
                context_length=model.get("context_length", 0),
                description=model.get("description", ""),
            ))
        except Exception as e:
            # 单个模型解析失败不影响整体
            logger.debug(f"跳过模型 {model.get('id', 'unknown')}: {e}")
            continue

    logger.info(f"成功获取 {len(pricing_list)} 个模型的定价数据")
    return pricing_list


def models_to_dict(models: list[ModelPricing]) -> dict:
    """将模型列表转换为以 model_id 为键的字典。"""
    return {m.model_id: m.to_dict() for m in models}


def dict_to_models(data: dict) -> list[ModelPricing]:
    """从字典恢复模型列表。"""
    return [ModelPricing.from_dict(v) for v in data.values()]
