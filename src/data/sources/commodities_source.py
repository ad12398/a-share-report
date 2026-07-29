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
    m = re.search(r'"(.+)"', text)
    if not m: return None
    vals = m.group(1).split(",")
    if len(vals) <= max(price_idx, prev_idx): return None
    price = float(vals[price_idx] or 0)
    prev = float(vals[prev_idx] or 0)
    change_pct = round((price - prev) / prev * 100, 2) if prev else 0
    return {"name": name, "price": price, "change_pct": change_pct, "unit": unit}


def _parse_global_index(text: str) -> dict[str, Any] | None:
    m = re.search(r'"(.+)"', text)
    if not m: return None
    vals = m.group(1).split(",")
    if len(vals) < 4: return None
    return {"name": vals[0], "price": float(vals[1] or 0), "change_pct": float(vals[3] or 0), "unit": "点"}


# ─── 主入口 ──────────────────────────────────────────────

def fetch_all_commodities() -> dict[str, Any]:
    result = {}
    # 期货商品: (code, price_idx, prev_idx, name, unit)
    futures = [
        ("hf_XAU", 0, 1, "伦敦金", "美元/盎司"),
        ("hf_GC", 0, 7, "COMEX黄金", "美元/盎司"),
        ("hf_CL", 0, 2, "WTI原油", "美元/桶"),
        ("hf_CAD", 0, 7, "LME铜", "美元/吨"),
    ]
    for code, pi, pv, name, unit in futures:
        resp = _safe_get(f"http://hq.sinajs.cn/list={code}")
        if resp:
            resp.encoding = "gbk"
            item = _parse_futures(resp.text, pi, pv, name, unit)
            if item:
                result[name] = item

    # 汇率
    resp = _safe_get("http://hq.sinajs.cn/list=fx_susdcny")
    if resp:
        resp.encoding = "gbk"
        m = re.search(r'"(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 3:
                price = float(vals[1] or 0)
                prev = float(vals[2] or 0)
                pct = round((price - prev) / prev * 100, 2) if prev else 0
                direction = "贬值" if pct > 0 else ("升值" if pct < 0 else "持平")
                result["在岸人民币"] = {
                    "name": "在岸人民币", "price": price, "change_pct": pct,
                    "unit": "USD/CNY", "direction": direction,
                }

    # 美股三大指数
    for code in ("gb_dji", "gb_inx", "gb_ixic"):
        resp = _safe_get(f"http://hq.sinajs.cn/list={code}")
        if resp:
            resp.encoding = "gbk"
            item = _parse_global_index(resp.text)
            if item:
                result[item["name"]] = item

    return result
