"""涓滄柟璐㈠瘜鏁版嵁婧?鈥斺€?鍖楀悜璧勯噾 & 榫欒檸姒滐紙绾?HTTP API锛?""

import logging
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def fetch_north_flow() -> dict[str, Any]:
    """鑾峰彇鍖楀悜璧勯噾褰撴棩鍑€娴佸悜锛堜笢鏂硅储瀵岋級"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/kamt.kline/get?"
            "fields1=f1,f3&fields2=f2,f4&klt=1&lmt=5"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
        logger.error(f"鍖楀悜璧勯噾鑾峰彇澶辫触: {e}")
        return {}


def fetch_dragon_tiger() -> list[dict[str, Any]]:
    """鑾峰彇浠婃棩榫欒檸姒滐紙涓滄柟璐㈠瘜锛?""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=20&po=1&np=1&fs=m:0+t:3&fid=f3"
            "&fields=f2,f3,f12,f14,f152"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
        logger.info(f"榫欒檸姒滆幏鍙?{len(result)} 鏉?)
        return result
    except Exception as e:
        logger.error(f"榫欒檸姒滆幏鍙栧け璐? {e}")
        return []
