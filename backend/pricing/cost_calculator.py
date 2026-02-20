"""成本计算器 — 整合定价获取、缓存和计算。

PricingManager 是 pricing 模块的核心类，提供：
- 每日首次获取 OpenRouter 定价数据
- 本地 JSON 缓存
- 模型名称模糊匹配
- 对话成本计算
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from config import settings

from .model_matcher import ModelMatcher
from .openrouter_client import fetch_openrouter_models, models_to_dict, dict_to_models

logger = logging.getLogger(__name__)


class PricingManager:
    """模型定价管理器。

    职责：
    1. 管理 OpenRouter 定价数据的获取和缓存
    2. 提供模型名称匹配
    3. 计算对话成本

    缓存文件：
    - pricing/models.json: 模型定价数据
    - pricing/last_fetch_date: 上次获取日期
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """初始化定价管理器。

        Args:
            cache_dir: 缓存目录，默认使用 settings.pricing_cache_dir
        """
        self._cache_dir = cache_dir or Path(settings.get_data_path()) / "pricing"
        self._models_file = self._cache_dir / "models.json"
        self._date_file = self._cache_dir / "last_fetch_date"

        # 内存缓存
        self._models_cache: Optional[dict] = None
        self._matcher: Optional[ModelMatcher] = None

        # 确保缓存目录存在
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def should_fetch_today(self) -> bool:
        """检查今天是否需要获取定价数据。

        返回 True 的情况：
        1. 从未获取过（date 文件不存在）
        2. 上次获取不是今天
        """
        if not self._date_file.exists():
            return True

        try:
            last_date_str = self._date_file.read_text().strip()
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            return last_date != date.today()
        except Exception:
            return True

    async def fetch_and_cache(self) -> bool:
        """从 OpenRouter 获取定价数据并缓存。

        Returns:
            是否成功获取
        """
        try:
            models = await fetch_openrouter_models()
            if not models:
                logger.warning("OpenRouter 返回空模型列表")
                return False

            # 转换为字典并保存
            models_dict = models_to_dict(models)
            self._models_file.write_text(
                json.dumps(models_dict, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 更新获取日期
            self._date_file.write_text(date.today().strftime("%Y-%m-%d"))

            # 更新内存缓存
            self._models_cache = models_dict
            self._matcher = ModelMatcher(models_dict)

            logger.info(f"OpenRouter 定价数据已更新：{len(models_dict)} 个模型")
            return True

        except Exception as e:
            logger.warning(f"获取 OpenRouter 定价失败: {e}")
            return False

    def _load_cache(self) -> dict:
        """加载缓存的定价数据。"""
        if self._models_cache is not None:
            return self._models_cache

        if self._models_file.exists():
            try:
                data = json.loads(self._models_file.read_text(encoding="utf-8"))
                self._models_cache = data
                self._matcher = ModelMatcher(data)
                logger.debug(f"从缓存加载 {len(data)} 个模型定价")
                return data
            except Exception as e:
                logger.warning(f"加载定价缓存失败: {e}")

        return {}

    def get_matcher(self) -> Optional[ModelMatcher]:
        """获取模型匹配器。"""
        if self._matcher is None:
            self._load_cache()
        return self._matcher

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[dict]:
        """计算对话成本。

        Args:
            model: 用户配置的模型名
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数

        Returns:
            成本信息字典，包含：
            - input_cost: 输入成本（美元）
            - output_cost: 输出成本（美元）
            - total_cost: 总成本（美元）
            - matched_model: 匹配到的 OpenRouter 模型 ID
            如果无法匹配模型则返回 None
        """
        matcher = self.get_matcher()
        if matcher is None:
            logger.debug("定价数据未加载，无法计算成本")
            return None

        pricing = matcher.get_pricing(model)
        if pricing is None:
            logger.debug(f"模型 {model} 未匹配到定价信息")
            return None

        # 获取单价（$/token）
        prompt_price = pricing.get("prompt_price", 0)
        completion_price = pricing.get("completion_price", 0)

        # 计算成本
        input_cost = input_tokens * prompt_price
        output_cost = output_tokens * completion_price
        total_cost = input_cost + output_cost

        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "matched_model": pricing.get("model_id", model),
            # 模型详情（用于前端悬停显示）
            "model_info": {
                "name": pricing.get("name", ""),
                "description": pricing.get("description", ""),
                "context_length": pricing.get("context_length", 0),
                "prompt_price": prompt_price,          # $/token
                "completion_price": completion_price,  # $/token
            },
        }

    def get_model_pricing(self, model: str) -> Optional[dict]:
        """获取模型的定价信息。

        Args:
            model: 用户配置的模型名

        Returns:
            定价信息字典，或 None
        """
        matcher = self.get_matcher()
        if matcher is None:
            return None
        return matcher.get_pricing(model)

    def get_cache_info(self) -> dict:
        """获取缓存状态信息。"""
        models = self._load_cache()
        last_date = None
        if self._date_file.exists():
            try:
                last_date = self._date_file.read_text().strip()
            except Exception:
                pass

        return {
            "models_count": len(models),
            "last_fetch_date": last_date,
            "cache_file": str(self._models_file),
            "needs_update": self.should_fetch_today(),
        }

    def clear_cache(self) -> bool:
        """清除缓存（强制下次重新获取）。"""
        try:
            if self._models_file.exists():
                self._models_file.unlink()
            if self._date_file.exists():
                self._date_file.unlink()
            self._models_cache = None
            self._matcher = None
            logger.info("定价缓存已清除")
            return True
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return False
