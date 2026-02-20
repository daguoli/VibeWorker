"""OpenRouter 定价模块 — 模型成本计算。

提供：
- OpenRouter API 模型定价数据获取
- 模型名称模糊匹配
- 对话成本计算

使用方式：
    from pricing import pricing_manager

    # 启动时获取定价（每日一次）
    if pricing_manager.should_fetch_today():
        await pricing_manager.fetch_and_cache()

    # 计算成本
    cost = pricing_manager.calculate_cost("gpt-4o", 1000, 500)
"""

from .cost_calculator import PricingManager

# 单例实例
pricing_manager = PricingManager()

__all__ = ["pricing_manager", "PricingManager"]
