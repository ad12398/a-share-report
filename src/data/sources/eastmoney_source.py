"""东方财富数据源 —— 北向资金 & 龙虎榜 & 融资融券（纯 HTTP API + 多端点重试）"""

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

# 东财 API 多端点尝试顺序
EM_BASE_URLS = [
    "https://push2.eastmoney.com",
    "https://push2his.eastmoney.com",
    "https://push2.eastmoney.com",  # 二次尝试（有时第一次超时是偶然的）
]


def _try_endpoints(url_path: str, timeout: int = 15, max_retries: int = 2) -> requests.Response | None:
    """尝试从多个东财端点获取数据"""
    for base in EM_BASE_URLS:
        url = base + url_path
        for attempt in range(max_retries):
            try:
                logger.info(f"东财请求: {url[:80]}... (attempt {attempt+1})")
                resp = requests.get(url, headers=HEADERS, timeout=timeout)
                if resp.status_code == 200 and resp.text and resp.text.strip():
                    return resp
                logger.warning(f"东财返回异常: status={resp.status_code}, len={len(resp.text) if resp.text else 0}")
            except requests.exceptions.Timeout:
                logger.warning(f"东财超时: {url[:80]}... (attempt {attempt+1})")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"东财连接失败: {url[:80]}... ({e})")
            except Exception as e:
                logger.warning(f"东财请求异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
        # 换端点前等待
        time.sleep(2)
    logger.error(f"所有东财端点均失败: {url_path}")
    return None


def fetch_north_flow() -> dict[str, Any]:
    """获取北向资金当日净流向（东方财富）

    返回: {"net_flow": float, "net_flow_sh": float, "net_flow_sz": float} 或 {}
    """
    try:
        # 沪深港通资金流向 K 线（1分钟线，取最新一根）
        url_path = (
            "/api/qt/kamt.kline/get?"
            "fields1=f1,f3&fields2=f2,f4&klt=1&lmt=5"
        )
        resp = _try_endpoints(url_path)
        if resp is None:
            return {}
        data = resp.json()
        result = {}
        if data.get("data"):
            # 北向资金（沪股通 + 深股通）
            if data["data"].get("s2n"):
                items = data["data"]["s2n"]
                if items:
                    latest = items[-1]
                    result["net_flow"] = float(latest.get("f2", 0) or 0)
                    result["net_flow_sh"] = float(latest.get("f2", 0) or 0)  # s2n = 沪
            # 深股通
            if data["data"].get("s2s"):
                items = data["data"]["s2s"]
                if items:
                    latest = items[-1]
                    sz_flow = float(latest.get("f2", 0) or 0)
                    if "net_flow" in result:
                        result["net_flow"] = result["net_flow"] + sz_flow
                    else:
                        result["net_flow"] = sz_flow
                    result["net_flow_sz"] = sz_flow
        if result:
            logger.info(f"北向资金: 净流入 {result.get('net_flow', 0):.2f} 亿")
        return result
    except Exception as e:
        logger.error(f"北向资金获取失败: {e}")
        return {}


def fetch_dragon_tiger() -> list[dict[str, Any]]:
    """获取今日龙虎榜（东方财富）"""
    try:
        url_path = (
            "/api/qt/clist/get?"
            "pn=1&pz=20&po=1&np=1&fs=m:0+t:3&fid=f3"
            "&fields=f2,f3,f12,f14,f152"
        )
        resp = _try_endpoints(url_path)
        if resp is None:
            return []
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


def fetch_margin_trading() -> dict[str, Any]:
    """获取融资融券数据（东方财富）

    返回: {
        "margin_balance": float,      # 融资余额（亿）
        "short_balance": float,       # 融券余额（亿）
        "total_balance": float,       # 两融余额（亿）
        "margin_buy": float,          # 融资买入额（亿）
        "date": str,                  # 数据日期
    }
    """
    try:
        # 东财融资融券数据接口
        url_path = (
            "/api/qt/clist/get?"
            "pn=1&pz=1&po=1&np=1&fs=m:0+t:6&fid=f3"
            "&fields=f2,f3,f12,f14,f152,f124,f125,f126,f127"
        )
        resp = _try_endpoints(url_path, timeout=20)
        if resp is None:
            # 尝试备用接口：datacenter API
            return _fetch_margin_fallback()

        # push2 API 返回的可能只是标的列表，融资融券汇总需要用另一个接口
        return _fetch_margin_fallback()
    except Exception as e:
        logger.error(f"融资融券获取失败: {e}")
        return {}


def _fetch_margin_fallback() -> dict[str, Any]:
    """融资融券数据备用接口（datacenter）"""
    try:
        # 东方财富数据中心 — 融资融券交易汇总
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPTA_WEB_MARGIN_TRADE"
            "&columns=ALL"
            "&sortColumns=TRADE_DATE&sortTypes=-1"
            "&pageSize=1&pageNumber=1"
        )
        resp = requests.get(
            url,
            headers={**HEADERS, "Referer": "https://data.eastmoney.com/rzrq/total.html"},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"融资融券 datacenter 返回: status={resp.status_code}")
            return {}
        data = resp.json()
        if data.get("success") and data.get("result") and data["result"].get("data"):
            items = data["result"]["data"]
            if items:
                item = items[0]
                result = {
                    "margin_balance": float(item.get("FIN_BALANCE", 0) or 0) / 1e8,   # 转亿
                    "short_balance": float(item.get("SALE_BALANCE", 0) or 0) / 1e8,
                    "total_balance": float(item.get("TOTAL_BALANCE", 0) or 0) / 1e8,
                    "margin_buy": float(item.get("FIN_BUY_AMT", 0) or 0) / 1e8,
                    "date": str(item.get("TRADE_DATE", "")[:10]),
                }
                logger.info(f"融资融券: 两融余额 {result['total_balance']:.0f} 亿 (date={result['date']})")
                return result
        logger.warning(f"融资融券 datacenter 返回空数据")
        return {}
    except Exception as e:
        logger.error(f"融资融券备用接口失败: {e}")
        return {}


