"""数据清洗层 —— 在传给 DeepSeek 之前过滤脏数据"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def clean_data_for_ai(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    清洗采集数据，移除明显错误的值，确保 AI 看到的数据合理。
    不会修改原始 raw_data。
    """
    import copy
    data = copy.deepcopy(raw_data)

    # 1. 清洗指数数据
    if data.get("index"):
        for code, info in data["index"].items():
            if isinstance(info, dict):
                pct = info.get("change_pct", 0)
                # 涨跌幅超过 20% 的指数数据显然错误（A股指数涨跌停限制）
                if abs(pct) > 20:
                    logger.warning(f"清洗: 指数 {info.get('name', code)} change_pct={pct} 异常，重置为 0")
                    info["change_pct"] = 0
                    info["change_amt"] = 0
                # 成交量为 0 则标记
                if info.get("amount", 0) == 0 and info.get("volume", 0) == 0:
                    info["_note"] = "成交额数据暂缺"

    # 2. 清洗市场概况
    overview = data.get("overview", {})
    if overview:
        up_ratio = overview.get("up_ratio", 0)
        total = overview.get("total", 0)
        # 涨跌比 100% 或 0% 且总数 > 100 则明显异常
        if total > 100 and up_ratio in (0, 100):
            logger.warning(f"清洗: 涨跌比 up_ratio={up_ratio}% 异常 (total={total})，标记为估算值")
            overview["_note"] = "涨跌比数据可能不准确，仅供参考"
        # 标记成交额缺失
        if overview.get("total_amount", 0) == 0:
            overview["_note"] = overview.get("_note", "") + "；成交额数据暂缺"

    # 3. 清洗板块数据——板块涨跌幅超过 ±15% 视为错误
    sectors = data.get("sectors", [])
    if sectors:
        clean_sectors = []
        for s in sectors:
            if isinstance(s, dict):
                pct = s.get("change_pct", 0)
                if abs(pct) < 15:  # 只保留合理值
                    clean_sectors.append(s)
        if len(clean_sectors) < len(sectors):
            logger.warning(f"清洗: 板块数据 {len(sectors)} → {len(clean_sectors)} (过滤异常值)")
        data["sectors"] = clean_sectors

    # 4. 股票涨跌幅不应超过 30%（A股涨停板上限，含北交所）
    for key in ("gainers", "losers"):
        movers = data.get("movers", {}).get(key, [])
        clean_movers = []
        for s in movers:
            if isinstance(s, dict) and abs(s.get("change_pct", 0)) <= 30:
                clean_movers.append(s)
        if movers and len(clean_movers) < len(movers):
            data["movers"][key] = clean_movers

    # 5. 移除所有内部标记字段
    data.pop("_validation", None)

    return data
