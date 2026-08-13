"""外围市场联动数据源 —— A50期货 / 恒生科技 / 恒生指数 / 离岸人民币（新浪 hq.sinajs.cn）"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn",
}

# 新浪行情代码
SYMBOLS = {
    "a50": "nf_A50",              # 富时A50期货（新加坡交易所，非交易时段为空）
    "hstech": "rt_hkHSTECH",      # 恒生科技指数
    "hsi": "int_hangseng",        # 恒生指数（港股大盘情绪）
    "cnh": "fx_susdcnh",          # 离岸人民币 USD/CNH
}


def _fetch_sina(symbol: str, timeout: int = 6) -> dict[str, Any] | None:
    """获取单个新浪行情数据，返回解析后的 dict 或 None"""
    try:
        url = f"http://hq.sinajs.cn/list={symbol}"
        resp = requests.get(url, headers=SINA_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        resp.encoding = "gbk"
        text = resp.text

        # 正则提取 var hq_str_XXX="...";
        m = re.search(r'hq_str_\w+="(.+)"', text)
        if not m or not m.group(1).strip():
            return None
        return {"symbol": symbol, "data": m.group(1), "raw": text}
    except Exception as e:
        logger.debug(f"外围联动 {symbol} 请求失败: {e}")
        return None


def _parse_hstech(data_str: str) -> dict[str, Any] | None:
    """解析恒生科技指数
    实测格式: [0]代码 [1]名称 [2]最新价 [3]今开 [4]最高 [5]最低 [6]? [7]涨跌额 [8]涨跌幅% ...
    注意: [3] 是今开不是昨收，涨跌幅必须直接用 [8] 官方值
    """
    fields = data_str.split(",")
    if len(fields) < 9:
        return None
    try:
        price = float(fields[2] or 0)
        change_pct = float(fields[8] or 0)  # 官方涨跌幅，勿用今开计算
        return {
            "name": "恒生科技",
            "price": price,
            "change_pct": change_pct,
            "note": "" if price else "尚未开盘",
        }
    except (ValueError, ZeroDivisionError):
        return None


def _parse_cnh(data_str: str) -> dict[str, Any] | None:
    """解析离岸人民币 USD/CNH
    实测格式: [0]时间 [1]买入 [2]卖出 [3]昨收 [4]? [5]今开 [6]最高 [7]最低 [8]最新价 [9]名称 [10]? [11]涨跌额
    """
    fields = data_str.split(",")
    if len(fields) < 9:
        return None
    try:
        price = float(fields[8] or 0)        # 最新价
        prev_close = float(fields[3] or 0)   # 昨收
        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
        # 离岸人民币：涨 = 人民币贬值，跌 = 人民币升值
        direction = "贬值" if change_pct > 0 else "升值" if change_pct < 0 else ""
        return {
            "name": "离岸人民币",
            "price": price,
            "change_pct": change_pct,
            "note": f"USD/CNH {abs(price - prev_close):.4f} {direction}" if price and prev_close and direction else "",
        }
    except (ValueError, ZeroDivisionError):
        return None


def _parse_a50(data_str: str) -> dict[str, Any] | None:
    """解析富时A50期货
    字段: [0]最新价 [1]涨跌额 [2]涨跌幅% [3]昨收 ...
    注意：非新加坡交易时段返回空字符串，此时返回 None
    """
    if not data_str or not data_str.strip():
        return None
    fields = data_str.split(",")
    if len(fields) < 4:
        return None
    try:
        price = float(fields[0] or 0)
        prev_close = float(fields[3] or 0)
        change_pct = float(fields[2] or 0) if len(fields) > 2 else 0
        return {
            "name": "富时A50",
            "price": price,
            "change_pct": change_pct,
            "note": "",
        }
    except (ValueError, ZeroDivisionError):
        return None


def _parse_hsi(data_str: str) -> dict[str, Any] | None:
    """解析恒生指数
    实测格式（4字段短格式）: [0]名称 [1]最新价 [2]涨跌额 [3]涨跌幅%
    """
    fields = data_str.split(",")
    if len(fields) < 4:
        return None
    try:
        price = float(fields[1] or 0)
        change_pct = float(fields[3] or 0)  # 官方涨跌幅
        return {
            "name": "恒生指数",
            "price": price,
            "change_pct": change_pct,
            "note": "" if price else "尚未开盘",
        }
    except (ValueError, ZeroDivisionError):
        return None


def fetch_linked_markets() -> dict[str, Any]:
    """并发获取外围市场联动数据（A50 + 恒生科技 + 恒生指数 + 离岸人民币），返回 KPI 友好格式"""
    result: dict[str, Any] = {}
    parsers = {
        "a50": _parse_a50,
        "hstech": _parse_hstech,
        "hsi": _parse_hsi,
        "cnh": _parse_cnh,
    }

    # 并发请求 4 个接口
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_fetch_sina, sym): key for key, sym in SYMBOLS.items()}
        for future in as_completed(futures, timeout=10):
            key = futures[future]
            try:
                raw = future.result()
                if raw:
                    parsed = parsers[key](raw["data"])
                    if parsed:
                        result[key] = parsed
            except Exception as e:
                logger.debug(f"外围联动 {key} 解析失败: {e}")

    # 记录日志
    names = [v["name"] for v in result.values() if v]
    logger.info(f"外围联动: 获取 {len(result)}/{len(SYMBOLS)} 项 ({', '.join(names)})")
    return result
