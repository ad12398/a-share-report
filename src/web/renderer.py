"""HTML 渲染引擎 —— Jinja2 模板渲染"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("a-share-report")

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "src" / "web" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "reports"

BEIJING_TZ = timezone(timedelta(hours=8))

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def _beijing_now() -> datetime:
    """返回北京时间"""
    return datetime.now(BEIJING_TZ)


def _safe_script_json(obj: Any) -> str:
    """将 Python 对象序列化为 JSON，并转义 </ 防止 XSS"""
    raw = json.dumps(obj, ensure_ascii=False)
    # 转义 </ 防止破坏 <script> 标签（如低概率的股票名含此序列）
    return raw.replace("</", "<\\/")


def render_report(
    slot: str,
    report_text: str,
    data: dict[str, Any],
    chart_data: dict[str, Any] | None = None,
) -> str:
    """渲染单份报告页面"""
    from src.analysis.prompts import SLOT_LABEL
    template = _env.get_template("report.html")
    now = _beijing_now()
    date_str = now.strftime("%Y-%m-%d")

    # 计算两市总成交额（仅上证+深证，避免子指数重复）
    total_amount = 0.0
    idx_map = data.get("index", {})
    for code, idx_val in idx_map.items():
        if code in ("000001", "399001") and isinstance(idx_val, dict):
            total_amount += float(idx_val.get("amount", 0)) / 1e4  # 万 → 亿

    return template.render(
        title=f"{date_str} {SLOT_LABEL.get(slot, slot)} - A股量化报告",
        date=date_str,
        time=now.strftime("%H:%M"),
        slot=slot,
        slot_label=SLOT_LABEL.get(slot, slot),
        report_content=report_text,
        index_data=idx_map,
        overview=data.get("overview", {}),
        chart_data=_safe_script_json(chart_data or {}),
        movers=data.get("movers", {}),
        dragon_tiger=data.get("dragon_tiger", []),
        commodities=data.get("commodities", {}),
        north_flow=data.get("north_flow", {}),
        linked_markets=data.get("linked_markets", {}),
        sectors=data.get("sectors", []),
        macro=data.get("macro", {}),
        total_amount=f"{total_amount:.0f}" if total_amount > 0 else "",
    )


def render_index_page(reports_index: list[dict[str, Any]]) -> str:
    """渲染首页（最新报告 + 搜索）"""
    template = _env.get_template("index.html")
    return template.render(
        reports=reports_index,
        latest=reports_index[0] if reports_index else None,
    )


def render_archives_page(reports_index: list[dict[str, Any]]) -> str:
    """渲染归档浏览页"""
    template = _env.get_template("archives.html")
    # 按月份分组
    by_month: dict[str, list] = {}
    for r in reports_index:
        month = r.get("date", "")[:7]
        by_month.setdefault(month, []).append(r)
    return template.render(
        by_month=by_month,
        total_reports=len(reports_index),
    )


def save_report_html(html: str, slot: str) -> str:
    """保存报告 HTML 到文件，返回相对路径"""
    today = _beijing_now().strftime("%Y-%m-%d")
    report_dir = OUTPUT_DIR / today
    report_dir.mkdir(parents=True, exist_ok=True)

    filepath = report_dir / f"{slot}.html"
    filepath.write_text(html, encoding="utf-8")
    logger.info(f"报告已保存: {filepath}")
    return str(filepath.relative_to(PROJECT_ROOT))


def save_index_html(html: str) -> str:
    """保存首页 HTML"""
    filepath = OUTPUT_DIR / "index.html"
    filepath.write_text(html, encoding="utf-8")
    return str(filepath.relative_to(PROJECT_ROOT))


def save_archives_html(html: str) -> str:
    """保存归档页 HTML"""
    filepath = OUTPUT_DIR / "archives.html"
    filepath.write_text(html, encoding="utf-8")
    return str(filepath.relative_to(PROJECT_ROOT))


def build_stats_data() -> dict[str, Any]:
    """从 last_slot.json 构建统计面板数据。

    返回模板所需的数据结构，包含 KPI、图表数据、数据量标记。
    仅使用每日 1500 收盘时段的数据以确保一致性。
    """
    summary_path = PROJECT_ROOT / "data" / "last_slot.json"
    if not summary_path.exists():
        return {"low_data": True, "total_days": 0, "total_reports": 0}

    try:
        raw = json.loads(summary_path.read_text(encoding="utf-8"))
        history = raw.get("history", {})
    except Exception:
        logger.warning("统计面板: last_slot.json 读取失败")
        return {"low_data": True, "total_days": 0, "total_reports": 0}

    if not history:
        return {"low_data": True, "total_days": 0, "total_reports": 0}

    # 每日取 1500 收盘时段，缺失则取当天最后可用时段
    daily: dict[str, dict] = {}
    total_reports = 0
    for date_str, slots in history.items():
        slot_entries = list(slots.items())
        total_reports += len(slot_entries)
        close_entry = slots.get("1500")
        if close_entry:
            daily[date_str] = close_entry
        elif slot_entries:
            # 取最后可用时段
            slot_entries.sort()
            daily[date_str] = slot_entries[-1][1]

    sorted_dates = sorted(daily.keys())
    total_days = len(sorted_dates)

    if total_days == 0:
        return {"low_data": True, "total_days": 0, "total_reports": total_reports}

    # ── KPI 计算 ──
    up_ratios = []
    north_turnovers = []   # 北向活跃度（成交总额）
    north_participations = []  # 外资占比
    south_flows = []       # 南向净买入
    amounts = []
    for d in sorted_dates:
        entry = daily[d]
        ov = entry.get("overview", {})
        nf = entry.get("north_flow", {})
        if ov.get("up_ratio"):
            up_ratios.append(ov["up_ratio"])
        if nf.get("turnover_total"):
            north_turnovers.append(nf["turnover_total"])
        if nf.get("participation_pct"):
            north_participations.append(nf["participation_pct"])
        south = nf.get("south_flow", {}) or {}
        if south.get("south_net"):
            south_flows.append(south["south_net"])
        if ov.get("total_amount"):
            amounts.append(ov["total_amount"])

    avg_up_ratio = round(sum(up_ratios) / len(up_ratios), 1) if up_ratios else 0
    avg_turnover = round(sum(north_turnovers) / len(north_turnovers), 0) if north_turnovers else 0
    avg_amount = round(sum(amounts) / len(amounts), 0) if amounts else 0
    avg_participation = round(sum(north_participations) / len(north_participations), 1) if north_participations else 0

    # ── 图表数据 ──
    chart_dates: list[str] = []
    chart_up_ratio: list[float] = []
    chart_north_turnover: list[float] = []
    chart_north_participation: list[float] = []
    chart_south_flow: list[float] = []
    chart_amount: list[float] = []

    # 指数累计收益计算
    index_names = ["上证指数", "深证成指", "创业板指", "科创50"]
    index_daily: dict[str, list[float]] = {n: [] for n in index_names}
    index_cum: dict[str, list[float]] = {n: [] for n in index_names}

    for d in sorted_dates:
        entry = daily[d]
        chart_dates.append(d)
        chart_up_ratio.append(entry.get("overview", {}).get("up_ratio", 0) or 0)
        chart_north_turnover.append(entry.get("north_flow", {}).get("turnover_total", 0) or 0)
        chart_north_participation.append(entry.get("north_flow", {}).get("participation_pct", 0) or 0)
        chart_south_flow.append((entry.get("north_flow", {}).get("south_flow", {}) or {}).get("south_net", 0) or 0)
        chart_amount.append(entry.get("overview", {}).get("total_amount", 0) or 0)

        idx_data = entry.get("index", {})
        for name in index_names:
            pct = idx_data.get(name, {}).get("change_pct", 0) or 0
            index_daily[name].append(pct)

    # 计算累计收益率
    for name in index_names:
        cum = 1.0
        result = []
        for pct in index_daily[name]:
            cum *= (1 + pct / 100)
            result.append(round((cum - 1) * 100, 2))
        index_cum[name] = result

    # ── 板块热力图数据 ──
    sector_names: list[str] = []
    sector_data: dict[str, dict[str, float]] = {}  # {sector_name: {date: change_pct}}
    for d in sorted_dates:
        entry = daily[d]
        sectors = entry.get("sectors", entry.get("sectors_top", []))
        for s in sectors:
            if isinstance(s, dict):
                name = s.get("name", "")
                pct = s.get("change_pct", 0)
            else:
                name = str(s)
                pct = 0
            if name:
                if name not in sector_data:
                    sector_data[name] = {}
                sector_data[name][d] = pct

    # 取出现频次最高的 30 个板块
    sector_freq = sorted(sector_data.items(), key=lambda x: len(x[1]), reverse=True)
    sector_names = [s[0] for s in sector_freq[:30]]

    sector_matrix: list[list[float | None]] = []
    for name in sector_names:
        row = [sector_data[name].get(d, None) for d in sorted_dates]
        sector_matrix.append(row)

    chart_json = {
        "dates": chart_dates,
        "up_ratio": chart_up_ratio,
        "north_turnover": chart_north_turnover,
        "north_participation": chart_north_participation,
        "south_flow": chart_south_flow,
        "amount": chart_amount,
        "index_returns": index_cum,
        "sector_names": sector_names,
        "sector_dates": sorted_dates,
        "sector_data": sector_matrix,
    }

    return {
        "low_data": total_days < 3,
        "total_days": total_days,
        "total_reports": total_reports,
        "avg_up_ratio": avg_up_ratio,
        "avg_turnover": avg_turnover,
        "avg_turnover_str": f"{avg_turnover:.0f}",
        "avg_participation": avg_participation,
        "avg_participation_str": f"{avg_participation:.1f}",
        "avg_amount": avg_amount,
        "avg_amount_str": f"{avg_amount:.0f}",
        "first_date": sorted_dates[0],
        "last_date": sorted_dates[-1],
        "chart_json": _safe_script_json(chart_json),
    }


def render_stats_page() -> str:
    """渲染统计面板页面"""
    template = _env.get_template("stats.html")
    data = build_stats_data()
    return template.render(**data)


def save_stats_html(html: str) -> str:
    """保存统计面板 HTML"""
    filepath = OUTPUT_DIR / "stats.html"
    filepath.write_text(html, encoding="utf-8")
    return str(filepath.relative_to(PROJECT_ROOT))
