"""数据采集主逻辑 —— 多源聚合 + 交叉校验"""

import logging
from typing import Any

from src.data.sources import akshare_source, sina_source, eastmoney_source
from src.data.validator import validate_index_quotes

logger = logging.getLogger("a-share-report")


def collect_all_data(slot: str) -> dict[str, Any]:
    """
    采集所有数据，按报告时段调整内容。

    参数:
        slot: "0925" | "1030" | "1130" | "1400" | "1500"
    """
    logger.info(f"开始采集数据 (slot={slot})")

    # 指数行情（主源 + 备用源）
    index_data = akshare_source.fetch_index_quotes()
    index_backup = sina_source.fetch_index_quotes()

    # 板块表现
    sector_data = akshare_source.fetch_sector_performance()

    # 涨跌榜
    movers_data = akshare_source.fetch_top_movers()

    # 市场概况
    overview_data = akshare_source.fetch_market_overview()

    # 交叉校验指数
    if index_backup:
        index_data = validate_index_quotes(index_data, index_backup)

    # 盘中及收盘数据：北向资金 & 龙虎榜
    north_data: dict = {}
    dragon_data: list = []
    if slot in ("1030", "1130", "1400", "1500"):
        north_data = eastmoney_source.fetch_north_flow()
        if slot in ("1400", "1500"):
            dragon_data = eastmoney_source.fetch_dragon_tiger()

    # 盘前简报特殊数据：隔夜美股
    global_data: dict = {}
    if slot == "0925":
        global_data = _fetch_overnight_global()

    result = {
        "slot": slot,
        "index": index_data,
        "sectors": sector_data,
        "movers": movers_data,
        "overview": overview_data,
        "north_flow": north_data,
        "dragon_tiger": dragon_data,
        "global": global_data,
        "_validation": index_data.pop("_validation", {}),
    }

    logger.info(f"数据采集完成 (slot={slot})")
    return result


def _fetch_overnight_global() -> dict[str, Any]:
    """获取隔夜全球市场数据（盘前简报用）"""
    result = {}
    try:
        import akshare as ak
        df_us = ak.index_us_stock_sina(symbol=".IXIC")
        if df_us is not None and len(df_us) > 0:
            result["us"] = {
                "index": "纳斯达克",
                "price": float(df_us.iloc[-1].get("收盘价", 0)),
                "change_pct": float(df_us.iloc[-1].get("涨跌幅", 0)),
            }
    except Exception as e:
        logger.warning(f"隔夜美股数据获取失败: {e}")

    try:
        df_a50 = None
        try:
            import akshare as ak
            df_a50 = ak.futures_zh_spot(symbol="A50")
        except Exception:
            pass
        if df_a50 is not None and len(df_a50) > 0:
            result["a50"] = {
                "price": float(df_a50.iloc[-1].get("最新价", 0)),
                "change_pct": float(df_a50.iloc[-1].get("涨跌幅", 0)),
            }
    except Exception as e:
        logger.warning(f"A50期货数据获取失败: {e}")

    return result
