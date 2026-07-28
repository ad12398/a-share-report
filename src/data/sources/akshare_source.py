"""数据源 —— 直接 HTTP 请求东方财富/新浪 API，不依赖 akshare 封装"""

import json
import logging
import re
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}


def fetch_index_quotes() -> dict[str, Any]:
    """获取主要指数实时行情（东方财富）"""
    try:
        # 东方财富指数行情 API
        url = (
            "https://push2.eastmoney.com/api/qt/ulist.np/get?"
            "fltt=2&secids=1.000001,0.399001,0.399006,1.000688,1.000300,1.000905"
            "&fields=f2,f3,f4,f5,f6,f12,f14"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        if not data.get("data") or not data["data"].get("diff"):
            logger.warning("东方财富指数 API 返回空数据")
            return _fallback_sina_index()

        result = {}
        name_map = {
            "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
            "000688": "科创50", "000300": "沪深300", "000905": "中证500",
        }
        for item in data["data"]["diff"]:
            code = str(item.get("f12", ""))
            if code in name_map:
                result[code] = {
                    "name": name_map[code],
                    "price": float(item.get("f2", 0) or 0),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "change_amt": float(item.get("f4", 0) or 0),
                    "volume": float(item.get("f5", 0) or 0),
                    "amount": float(item.get("f6", 0) or 0),
                }
        logger.info(f"东财: 获取指数行情 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"东财指数行情获取失败: {e}")
        return _fallback_sina_index()


def _fallback_sina_index() -> dict[str, Any]:
    """备用：新浪指数行情"""
    try:
        codes = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000905"
        url = f"http://hq.sinajs.cn/list={codes}"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        result = {}
        name_map = {
            "sh000001": ("000001", "上证指数"), "sz399001": ("399001", "深证成指"),
            "sz399006": ("399006", "创业板指"), "sh000688": ("000688", "科创50"),
            "sh000300": ("000300", "沪深300"), "sh000905": ("000905", "中证500"),
        }
        for line in resp.text.strip().split("\n"):
            m = re.search(r'hq_str_(\w+)="(.+)"', line)
            if m:
                sid, vals = m.group(1), m.group(2).split(",")
                if sid in name_map and len(vals) >= 4:
                    code, cname = name_map[sid]
                    result[code] = {
                        "name": cname,
                        "price": float(vals[1] or 0),
                        "change_pct": float(vals[3] or 0),
                        "change_amt": float(vals[2] or 0),
                        "volume": float(vals[8] or 0) if len(vals) > 8 else 0,
                        "amount": float(vals[9] or 0) if len(vals) > 9 else 0,
                    }
        logger.info(f"新浪备用: 获取指数行情 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"新浪备用也失败了: {e}")
        return {}


def fetch_sector_performance() -> list[dict[str, Any]]:
    """获取行业板块涨跌榜（东方财富）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=30&po=1&np=1&fs=m:90+t:2&fid=f3"
            "&fields=f2,f3,f4,f12,f14,f128"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        sectors = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                sectors.append({
                    "name": str(item.get("f14", "")),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "leader": str(item.get("f128", "")),
                })
        logger.info(f"东财: 获取行业板块 {len(sectors)} 条")
        return sectors
    except Exception as e:
        logger.error(f"板块数据获取失败: {e}")
        return []


def fetch_top_movers() -> dict[str, list[dict[str, Any]]]:
    """获取涨幅榜和跌幅榜前 20（东方财富）"""
    result = {"gainers": [], "losers": []}
    try:
        # 涨幅榜
        url_up = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=20&po=1&np=1&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fid=f3"
            "&fields=f2,f3,f12,f14"
        )
        resp = requests.get(url_up, headers=HEADERS, timeout=15)
        data = resp.json()
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                result["gainers"].append({
                    "code": str(item.get("f12", "")),
                    "name": str(item.get("f14", "")),
                    "price": float(item.get("f2", 0) or 0),
                    "change_pct": float(item.get("f3", 0) or 0),
                })

        # 跌幅榜
        url_down = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=20&po=0&np=1&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fid=f3"
            "&fields=f2,f3,f12,f14"
        )
        resp = requests.get(url_down, headers=HEADERS, timeout=15)
        data = resp.json()
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                result["losers"].append({
                    "code": str(item.get("f12", "")),
                    "name": str(item.get("f14", "")),
                    "price": float(item.get("f2", 0) or 0),
                    "change_pct": float(item.get("f3", 0) or 0),
                })

        logger.info(f"东财: 涨跌幅榜各 {len(result['gainers'])}/{len(result['losers'])} 条")
        return result
    except Exception as e:
        logger.error(f"涨跌榜获取失败: {e}")
        return result


def fetch_market_overview() -> dict[str, Any]:
    """获取全市场概况（东方财富）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=1&np=1&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
            "&fid=f3&fields=f2,f3,f4,f5,f6,f12,f14"
        )
        # 获取全量数据的涨跌统计
        url_stat = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=5000&np=1&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
            "&fid=f3&fields=f3,f6"
        )
        resp = requests.get(url_stat, headers=HEADERS, timeout=20)
        data = resp.json()
        total = 0
        up = down = flat = 0
        total_amount = 0
        if data.get("data") and data["data"].get("diff"):
            items = data["data"]["diff"]
            total = len(items)
            for item in items:
                pct = float(item.get("f3", 0) or 0)
                if pct > 0:
                    up += 1
                elif pct < 0:
                    down += 1
                else:
                    flat += 1
                total_amount += float(item.get("f6", 0) or 0)

        return {
            "total": total,
            "up": up,
            "down": down,
            "flat": flat,
            "total_amount": total_amount,
            "up_ratio": round(up / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        logger.error(f"市场概况获取失败: {e}")
        return {"total": 0, "up": 0, "down": 0, "flat": 0, "total_amount": 0, "up_ratio": 0}
