"""数据采集主逻辑 —— 多源聚合 + 交叉校验（纯 HTTP，无 akshare 依赖）"""

import logging
import re
from typing import Any

import requests

from src.data.sources import akshare_source, sina_source, eastmoney_source, commodities_source
from src.data.validator import validate_index_quotes

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def collect_all_data(slot: str) -> dict[str, Any]:
    """采集所有数据，按报告时段调整内容。"""
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

    # 大宗商品 & 汇率
    commodities_data = commodities_source.fetch_all_commodities()

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

    # 清理校验标记——不要传给 DeepSeek，仅供内部日志使用
    validation_info = index_data.pop("_validation", {})
    if validation_info.get("warnings"):
        logger.warning(f"数据校验警告: {validation_info['warnings']}")

    result = {
        "slot": slot,
        "index": index_data,
        "sectors": sector_data,
        "movers": movers_data,
        "overview": overview_data,
        "north_flow": north_data,
        "dragon_tiger": dragon_data,
        "commodities": commodities_data,
        "global": global_data,
    }

    logger.info(f"数据采集完成 (slot={slot})")
    return result


def _fetch_overnight_global() -> dict[str, Any]:
    """获取隔夜全球市场数据（新浪 + 东方财富，无需 akshare）"""
    result = {}

    # 纳斯达克指数（新浪）
    try:
        url = "http://hq.sinajs.cn/list=gb_ixic"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = re.search(r'="(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 2:
                result["us"] = {
                    "index": "纳斯达克",
                    "price": float(vals[1] or 0),
                    "change_pct": float(vals[2] or 0) if len(vals) > 2 else 0,
                }
    except Exception:
        pass

    # 富时A50期货
    try:
        url = "http://hq.sinajs.cn/list=nf_A50"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = re.search(r'="(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 2:
                result["a50"] = {
                    "price": float(vals[1] or 0),
                    "change_pct": float(vals[2] or 0) if len(vals) > 2 else 0,
                }
    except Exception:
        pass

    return result