def fetch_margin_stocks() -> list[dict[str, Any]]:
    """获取融资净买入前10个股"""
    try:
        url_path = (
            "/api/qt/clist/get?"
            "pn=1&pz=10&po=1&np=1&fs=m:0+t:6&fid=f124"
            "&fields=f2,f3,f12,f14,f124,f125"
        )
        resp = _try_endpoints(url_path)
        if resp is None:
            return []
        data = resp.json()
        result = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                result.append({
                    "code": str(item.get("f12", "")),
                    "name": str(item.get("f14", "")),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "margin_net_buy": float(item.get("f124", 0) or 0) / 1e4,  # 转万
                    "margin_balance": float(item.get("f125", 0) or 0) / 1e8,   # 转亿
                })
        logger.info(f"融资买入前10: {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"融资个股获取失败: {e}")
        return []


# ═══ 诊断工具 ═══

def run_diagnostics() -> dict[str, Any]:
    """运行东财 API 连通性诊断，返回每个端点的测试结果"""
    results = {}

    # 测试 push2 端点
    for base in EM_BASE_URLS:
        label = base.replace("https://", "")
        try:
            test_url = f"{base}/api/qt/kamt.kline/get?fields1=f1&fields2=f2&klt=1&lmt=1"
            resp = requests.get(test_url, headers=HEADERS, timeout=10)
            results[label] = {
                "status": resp.status_code,
                "len": len(resp.text) if resp.text else 0,
                "ok": resp.status_code == 200 and len(resp.text) > 50,
            }
        except requests.exceptions.Timeout:
            results[label] = {"status": "TIMEOUT", "len": 0, "ok": False}
        except requests.exceptions.ConnectionError as e:
            results[label] = {"status": f"CONN_ERR: {e}", "len": 0, "ok": False}
        except Exception as e:
            results[label] = {"status": f"ERR: {e}", "len": 0, "ok": False}

    # 测试 datacenter 端点
    try:
        test_url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPTA_WEB_MARGIN_TRADE&columns=TRADE_DATE&sortColumns=TRADE_DATE&sortTypes=-1&pageSize=1"
        )
        resp = requests.get(test_url, headers={**HEADERS, "Referer": "https://data.eastmoney.com/rzrq/total.html"}, timeout=10)
        results["datacenter-web"] = {
            "status": resp.status_code,
            "len": len(resp.text) if resp.text else 0,
            "ok": resp.status_code == 200 and len(resp.text) > 50,
        }
    except Exception as e:
        results["datacenter-web"] = {"status": f"ERR: {e}", "len": 0, "ok": False}

    return results
