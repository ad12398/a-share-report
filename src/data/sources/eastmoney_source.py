"""东方财富数据源 —— 北向资金 & 龙虎榜（纯 HTTP API + 重试）"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def _safe_get(url: str, timeout: int = 15, max_retries: int = 3) -> requests.Response | None:
    """带重试的 HTTP GET"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text and resp.text.strip():
                return resp
        except Exception as e:
            logger.warning(f"API 请求失败 (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    return None


def fetch_north_flow() -> dict[str, Any]:
    """获取北向资金当日净流向（东方财富）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/kamt.kline/get?"
            "fields1=f1,f3&fields2=f2,f4&klt=1&lmt=5"
        )
        resp = _safe_get(url)
        if resp is None:
            return {}
        data = resp.json()
        if data.get("data") and data["data"].get("s2n"):
            items = data["data"]["s2n"]
            if items:
                latest = items[-1]
                return {
                    "net_flow": float(latest.get("f2", 0) or 0),
                }
        return {}
    except Exception as e:
        logger.error(f"北向资金获取失败: {e}")
        return {}


def fetch_dragon_tiger() -> list[dict[str, Any]]:
    """获取今日龙虎榜（东方财富）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=20&po=1&np=1&fs=m:0+t:3&fid=f3"
            "&fields=f2,f3,f12,f14,f152"
        )
        resp = _safe_get(url)
        if resp is None:
            return {}
        data = resp.json()
        result = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                result.append({
                    "code": str(item.get("f12", "")),
                    "name": str(item.get("f14", "")),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "reason": str(item.get("f152", "")),
                })
        logger.info(f"龙虎榜获取 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"龙虎榜获取失败: {e}")
        return []
