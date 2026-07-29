"""数据清洗层 —— 原则：能标记就不删除，仅过滤物理不可能值"""

import logging
from typing import Any

logger = logging.getLogger("a-share-report")


def clean_data_for_ai(raw_data: dict[str, Any]) -> dict[str, Any]:
    """清洗数据，标记 > 删除"""
    import copy
    data = copy.deepcopy(raw_data)

    _clean_index(data)
    _clean_overview(data)
    _clean_sectors(data)
    _clean_movers(data)
    _clean_commodities(data)

    data.pop("_validation", None)
    return data


# ─── 指数 ────────────────────────────────────────────────

def _clean_index(data: dict[str, Any]):
    if not data.get("index"):
        return
    for code, info in data["index"].items():
        if not isinstance(info, dict):
            continue
        notes = []
        pct = info.get("change_pct", 0)

        # 涨跌幅 >50%：标记不删——如果真发生了极端行情 AI 自己判断
        if abs(pct) > 50:
            logger.warning(f"清洗: 指数 {info.get('name', code)} change_pct={pct} 极端值，标记")
            notes.append(f"涨跌幅 {pct}% 疑似异常，请交叉验证")

        # 开/高/低全为 0：标记
        if info.get("open", 0) == 0 and info.get("high", 0) == 0 and info.get("low", 0) == 0:
            notes.append("开盘/最高/最低数据暂缺，日内走势分析受限")

        # 成交量/额缺失
        if info.get("amount", 0) == 0 and info.get("volume", 0) == 0:
            notes.append("成交额/量数据暂缺")

        if notes:
            info["_note"] = "；".join(notes)


# ─── 市场概况 ────────────────────────────────────────────

def _clean_overview(data: dict[str, Any]):
    overview = data.get("overview", {})
    if not overview:
        return
    notes = []
    up_ratio = overview.get("up_ratio", 0)
    total = overview.get("total", 0)

    if total > 100 and up_ratio in (0, 100):
        notes.append("涨跌比极端（0%或100%），可能采样偏差")
    if overview.get("total_amount", 0) == 0:
        notes.append("成交额暂缺")

    # 涨停/跌停计数为 0 且 total > 100：标记（交易日不可能没有涨跌停）
    if total > 100 and overview.get("limit_up", 0) == 0 and overview.get("limit_down", 0) == 0:
        notes.append("涨跌停计数可能不完整")

    if notes:
        overview["_note"] = "；".join(notes)


# ─── 板块 ────────────────────────────────────────────────

def _clean_sectors(data: dict[str, Any]):
    sectors = data.get("sectors", [])
    if not sectors:
        return
    # 板块涨跌幅 >30% 硬过滤（加权指数不可能超过单日最大个股涨跌幅 30%）
    clean = [s for s in sectors if isinstance(s, dict) and abs(s.get("change_pct", 0)) <= 30]
    if len(clean) < len(sectors):
        logger.warning(f"清洗: 板块 {len(sectors)} → {len(clean)} (过滤 >30% 异常值)")
    data["sectors"] = clean


# ─── 个股涨跌榜 ──────────────────────────────────────────

def _clean_movers(data: dict[str, Any]):
    for key in ("gainers", "losers"):
        movers = data.get("movers", {}).get(key, [])
        if not movers:
            continue
        clean = []
        for s in movers:
            if not isinstance(s, dict):
                continue
            pct = s.get("change_pct", 0)
            # 个股涨跌幅 >30% 硬过滤（A 股涨停板上限 30%，北交所）
            if abs(pct) > 30:
                logger.warning(f"清洗: {key} {s.get('name', '?')} change_pct={pct} >30%，过滤")
                continue
            # PE/PB 为负或异常大 → 标记不删
            pe = s.get("pe", 0)
            pb = s.get("pb", 0)
            if pe and pe < 0:
                s["_pe_note"] = "PE为负"
            if pb and pb > 50:
                s["_pb_note"] = "PB异常高"
            clean.append(s)
        data["movers"][key] = clean


# ─── 商品/汇率/全球指数 ──────────────────────────────────

def _clean_commodities(data: dict[str, Any]):
    commodities = data.get("commodities", {})
    if not commodities:
        return
    for name, item in list(commodities.items()):
        if not isinstance(item, dict):
            continue
        notes = []
        pct = item.get("change_pct", 0)
        price = item.get("price", 0)

        # 价格为 0 → 删除整条
        if price == 0:
            logger.warning(f"清洗: 商品 {name} 价格为 0，移除")
            del commodities[name]
            continue

        # 涨跌幅异常大（商品单日 >15% 极其罕见，如原油暴跌 2020 年才-30%）
        if abs(pct) > 15:
            notes.append(f"涨跌幅 {pct}% 极大，请核实是否为真实行情")

        # 美股指数涨跌幅区分对待（美股无涨跌停，但单日 >10% 罕见）
        if name in ("道琼斯", "标普500指数", "纳斯达克", "标普指数"):
            if abs(pct) > 10:
                notes.append(f"{name} 涨跌幅 {pct}% 异常，请核实")
        # 商品
        elif "黄金" in name or "原油" in name or "铜" in name:
            if abs(pct) > 8:
                notes.append(f"{name} 涨跌幅 {pct}% 较大")
            if abs(pct) > 20:
                notes.append(f"{name} 涨跌幅 {pct}% 极可能是数据错误")

        if notes:
            item["_note"] = "；".join(notes)
