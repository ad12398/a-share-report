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
