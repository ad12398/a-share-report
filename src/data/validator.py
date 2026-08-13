"""数据校验 —— 多源交叉验证"""

import logging

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
        logger.info("指数交叉校验通过")

    return primary | {"_validation": {"warnings": warnings, "passed": len(warnings) == 0}}
