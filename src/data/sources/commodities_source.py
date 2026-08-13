"""大宗商品、汇率、全球指数 — 新浪财经 API"""

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
REFERER = {"Referer": "https://finance.sina.com.cn"}


def _safe_get(url: str, timeout: int = 15, max_retries: int = 3) -> requests.Response | None:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers={**HEADERS, **REFERER}, timeout=timeout)
            if resp.status_code == 200 and resp.text and resp.text.strip():
                return resp
        except Exception as e:
            logger.warning(f"商品请求失败 (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    return None


def _parse_futures(text: str, price_idx: int, prev_idx: int, name: str, unit: str) -> dict[str, Any] | None:
    try:
        m = re.search(r'"(.+)"', text)
        if not m: return None
        vals = m.group(1).split(",")
        if len(vals) <= max(price_idx, prev_idx): return None
        price = float(vals[price_idx] or 0)
        prev = float(vals[prev_idx] or 0)
        change_pct = round((price - prev) / prev * 100, 2) if prev else 0
        return {"name": name, "price": price, "change_pct": change_pct, "unit": unit}
    except (ValueError, ZeroDivisionError) as e:
        logger.warning(f"期货 {name} 解析失败: {e}")
        return None


def _parse_global_index(text: str) -> dict[str, Any] | None:
    """新浪全球指数格式兼容两种：
    gb_inx:    名称,价格,涨跌幅,日期时间(含":")...
    int_sp500: 名称,价格,涨跌额,涨跌幅
    判断依据：vals[3] 是否含 ":"（时间），
    注意不能用 "-" 判断——int_ 格式的负涨跌幅（如 -0.17）也含 "-"，会误判
    """
    m = re.search(r'"(.+)"', text)
    if not m: return None
    vals = m.group(1).split(",")
    if len(vals) < 4: return None
    name = vals[0]
    price = float(vals[1] or 0)
    third = vals[3].strip()
    if ":" in third:
        # gb_* 格式：vals[2]=涨跌幅, vals[3]=时间
        return {"name": name, "price": price, "change_pct": float(vals[2] or 0), "unit": "点"}
    else:
        # int_* 格式：vals[2]=涨跌额, vals[3]=涨跌幅
        return {"name": name, "price": price, "change_pct": float(vals[3] or 0), "unit": "点"}


# ─── 主入口 ──────────────────────────────────────────────

def fetch_all_commodities() -> dict[str, Any]:
    """采集商品/汇率/全球指数。任何单项失败都不影响其它项和主流程。"""
    result = {}

    # 期货商品: (code, price_idx, prev_idx, name, unit)
    futures = [
        ("hf_XAU", 0, 1, "伦敦金", "美元/盎司"),
        ("hf_GC", 0, 7, "COMEX黄金", "美元/盎司"),
        ("hf_CL", 0, 2, "WTI原油", "美元/桶"),
        ("hf_CAD", 0, 7, "LME铜", "美元/吨"),
    ]
    for code, pi, pv, name, unit in futures:
        try:
            resp = _safe_get(f"http://hq.sinajs.cn/list={code}")
            if resp:
                resp.encoding = "gbk"
                item = _parse_futures(resp.text, pi, pv, name, unit)
                if item:
                    result[name] = item
        except Exception as e:
            logger.warning(f"商品 {name} 采集失败: {e}")

    # 汇率（实测格式: [0]时间 [1]买入 [2]卖出 [3]昨收 [5]今开 [6]最高 [7]最低 [8]最新价 [9]名称）
    try:
        resp = _safe_get("http://hq.sinajs.cn/list=fx_susdcny")
        if resp:
            resp.encoding = "gbk"
            m = re.search(r'"(.+)"', resp.text)
            if m:
                vals = m.group(1).split(",")
                if len(vals) >= 9:
                    price = float(vals[8] or 0)       # 最新价
                    prev = float(vals[3] or 0)        # 昨收
                    pct = round((price - prev) / prev * 100, 2) if prev else 0
                    direction = "贬值" if pct > 0 else ("升值" if pct < 0 else "持平")
                    result["在岸人民币"] = {
                        "name": "在岸人民币", "price": price, "change_pct": pct,
                        "unit": "USD/CNY", "direction": direction,
                    }
    except Exception as e:
        logger.warning(f"在岸人民币采集失败: {e}")

    # 美股三大指数
    for code in ("gb_dji", "gb_inx", "gb_ixic"):
        try:
            resp = _safe_get(f"http://hq.sinajs.cn/list={code}")
            if resp:
                resp.encoding = "gbk"
                item = _parse_global_index(resp.text)
                if item:
                    result[item["name"]] = item
        except Exception as e:
            logger.warning(f"全球指数 {code} 采集失败: {e}")

    return result
