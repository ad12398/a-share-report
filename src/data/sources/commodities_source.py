"""大宗商品 & 汇率数据源 —— 新浪财经 API"""

import logging
import re
import time
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _safe_get(url: str, timeout: int = 15, max_retries: int = 3, extra_headers: dict | None = None) -> requests.Response | None:
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=h, timeout=timeout)
            if resp.status_code == 200 and resp.text and resp.text.strip():
                return resp
        except Exception as e:
            logger.warning(f"商品数据请求失败 (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    return None


def fetch_all_commodities() -> dict[str, Any]:
    """一次性获取黄金、原油、汇率"""
    result = {}
    result["gold"] = _fetch_gold()
    result["oil"] = _fetch_oil()
    result["forex"] = _fetch_forex()
    return result


def _fetch_gold() -> dict[str, Any]:
    """伦敦金（现货黄金）"""
    try:
        resp = _safe_get("http://hq.sinajs.cn/list=hf_XAU", extra_headers={"Referer": "https://finance.sina.com.cn"})
        if not resp:
            return {}
        resp.encoding = "gbk"
        m = re.search(r'"(.+)"', resp.text)
        if not m:
            return {}
        vals = m.group(1).split(",")
        if len(vals) < 6:
            return {}
        # Sina 期货格式: [0]最新价 [1]昨收
        price = float(vals[0] or 0)
        prev = float(vals[1] or 0)
        change_pct = round((price - prev) / prev * 100, 2) if prev else 0
        return {"name": "伦敦金(XAU)", "price": price, "change_pct": change_pct, "unit": "美元/盎司"}
    except Exception as e:
        logger.warning(f"黄金数据获取失败: {e}")
        return {}


def _fetch_oil() -> dict[str, Any]:
    """WTI 原油"""
    try:
        resp = _safe_get("http://hq.sinajs.cn/list=hf_CL", extra_headers={"Referer": "https://finance.sina.com.cn"})
        if not resp:
            return {}
        resp.encoding = "gbk"
        m = re.search(r'"(.+)"', resp.text)
        if not m:
            return {}
        vals = m.group(1).split(",")
        if len(vals) < 3:
            return {}
        # 原油格式: [0]最新价 [2]昨收
        price = float(vals[0] or 0)
        prev = float(vals[2] or 0) if vals[2] else float(vals[0] or 0)
        change_pct = round((price - prev) / prev * 100, 2) if prev else 0
        return {"name": "WTI原油", "price": price, "change_pct": change_pct, "unit": "美元/桶"}
    except Exception as e:
        logger.warning(f"原油数据获取失败: {e}")
        return {}


def _fetch_forex() -> dict[str, Any]:
    """在岸人民币 USD/CNY"""
    try:
        resp = _safe_get("http://hq.sinajs.cn/list=fx_susdcny", extra_headers={"Referer": "https://finance.sina.com.cn"})
        if not resp:
            return {}
        resp.encoding = "gbk"
        m = re.search(r'"(.+)"', resp.text)
        if not m:
            return {}
        vals = m.group(1).split(",")
        if len(vals) < 3:
            return {}
        # 外汇格式: [0]时间 [1]当前价 [2]昨收
        price = float(vals[1] or 0)
        prev = float(vals[2] or 0)
        change_pct = round((price - prev) / prev * 100, 2) if prev else 0
        # 人民币：正值=贬值，负值=升值
        direction = "贬值" if change_pct > 0 else ("升值" if change_pct < 0 else "持平")
        return {
            "name": "在岸人民币",
            "price": price,
            "change_pct": change_pct,
            "unit": "USD/CNY",
            "direction": direction,
        }
    except Exception as e:
        logger.warning(f"汇率数据获取失败: {e}")
        return {}
