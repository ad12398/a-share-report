"""数据源 —— 腾讯（指数）+ 新浪（股票）+ 东财（板块），GitHub Actions 优化"""

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


def _safe_get(url: str, timeout: int = 20, max_retries: int = 3, extra_headers: dict | None = None) -> requests.Response | None:
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=h, timeout=timeout)
            if resp.status_code == 200 and resp.text and resp.text.strip():
                return resp
            logger.warning(f"API 返回异常 (attempt {attempt+1}): status={resp.status_code}")
            # 502/503 多等一会
            if resp.status_code in (502, 503):
                time.sleep(5)
        except Exception as e:
            logger.warning(f"API 请求失败 (attempt {attempt+1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))
    return None


# ═══ 指数行情（腾讯 + 新浪备用）══════════════════════════════════════

def fetch_index_quotes() -> dict[str, Any]:
    code_map = {
        "sh000001": "000001", "sz399001": "399001", "sz399006": "399006",
        "sh000688": "000688", "sh000300": "000300", "sh000905": "000905",
    }
    name_map = {
        "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
        "000688": "科创50", "000300": "沪深300", "000905": "中证500",
    }

    # 腾讯优先
    try:
        codes = ",".join(code_map.keys())
        url = f"http://qt.gtimg.cn/q={codes}"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.qq.com"})
        if resp:
            resp.encoding = "gbk"
            result = {}
            for line in resp.text.strip().split("\n"):
                m = re.search(r'v_(\w+)="(.+)"', line)
                if m:
                    sid = m.group(1)
                    fields = m.group(2).split("~")
                    if sid in code_map and len(fields) >= 6:
                        price = float(fields[3] or 0)
                        prev_close = float(fields[4] or 0)
                        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                        change_amt = round(price - prev_close, 2)
                        result[code_map[sid]] = {
                            "name": name_map[code_map[sid]],
                            "price": price,
                            "open": float(fields[5] or 0) if len(fields) > 5 else 0,
                            "high": 0,  # 腾讯指数无日内高低，用新浪补充
                            "low": 0,
                            "change_pct": change_pct,
                            "change_amt": change_amt,
                            "volume": float(fields[6] or 0) if len(fields) > 6 else 0,
                            "amount": float(fields[7] or 0) if len(fields) > 7 else 0,
                        }
            if result:
                logger.info(f"腾讯: 获取指数行情 {len(result)} 条")
                return result
    except Exception as e:
        logger.warning(f"腾讯指数失败: {e}")

    return _sina_index_fallback()


def _sina_index_fallback() -> dict[str, Any]:
    try:
        codes = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000905"
        url = f"http://hq.sinajs.cn/list={codes}"
        resp = _safe_get(url, extra_headers={"Referer": "https://finance.sina.com.cn"})
        if not resp:
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
                    # Sina: [0]名 [1]今开 [2]昨收 [3]当前 [4]最高 [5]最低
                    price = float(vals[3] or 0) if len(vals) > 3 else 0
                    prev_close = float(vals[2] or 0) if len(vals) > 2 else 0
                    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                    result[code] = {
                        "name": cname,
                        "price": price,
                        "open": float(vals[1] or 0) if len(vals) > 1 else 0,
                        "high": float(vals[4] or 0) if len(vals) > 4 else 0,
                        "low": float(vals[5] or 0) if len(vals) > 5 else 0,
                        "change_pct": change_pct,
                        "change_amt": round(price - prev_close, 2),
                        "volume": float(vals[8] or 0) if len(vals) > 8 else 0,
                        "amount": float(vals[9] or 0) if len(vals) > 9 else 0,
                    }
        logger.info(f"新浪: 获取指数行情 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"新浪指数也失败: {e}")
        return {}


# ═══ 板块涨跌榜（东财 → 新浪备用） ═══

def fetch_sector_performance() -> list[dict[str, Any]]:
    # 先试东方财富
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=30&po=1&np=1&fs=m:90+t:3&fid=f3"
            "&fields=f2,f3,f14,f128"
        )
        resp = _safe_get(url, max_retries=1)  # 只试 1 次，快速降级
        if resp:
            data = resp.json()
            if data.get("data") and data["data"].get("diff"):
                sectors = [{"name": str(item.get("f14", "")), "change_pct": float(item.get("f3", 0) or 0), "leader": str(item.get("f128", ""))} for item in data["data"]["diff"]]
                if sectors:
                    logger.info(f"东财: 获取行业板块 {len(sectors)} 条")
                    return sectors
    except Exception:
        pass

    # 降级到新浪
    return _sina_sectors_fallback()


def _sina_sectors_fallback() -> list[dict[str, Any]]:
    """新浪行业板块数据"""
    try:
        url = "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
        resp = _safe_get(url, extra_headers={"Referer": "https://vip.stock.finance.sina.com.cn"})
        if not resp:
            return []
        text = resp.text
        json_start = text.find("{")
        if json_start == -1:
            return []
        data = json.loads(text[json_start:])
        sectors = []
        for value in data.values():
            fields = value.split(",")
            if len(fields) >= 6:
                try:
                    pct = float(fields[5] or 0)
                except ValueError:
                    pct = 0.0
                sectors.append({
                    "name": fields[1],
                    "change_pct": pct,
                    "leader": "",
                })
        sectors.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        result = sectors[:30]
        logger.info(f"新浪: 获取行业板块 {len(result)} 条")
        return result
    except Exception as e:
        logger.warning(f"新浪板块失败: {e}")
        return []


# ═══ 涨跌幅榜（新浪 API） ═══

def fetch_top_movers() -> dict[str, list[dict[str, Any]]]:
    result = {"gainers": [], "losers": []}
    try:
        # 新浪 A 股涨幅榜（JSON 接口）
        url = (
            "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodeData?page=1&num=20&sort=changepercent"
            "&asc=0&node=hs_a&symbol=&_s_r_a=auto"
        )
        resp = _safe_get(url, extra_headers={"Referer": "https://vip.stock.finance.sina.com.cn"})
        if resp:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    result["gainers"].append({
                        "code": str(item.get("symbol", "")),
                        "name": str(item.get("name", "")),
                        "price": float(item.get("trade", 0) or 0),
                        "change_pct": float(item.get("changepercent", 0) or 0),
                        "pe": float(item.get("per", 0) or 0),
                        "pb": float(item.get("pb", 0) or 0),
                    })

        # 跌幅榜
        url = (
            "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodeData?page=1&num=20&sort=changepercent"
            "&asc=1&node=hs_a&symbol=&_s_r_a=auto"
        )
        resp = _safe_get(url, extra_headers={"Referer": "https://vip.stock.finance.sina.com.cn"})
        if resp:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    result["losers"].append({
                        "code": str(item.get("symbol", "")),
                        "name": str(item.get("name", "")),
                        "price": float(item.get("trade", 0) or 0),
                        "change_pct": float(item.get("changepercent", 0) or 0),
                        "pe": float(item.get("per", 0) or 0),
                        "pb": float(item.get("pb", 0) or 0),
                    })

        logger.info(f"新浪: 涨跌幅榜各 {len(result['gainers'])}/{len(result['losers'])} 条")
        return result
    except Exception as e:
        logger.error(f"涨跌榜获取失败: {e}")
        return result


# ═══ 市场概况 ═══

def fetch_market_overview() -> dict[str, Any]:
    """
    按股票代码顺序采样统计市场涨跌比。
    用 sort=symbol 排序可获得代表性样本，而非全是涨/跌的极端值。
    """
    try:
        total = up = down = flat = limit_up = limit_down = 0
        turnover_sum = 0.0
        base_url = (
            "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodeData?node=hs_a&symbol=&_s_r_a=auto&num=100&sort=symbol"
        )

        for page in range(1, 11):  # 10页 × 100 = 1000只采样
            url = f"{base_url}&page={page}"
            resp = _safe_get(url, extra_headers={"Referer": "https://vip.stock.finance.sina.com.cn"}, max_retries=1)
            if not resp:
                break
            batch = resp.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break
            for item in batch:
                pct = float(item.get("changepercent", 0) or 0)
                total += 1
                if pct > 0: up += 1
                elif pct < 0: down += 1
                else: flat += 1
                if pct >= 9.5: limit_up += 1
                if pct <= -9.5: limit_down += 1
                # 换手率累加
                tor = float(item.get("turnoverratio", 0) or 0)
                turnover_sum += tor

        avg_turnover = round(turnover_sum / total, 2) if total > 0 else 0
        logger.info(f"新浪: 市场概况 sampled total={total} up={up} down={down} 涨停≈{limit_up} 跌停≈{limit_down} 均换手={avg_turnover}%")
        return {
            "total": total, "up": up, "down": down, "flat": flat,
            "limit_up": limit_up, "limit_down": limit_down,
            "total_amount": 0, "avg_turnover": avg_turnover,
            "up_ratio": round(up / total * 100, 1) if total > 0 else 0,
        }
    except Exception as e:
        logger.error(f"市场概况获取失败: {e}")
        return _empty_overview()


def _empty_overview() -> dict[str, Any]:
    return {"total": 0, "up": 0, "down": 0, "flat": 0, "total_amount": 0, "up_ratio": 0, "limit_up": 0, "limit_down": 0, "avg_turnover": 0}
