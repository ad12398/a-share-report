"""数据清洗层 —— 物理不可能值硬过滤，异常值打标记"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def clean_data_for_ai(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    清洗采集数据：
    - 物理上不可能的值 → 过滤掉（如涨跌幅 3813%）
    - 可疑但可能的值 → 标记 _note 留给 AI 自己判断
    """
    import copy
    data = copy.deepcopy(raw_data)

    # 1. 指数数据
    if data.get("index"):
        for code, info in data["index"].items():
            if isinstance(info, dict):
                pct = info.get("change_pct", 0)
                # 指数涨跌幅 >50% 物理上不可能 → 硬过滤
                if abs(pct) > 50:
                    logger.warning(f"清洗: 指数 {info.get('name', code)} change_pct={pct} 异常，过滤")
                    info["change_pct"] = 0
                    info["change_amt"] = 0
                    info["_note"] = "涨跌幅数据异常已过滤"
                # 指数涨跌幅 10%-50%：罕见但可能，标记
                elif abs(pct) > 10:
                    info["_note"] = f"涨跌幅 {pct}% 较大，请核实"
                # 成交量缺失标记
                if info.get("amount", 0) == 0 and info.get("volume", 0) == 0:
                    info["_note"] = (info.get("_note", "") + "；成交额数据暂缺").strip("；")

    # 2. 市场概况：100% 或 0% 涨跌比标记但不删除
    overview = data.get("overview", {})
    if overview:
        up_ratio = overview.get("up_ratio", 0)
        total = overview.get("total", 0)
        if total > 100 and up_ratio in (0, 100):
            overview["_note"] = "涨跌比异常，可能采样偏差，仅供参考"
        if overview.get("total_amount", 0) == 0:
            overview["_note"] = (overview.get("_note", "") + "；成交额暂缺").strip("；")

    # 3. 板块数据：涨跌幅 >30% 物理上不可能（板块由多只股票加权，不可能超过最大个股涨幅）→ 硬过滤
    sectors = data.get("sectors", [])
    if sectors:
        clean_sectors = [s for s in sectors if isinstance(s, dict) and abs(s.get("change_pct", 0)) <= 30]
        if len(clean_sectors) < len(sectors):
            logger.warning(f"清洗: 板块数据 {len(sectors)} → {len(clean_sectors)} (过滤异常值)")
        data["sectors"] = clean_sectors

    # 4. 个股涨跌幅 >30% 物理上不可能（A股涨停板上限 30%，北交所）→ 硬过滤
    for key in ("gainers", "losers"):
        movers = data.get("movers", {}).get(key, [])
        clean_movers = [s for s in movers if isinstance(s, dict) and abs(s.get("change_pct", 0)) <= 30]
        if movers and len(clean_movers) < len(movers):
            logger.warning(f"清洗: {key} {len(movers)} → {len(clean_movers)}")
            data["movers"][key] = clean_movers

    # 5. 移除内部标记
    data.pop("_validation", None)

    return data
