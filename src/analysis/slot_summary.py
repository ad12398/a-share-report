"""时段摘要 —— 保存/加载/对比上一时段与昨日同期数据，注入 Prompt"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("a-share-report")

BEIJING_TZ = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent.parent
SUMMARY_PATH = PROJECT_ROOT / "data" / "last_slot.json"
SLOT_ORDER = ["0925", "1030", "1130", "1400", "1500"]


# ═══ 保存 ═══

def save_summary(slot: str, date_str: str, data: dict[str, Any]):
    """从 data 提取关键指标，追加保存到摘要文件"""
    now = datetime.now(BEIJING_TZ)

    # 提取指数摘要
    index_summary = {}
    for code, info in data.get("index", {}).items():
        if code == "_validation":
            continue
        index_summary[info.get("name", code)] = {
            "price": info.get("price", 0),
            "change_pct": info.get("change_pct", 0),
        }

    # 提取完整板块排名（用于统计面板热力图）
    sectors = data.get("sectors", [])
    sectors_sorted = sorted(sectors, key=lambda s: s.get("change_pct", 0), reverse=True)
    sectors_all = [{"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)} for s in sectors_sorted[:30]]

    entry = {
        "slot": slot,
        "date": date_str,
        "time": now.strftime("%H:%M"),
        "index": index_summary,
        "north_flow": data.get("north_flow", {}),
        "fund_flow": data.get("fund_flow", {}),
        "overview": {
            "up_ratio": data.get("overview", {}).get("up_ratio", 0),
            "total_amount": data.get("overview", {}).get("total_amount", 0),
        },
        "sectors": sectors_all,
        "linked_markets": data.get("linked_markets", {}),
    }

    # 读取已有文件（保留 history）
    history: dict = {}
    if SUMMARY_PATH.exists():
        try:
            existing = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
            # 只保留最近 30 天的 history
            history = existing.get("history", {})
        except Exception:
            pass

    # 写入 history
    if date_str not in history:
        history[date_str] = {}
    history[date_str][slot] = entry

    payload = {"latest": entry, "history": history}
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 写入前备份旧文件，防写入中断损坏
    if SUMMARY_PATH.exists():
        try:
            SUMMARY_PATH.rename(SUMMARY_PATH.with_suffix(".json.bak"))
        except OSError:
            pass

    SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"时段摘要已保存: {date_str} {slot}")


# ═══ 加载 ═══

def load_previous(current_slot: str, current_date: str) -> dict[str, Any] | None:
    """加载上一时段和昨日同期的摘要，返回 None 如果没有历史数据"""
    if not SUMMARY_PATH.exists():
        return None

    try:
        payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        history = payload.get("history", {})
    except Exception:
        return None

    result: dict[str, Any] = {}

    # 找上一时段
    prev_slot = _prev_slot(current_slot)
    if prev_slot and current_date in history and prev_slot in history[current_date]:
        result["prev"] = history[current_date][prev_slot]

    # 找昨日同期
    yesterday = _yesterday(current_date)
    if yesterday and yesterday in history and current_slot in history[yesterday]:
        result["yesterday"] = history[yesterday][current_slot]

    # 如果 0925 没有上一时段，找昨日收盘
    if current_slot == "0925" and "prev" not in result and yesterday and yesterday in history:
        if "1500" in history[yesterday]:
            result["prev"] = history[yesterday]["1500"]
            result["prev"]["_label"] = "昨日收盘"

    return result if result else None


def _prev_slot(slot: str) -> str | None:
    for i, s in enumerate(SLOT_ORDER):
        if s == slot and i > 0:
            return SLOT_ORDER[i - 1]
    return None


def _yesterday(date_str: str) -> str | None:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None


# ═══ 构建对比文本 ═══

def build_comparison(prev_data: dict[str, Any] | None, data: dict[str, Any]) -> str:
    """将上一时段/昨日同期摘要 + 本时段数据合并，生成 Prompt 对比文本"""
    if not prev_data:
        return ""

    lines: list[str] = []
    current = _extract_current(data)
    # 从 data 提取当前领涨板块 TOP 3（兼容旧格式 sectors_top）
    sectors = data.get("sectors", [])
    if sectors:
        curr_top3 = [s.get("name", "") for s in sorted(sectors, key=lambda x: x.get("change_pct", 0), reverse=True)[:3]]
    else:
        curr_top3 = []

    # ── 上一时段 ──
    prev = prev_data.get("prev")
    if prev:
        label = prev.get("_label", f"上一时段（{prev.get('time', '?')}）")
        lines.append(f"【对比基准】{label}")
        lines.extend(_make_comparison(prev, current, "上一时段", curr_top3))
        lines.append("")

    # ── 昨日同期 ──
    yesterday = prev_data.get("yesterday")
    if yesterday:
        label = f"昨日同期（{yesterday.get('date', '?')} {yesterday.get('time', '?')}）"
        lines.append(f"【对比基准2】{label}")
        lines.extend(_make_comparison(yesterday, current, "昨日同期", curr_top3))
        lines.append("")

    # ── 分析指令 ──
    lines.append("**对比分析要求**（必须执行）：")
    lines.append("1. 在每节分析中引用上述对比数据，注明'较上一时段'或'较昨日同期'的边际变化")
    lines.append("2. 判断当前走势属于：动能加速 / 动能衰竭 / 趋势反转")
    lines.append("3. 如有 北向反转、量价背离、板块快速轮动 等信号，重点警示")
    lines.append("4. 简明扼要一句话点睛：\"本时段核心变化是 XXX\"，放在分析开头")

    return "\n".join(lines)


def _extract_current(data: dict[str, Any]) -> dict[str, Any]:
    """从本时段 data 提取与摘要相同的对比字段"""
    index_summary = {}
    for code, info in data.get("index", {}).items():
        if code == "_validation":
            continue
        index_summary[info.get("name", code)] = {
            "price": info.get("price", 0),
            "change_pct": info.get("change_pct", 0),
        }
    return {
        "index": index_summary,
        "north_flow": data.get("north_flow", {}),
        "fund_flow": data.get("fund_flow", {}),
        "overview": {
            "up_ratio": data.get("overview", {}).get("up_ratio", 0),
            "total_amount": data.get("overview", {}).get("total_amount", 0),
        },
    }


def _make_comparison(prev: dict[str, Any], current: dict[str, Any], label: str, curr_top3: list[str]) -> list[str]:
    """生成对比行，含计算结果和异常标记"""
    lines: list[str] = []
    flags: list[str] = []

    # ── 指数对比 ──
    prev_index = prev.get("index", {})
    curr_index = current.get("index", {})
    for name, curr_info in curr_index.items():
        prev_info = prev_index.get(name, {})
        curr_pct = curr_info.get("change_pct", 0)
        prev_pct = prev_info.get("change_pct", 0)
        if prev_pct is None:
            continue
        delta = round(curr_pct - prev_pct, 2)

        # 判断动能方向
        if abs(delta) < 0.3:
            trend = "横盘延续"
        elif curr_pct >= 0 and delta > 0:
            trend = "加速上涨"
            if delta > 2:
                flags.append(f"{name} 加速上涨 {delta:.1f}pp，动能突变")
        elif curr_pct >= 0 and delta < 0:
            trend = "涨势放缓"
            if abs(delta) > 2:
                flags.append(f"{name} 涨势快速衰竭 {abs(delta):.1f}pp")
        elif curr_pct < 0 and delta < 0:
            trend = "加速下跌"
            if abs(delta) > 2:
                flags.append(f"{name} 加速下跌 {abs(delta):.1f}pp，警惕踩踏")
        else:  # curr_pct < 0 and delta > 0
            trend = "跌势减弱/反弹"
            if delta > 2:
                flags.append(f"{name} 触底反弹 {delta:.1f}pp，可能趋势反转")

        lines.append(f"  {name}：{curr_pct:+.2f}%（较{label} {delta:+.2f}pp，{trend}）")

    # ── 北向对比 ──
    prev_north = prev.get("north_flow", {}).get("net_flow", 0)
    curr_north = current.get("north_flow", {}).get("net_flow", 0)
    if prev_north and curr_north:
        north_delta = round(curr_north - prev_north, 2)
        north_sign = prev_north * curr_north
        lines.append(f"  北向资金：{curr_north:+.2f} 亿（较{label} {north_delta:+.2f} 亿）")
        if north_sign < 0:
            flags.append("⚠️ 北向资金反转（流入⇄流出切换），必须关注")
    elif curr_north:
        lines.append(f"  北向资金：{curr_north:+.2f} 亿（{label}数据暂缺）")

    # ── 成交额对比 ──
    prev_amt = prev.get("overview", {}).get("total_amount", 0)
    curr_amt = current.get("overview", {}).get("total_amount", 0)
    if prev_amt and curr_amt:
        amt_delta = round((curr_amt - prev_amt) / prev_amt * 100, 1)
        vol_label = "放量" if amt_delta > 10 else "缩量" if amt_delta < -10 else "持平"
        if abs(amt_delta) > 10:
            lines.append(f"  成交额：{curr_amt:.0f} 亿（较{label} {amt_delta:+.1f}%，{vol_label}）")
            if abs(amt_delta) > 30:
                flags.append(f"⚠️ 成交额异常{vol_label} ({amt_delta:+.1f}%)")

    # ── 板块轮动 ──
    # 兼容旧格式 sectors_top/list 和新格式 sectors/dict-list
    prev_sectors = prev.get("sectors", prev.get("sectors_top", []))
    prev_top3: set[str] = set()
    if prev_sectors and isinstance(prev_sectors[0], dict):
        prev_top3 = set(s.get("name", "") for s in prev_sectors[:3])
    elif prev_sectors:
        prev_top3 = set(str(s) for s in prev_sectors[:3])
    curr_top3_set = set(curr_top3)
    if prev_top3 and curr_top3_set:
        overlap = prev_top3 & curr_top3_set
        if len(overlap) == 0:
            flags.append(f"⚠️ 板块快速轮动：领涨板块完全替换（{', '.join(curr_top3_set)} 接替 {', '.join(prev_top3)}）")
        elif len(overlap) < 2:
            flags.append(f"板块部分轮动：领涨板块 {', '.join(overlap)} 延续，{', '.join(curr_top3_set - overlap)} 新进")

    # ── 外围联动 ──
    prev_linked = prev.get("linked_markets", {})
    curr_linked = current.get("linked_markets", {})
    if prev_linked and curr_linked:
        linked_items = []
        for key, name in [("a50", "富时A50"), ("hstech", "恒生科技"), ("cnh", "离岸人民币")]:
            p = prev_linked.get(key, {})
            c = curr_linked.get(key, {})
            if isinstance(p, dict) and isinstance(c, dict):
                prev_pct = p.get("change_pct") or 0
                curr_pct = c.get("change_pct") or 0
                if prev_pct and curr_pct:
                    delta = round(curr_pct - prev_pct, 2)
                    if abs(delta) < 0.1:
                        continue
                    # 联动方向判断
                    if name == "离岸人民币":
                        direction = "贬值加速" if delta > 0 else "升值"
                        linked_items.append(f"  {name}：{curr_pct:+.2f}%（较{label} {delta:+.2f}pp，{direction}）")
                    else:
                        linked_items.append(f"  {name}：{curr_pct:+.2f}%（较{label} {delta:+.2f}pp）")
        if linked_items:
            lines.append("")
            lines.append(f"⚓ **外围联动**（较{label}）：")
            lines.extend(linked_items)
            # 背离检测：A50 跌但上证涨
            a50_c = curr_linked.get("a50", {})
            if isinstance(a50_c, dict) and a50_c.get("change_pct", 0) < -0.5:
                curr_idx = current.get("index", {})
                上证 = curr_idx.get("上证指数", {})
                if isinstance(上证, dict) and 上证.get("change_pct", 0) > 0:
                    flags.append("⚠️ A50期指与上证背离（A50跌、上证涨），外盘不认可内盘涨势，偏空信号")

    # ── 汇总异常标记 ──
    if flags:
        lines.insert(0, "⚠️ **异常信号**：")
        for i, flag in enumerate(flags):
            lines.insert(i + 1, f"  {flag}")

    return lines

