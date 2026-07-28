"""akshare 数据源 —— 主力数据采集"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def fetch_index_quotes() -> dict[str, Any]:
    """获取主要指数实时行情"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        targets = {
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
            "000688": "科创50",
            "000300": "沪深300",
            "000905": "中证500",
        }
        result = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if code in targets:
                result[code] = {
                    "name": targets[code],
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "change_amt": float(row.get("涨跌额", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                }
        logger.info(f"akshare: 获取指数行情 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"akshare 指数行情获取失败: {e}")
        return {}


def fetch_sector_performance() -> list[dict[str, Any]]:
    """获取行业板块涨跌榜"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        sectors = []
        for _, row in df.head(30).iterrows():
            sectors.append({
                "name": str(row.get("板块名称", "")),
                "change_pct": float(row.get("最新价", 0)),
                "leader": str(row.get("领涨股票", "")),
            })
        logger.info(f"akshare: 获取行业板块 {len(sectors)} 条")
        return sectors
    except Exception as e:
        logger.error(f"akshare 板块数据获取失败: {e}")
        return []


def fetch_top_movers() -> dict[str, list[dict[str, Any]]]:
    """获取涨幅榜和跌幅榜前 20"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        df_sorted = df.sort_values("涨跌幅", ascending=False)
        gainers = []
        losers = []
        for _, row in df_sorted.head(20).iterrows():
            gainers.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
            })
        for _, row in df_sorted.tail(20).iterrows():
            losers.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
            })
        losers.reverse()
        logger.info(f"akshare: 涨跌幅榜各 {len(gainers)}/{len(losers)} 条")
        return {"gainers": gainers, "losers": losers}
    except Exception as e:
        logger.error(f"akshare 涨跌榜获取失败: {e}")
        return {"gainers": [], "losers": []}


def fetch_market_overview() -> dict[str, Any]:
    """获取全市场概况（上涨/下跌/平盘家数）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        up_count = int((df["涨跌幅"] > 0).sum())
        down_count = int((df["涨跌幅"] < 0).sum())
        flat_count = int((df["涨跌幅"] == 0).sum())
        total_amount = float(df["成交额"].sum()) if "成交额" in df.columns else 0
        return {
            "total": len(df),
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
            "total_amount": total_amount,
            "up_ratio": round(up_count / len(df) * 100, 1) if len(df) > 0 else 0,
        }
    except Exception as e:
        logger.error(f"akshare 市场概况获取失败: {e}")
        return {}
