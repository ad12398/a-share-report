"""东方财富数据源 —— 北向资金 & 龙虎榜"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def fetch_north_flow() -> dict[str, Any]:
    """获取北向资金流向"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            return {
                "date": str(latest.get("date", "")),
                "net_flow": float(latest.get("value", 0)),
            }
        return {}
    except Exception as e:
        logger.error(f"北向资金获取失败: {e}")
        return {}


def fetch_dragon_tiger() -> list[dict[str, Any]]:
    """获取今日龙虎榜"""
    try:
        import akshare as ak
        df = ak.stock_sina_lhb_detail_daily(trade_date="")
        if df is not None and len(df) > 0:
            result = []
            for _, row in df.head(20).iterrows():
                result.append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "reason": str(row.get("上榜原因", "")),
                })
            logger.info(f"龙虎榜获取 {len(result)} 条")
            return result
        return []
    except Exception as e:
        logger.error(f"龙虎榜获取失败: {e}")
        return []
