"""HTML 渲染引擎 —— Jinja2 模板渲染"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("a-share-report")

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "src" / "web" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "reports"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def render_report(
    slot: str,
    report_text: str,
    data: dict[str, Any],
    chart_data: dict[str, Any] | None = None,
) -> str:
    """渲染单份报告页面"""
    from src.analysis.prompts import SLOT_LABEL
    template = _env.get_template("report.html")
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    return template.render(
        title=f"{date_str} {SLOT_LABEL.get(slot, slot)} - A股量化报告",
        date=date_str,
        time=now.strftime("%H:%M"),
        slot=slot,
        slot_label=SLOT_LABEL.get(slot, slot),
        report_content=report_text,
        index_data=data.get("index", {}),
        overview=data.get("overview", {}),
        chart_data=json.dumps(chart_data or {}, ensure_ascii=False),
        movers=data.get("movers", {}),
        commodities=data.get("commodities", {}),
        north_flow=data.get("north_flow", {}),
        sectors=data.get("sectors", []),
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
    today = datetime.now().strftime("%Y-%m-%d")
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
