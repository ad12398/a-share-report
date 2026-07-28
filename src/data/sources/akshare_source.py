"""数据源 —— 腾讯财经 API（主） + 新浪（备用），GitHub Actions 友好"""

import json
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
    """带重试的 HTTP GET"""
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=h, timeout=timeout)
            if resp.status_code == 200 and resp.text and resp.text.strip():
                return resp
            logger.warning(f"API 返回异常 (attempt {attempt+1}): status={resp.status_code}, len={len(resp.text)}")
        except Exception as e:
            logger.warning(f"API 请求失败 (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    return None


# ─── 腾讯财经 API ─────────────────────────────────────────

def _parse_tencent_quote(text: str) -> dict[str, str]:
    """解析腾讯行情响应格式: v_sh000001="1~上证指数~000001~..." """
    result = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = re.search(r'v_(\w+)="(.+)"', line)
        if m:
            sid = m.group(1)
            fields = m.group(2).split("~")
            if len(fields) >= 5:
                result[sid] = {
                    "name": fields[1],
                    "price": fields[3],
                    "change_pct": fields[5] if len(fields) > 5 else "0",
                    "change_amt": fields[4] if len(fields) > 4 else "0",
                }
    return result


def fetch_index_quotes() -> dict[str, Any]:
    """获取主要指数行情（腾讯 + 新浪备用）"""
    code_map = {
        "sh000001": "000001", "sz399001": "399001", "sz399006": "399006",
        "sh000688": "000688", "sh000300": "000300", "sh000905": "000905",
    }
    name_map = {
        "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
        "000688": "科创50", "000300": "沪深300", "000905": "中证500",
    }

    # 尝试腾讯
    try:
        codes = ",".join(code_map.keys())
        url = f"http://qt.gtimg.cn/q={codes}"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.qq.com"})
        if resp is not None:
            resp.encoding = "gbk"
            parsed = _parse_tencent_quote(resp.text)
            result = {}
            for tx_code, c in code_map.items():
                if tx_code in parsed:
                    p = parsed[tx_code]
                    result[c] = {
                        "name": name_map[c],
                        "price": float(p.get("price", 0) or 0),
                        "change_pct": float(p.get("change_pct", 0) or 0),
                        "change_amt": float(p.get("change_amt", 0) or 0),
                        "volume": 0,
                        "amount": 0,
                    }
            if result:
                logger.info(f"腾讯: 获取指数行情 {len(result)} 条")
                return result
    except Exception as e:
        logger.warning(f"腾讯指数行情失败: {e}")

    # 降级到新浪
    return _fallback_sina_index()


def _fallback_sina_index() -> dict[str, Any]:
    """新浪指数（备用）"""
    try:
        codes = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000905"
        url = f"http://hq.sinajs.cn/list={codes}"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.sina.com.cn"})
        if resp is None:
            return {}
        resp.encoding = "gbk"
        name_map = {
            "sh000001": ("000001", "上证指数"), "sz399001": ("399001", "深证成指"),
            "sz399006": ("399006", "创业板指"), "sh000688": ("000688", "科创50"),
            "sh000300": ("000300", "沪深300"), "sh000905": ("000905", "中证500"),
        }
        result = {}
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
    """获取行业板块涨跌幅（腾讯财经）"""
    try:
        # 腾讯财经行业板块接口
        url = "http://qt.gtimg.cn/q=pt_hy"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.qq.com"})
        if resp is None:
            return _fallback_sina_sectors()
        resp.encoding = "gbk"
        text = resp.text
        sectors = []
        # 腾讯行业板块格式: v_pt_hy_sz="板块号~板块名~涨跌幅~..."
        for line in text.split("\n"):
            m = re.search(r'v_pt_hy_\w+="(.+)"', line)
            if m:
                parts = m.group(1).split("~")
                if len(parts) >= 3 and parts[1]:
                    try:
                        pct = float(parts[2] or 0)
                    except ValueError:
                        pct = 0.0
                    sectors.append({"name": parts[1], "change_pct": pct, "leader": ""})
        # 按涨跌幅排序
        sectors.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        result = sectors[:30] if len(sectors) > 30 else sectors
        logger.info(f"腾讯: 获取行业板块 {len(result)} 条")
        return result
    except Exception as e:
        logger.warning(f"腾讯板块数据失败: {e}")
        return _fallback_sina_sectors()


def _fallback_sina_sectors() -> list[dict[str, Any]]:
    """新浪板块数据（备用——返回空，日后再完善）"""
    logger.warning("暂无板块备用源")
    return []


def fetch_top_movers() -> dict[str, list[dict[str, Any]]]:
    """获取涨跌幅榜（腾讯财经）"""
    result = {"gainers": [], "losers": []}
    try:
        # 腾讯 A 股全量行情（取前 2000 条够了）
        url = "http://qt.gtimg.cn/q=r_ash"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.qq.com"})
        if resp is None:
            return result
        resp.encoding = "gbk"
        stocks = []
        for line in resp.text.split("\n"):
            m = re.search(r'v_sz\w+="(.+)"', line)
            if m:
                parts = m.group(1).split("~")
                if len(parts) >= 6:
                    try:
                        pct = float(parts[6] or 0)
                    except ValueError:
                        pct = 0.0
                    stocks.append({
                        "code": parts[0],
                        "name": parts[1],
                        "price": float(parts[3] or 0),
                        "change_pct": pct,
                    })

        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        result["gainers"] = stocks[:20]
        result["losers"] = list(reversed(stocks[-20:]))
        logger.info(f"腾讯: 涨跌幅榜各 {len(result['gainers'])}/{len(result['losers'])} 条")
        return result
    except Exception as e:
        logger.error(f"涨跌榜获取失败: {e}")
        return result


def fetch_market_overview() -> dict[str, Any]:
    """获取全市场概况（从涨跌榜数据推算）"""
    try:
        url = "http://qt.gtimg.cn/q=r_ash"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.qq.com"})
        if resp is None:
            return _empty_overview()
        resp.encoding = "gbk"
        total = 0
        up = down = flat = 0
        for line in resp.text.split("\n"):
            m = re.search(r'v_sz\w+="(.+)"', line)
            if m:
                parts = m.group(1).split("~")
                if len(parts) >= 6:
                    total += 1
                    try:
                        pct = float(parts[6] or 0)
                    except ValueError:
                        pct = 0.0
                    if pct > 0:
                        up += 1
                    elif pct < 0:
                        down += 1
                    else:
                        flat += 1
        logger.info(f"腾讯: 市场概况 total={total} up={up} down={down}")
        return {
            "total": total, "up": up, "down": down, "flat": flat,
            "total_amount": 0,
            "up_ratio": round(up / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        logger.error(f"市场概况获取失败: {e}")
        return _empty_overview()


def _empty_overview() -> dict[str, Any]:
    return {"total": 0, "up": 0, "down": 0, "flat": 0, "total_amount": 0, "up_ratio": 0}
