"""akshare 数据源 —— 主力数据采集（列名自适应版）"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("a-share-report")


def _safe_col(row: pd.Series, *names: str) -> float:
    """安全获取列值：按优先级尝试多个列名，返回 float"""
    for name in names:
        val = row.get(name)
        if val is not None and pd.notna(val):
            return float(val)
    return 0.0


def _safe_str(row: pd.Series, *names: str) -> str:
    """安全获取字符串列值"""
    for name in names:
        val = row.get(name)
        if val is not None and pd.notna(val):
            return str(val)
    return ""


def _debug_columns(df: pd.DataFrame, func_name: str):
    """打印列名用于调试"""
    logger.warning(f"[{func_name}] 实际列名: {list(df.columns)}")


def fetch_index_quotes() -> dict[str, Any]:
    """获取主要指数实时行情"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        targets = {
            "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
            "000688": "科创50", "000300": "沪深300", "000905": "中证500",
        }
        # 修正深证成指代码
        if "399001" in targets:
            pass
        result = {}
        for _, row in df.iterrows():
            code = _safe_str(row, "代码", "code", "symbol")
            if code in targets:
                result[code] = {
                    "name": targets[code],
                    "price": _safe_col(row, "最新价", "最新", "close", "price"),
                    "change_pct": _safe_col(row, "涨跌幅", "涨跌幅(%)", "pct_chg", "pct_change"),
                    "change_amt": _safe_col(row, "涨跌额", "涨跌额(元)", "change", "chg"),
                    "volume": _safe_col(row, "成交量", "成交量(手)", "volume", "vol"),
                    "amount": _safe_col(row, "成交额", "成交额(元)", "amount", "amt"),
                }
        if not result:
            _debug_columns(df, "stock_zh_index_spot_em")
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
                "name": _safe_str(row, "板块名称", "板块", "name", "board_name", "industry"),
                "change_pct": _safe_col(row, "涨跌幅", "涨跌幅(%)", "最新价", "pct_chg", "change_pct"),
                "leader": _safe_str(row, "领涨股票", "领涨股", "leading", "leader"),
            })
        if not sectors:
            _debug_columns(df, "stock_board_industry_name_em")
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

        # 灵活找涨跌幅列
        pct_col = None
        for candidate in ["涨跌幅", "涨跌幅(%)", "pct_chg", "pct_change", "change_pct"]:
            if candidate in df.columns:
                pct_col = candidate
                break
        if pct_col is None:
            _debug_columns(df, "stock_zh_a_spot_em")
            raise KeyError("找不到涨跌幅列")

        df_sorted = df.sort_values(pct_col, ascending=False)
        gainers = []
        losers = []
        for _, row in df_sorted.head(20).iterrows():
            gainers.append({
                "code": _safe_str(row, "代码", "code", "symbol"),
                "name": _safe_str(row, "名称", "name", "stock_name"),
                "price": _safe_col(row, "最新价", "最新", "close", "price"),
                "change_pct": float(row.get(pct_col, 0) or 0),
            })
        for _, row in df_sorted.tail(20).iterrows():
            losers.append({
                "code": _safe_str(row, "代码", "code", "symbol"),
                "name": _safe_str(row, "名称", "name", "stock_name"),
                "price": _safe_col(row, "最新价", "最新", "close", "price"),
                "change_pct": float(row.get(pct_col, 0) or 0),
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

        # 灵活找涨跌幅列和成交额列
        pct_col = None
        for candidate in ["涨跌幅", "涨跌幅(%)", "pct_chg", "pct_change", "change_pct"]:
            if candidate in df.columns:
                pct_col = candidate
                break
        if pct_col is None:
            _debug_columns(df, "stock_zh_a_spot_em")
            raise KeyError("找不到涨跌幅列")

        amt_col = None
        for candidate in ["成交额", "成交额(元)", "amount", "amt", "turnover"]:
            if candidate in df.columns:
                amt_col = candidate
                break

        up_count = int((df[pct_col] > 0).sum())
        down_count = int((df[pct_col] < 0).sum())
        flat_count = int((df[pct_col] == 0).sum())
        total_amount = float(df[amt_col].sum()) if amt_col else 0

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
