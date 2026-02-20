"""模型名称模糊匹配器。

用户配置的模型名可能与 OpenRouter 的格式不同，需要智能匹配。

匹配策略（按优先级）：
1. 精确匹配（忽略大小写）
2. 移除 provider 前缀后匹配（如 gpt-4o 匹配 openai/gpt-4o）
3. 基础名称匹配（移除日期/版本后缀）
4. 包含关系匹配（用户名包含在 OpenRouter 名中）

示例：
    用户配置              OpenRouter 格式
    --------              ---------------
    claude-3-opus     ->  anthropic/claude-3-opus-20240229
    gpt-4o            ->  openai/gpt-4o
    deepseek-chat     ->  deepseek/deepseek-chat
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_model_name(name: str) -> str:
    """标准化模型名称：小写 + 移除多余空格。"""
    return name.lower().strip()


def strip_provider_prefix(model_id: str) -> str:
    """移除 provider 前缀（如 openai/gpt-4o -> gpt-4o）。"""
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def strip_version_suffix(name: str) -> str:
    """移除版本/日期后缀。

    常见模式：
    - claude-3-opus-20240229 -> claude-3-opus
    - gpt-4-0613 -> gpt-4
    - deepseek-v2.5 -> deepseek-v2
    """
    # 移除日期后缀：-20240229, -0613 等
    name = re.sub(r"-\d{6,8}$", "", name)
    # 移除版本后缀：-v2.5 保留主版本
    name = re.sub(r"\.\d+$", "", name)
    return name


def extract_base_name(name: str) -> str:
    """提取模型基础名称（移除所有修饰符）。

    claude-3-opus-20240229 -> claude-3-opus
    gpt-4-turbo-2024-04-09 -> gpt-4-turbo
    """
    # 移除 provider
    name = strip_provider_prefix(name)
    # 移除版本
    name = strip_version_suffix(name)
    return normalize_model_name(name)


class ModelMatcher:
    """模型名称匹配器。"""

    def __init__(self, openrouter_models: dict[str, dict]):
        """初始化匹配器。

        Args:
            openrouter_models: OpenRouter 模型字典 {model_id: pricing_dict}
        """
        self._models = openrouter_models
        # 构建索引用于快速匹配
        self._build_index()

    def _build_index(self):
        """构建匹配索引。"""
        # 精确匹配索引（小写）
        self._exact_index: dict[str, str] = {}
        # 移除 provider 后的索引
        self._no_provider_index: dict[str, str] = {}
        # 基础名称索引
        self._base_name_index: dict[str, str] = {}

        for model_id in self._models.keys():
            normalized = normalize_model_name(model_id)
            self._exact_index[normalized] = model_id

            # 移除 provider 后的名称
            no_provider = strip_provider_prefix(normalized)
            if no_provider not in self._no_provider_index:
                self._no_provider_index[no_provider] = model_id

            # 基础名称
            base = extract_base_name(normalized)
            if base not in self._base_name_index:
                self._base_name_index[base] = model_id

    def match(self, user_model: str) -> Optional[str]:
        """匹配用户模型名到 OpenRouter model_id。

        Args:
            user_model: 用户配置的模型名

        Returns:
            匹配到的 OpenRouter model_id，或 None
        """
        if not user_model:
            return None

        normalized = normalize_model_name(user_model)

        # 策略 1：精确匹配
        if normalized in self._exact_index:
            logger.debug(f"模型精确匹配: {user_model} -> {self._exact_index[normalized]}")
            return self._exact_index[normalized]

        # 策略 2：移除 provider 后匹配
        no_provider = strip_provider_prefix(normalized)
        if no_provider in self._no_provider_index:
            logger.debug(f"模型 provider 匹配: {user_model} -> {self._no_provider_index[no_provider]}")
            return self._no_provider_index[no_provider]

        # 策略 3：基础名称匹配
        base = extract_base_name(normalized)
        if base in self._base_name_index:
            logger.debug(f"模型基础名匹配: {user_model} -> {self._base_name_index[base]}")
            return self._base_name_index[base]

        # 策略 4：包含关系匹配（用户名是 OpenRouter 名的前缀或子串）
        for openrouter_id in self._models.keys():
            openrouter_normalized = normalize_model_name(openrouter_id)
            openrouter_no_provider = strip_provider_prefix(openrouter_normalized)

            # 检查用户输入是否是 OpenRouter 名的前缀
            if openrouter_no_provider.startswith(normalized):
                logger.debug(f"模型前缀匹配: {user_model} -> {openrouter_id}")
                return openrouter_id

            # 检查用户输入是否包含在 OpenRouter 名中
            if normalized in openrouter_no_provider:
                logger.debug(f"模型子串匹配: {user_model} -> {openrouter_id}")
                return openrouter_id

        logger.debug(f"模型未匹配: {user_model}")
        return None

    def get_pricing(self, user_model: str) -> Optional[dict]:
        """获取用户模型对应的定价信息。

        Args:
            user_model: 用户配置的模型名

        Returns:
            定价字典，或 None
        """
        model_id = self.match(user_model)
        if model_id:
            return self._models.get(model_id)
        return None
