"""数据校验 —— 多源交叉验证"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def validate_index_quotes(primary: dict, secondary: dict) -> dict:
    """
    交叉校验指数行情数据。
    如果主源和备源偏差超过阈值，标记 warning。
    返回主源数据 + 校验状态。
    """
    threshold = 0.5  # 0.5% 偏差阈值
    warnings = []

    for code, data in primary.items():
        if code in secondary:
            price1 = data.get("price", 0)
            price2 = secondary[code].get("price", 0)
            if price1 and price2:
                deviation = abs(price1 - price2) / price2 * 100
                if deviation > threshold:
                    msg = f"指数 {data.get('name', code)} 偏差 {deviation:.2f}%"
                    warnings.append(msg)
                    logger.warning(msg)

    if warnings:
        logger.warning(f"指数交叉校验发现 {len(warnings)} 个异常")
    else:
        logger.info("指数交叉校验通过 ✓")

    return primary | {"_validation": {"warnings": warnings, "passed": len(warnings) == 0}}


def validate_sector_data(primary: list, secondary: list) -> list:
    """校验板块排名相关性"""
    if not primary or not secondary:
        return primary

    primary_names = [s["name"] for s in primary[:10]]
    secondary_names = [s["name"] if isinstance(s, dict) else s for s in secondary[:10]]
    overlap = len(set(primary_names) & set(secondary_names))

    if overlap >= len(primary_names) * 0.7:  # 70% 重叠率
        logger.info(f"板块交叉校验通过 ✓（前10名重叠 {overlap}）")
    else:
        logger.warning(f"板块交叉校验异常：前10名仅重叠 {overlap}")

    return primary
