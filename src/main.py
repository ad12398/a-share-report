"""A 股量化报告系统 — 主入口"""

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BEIJING_TZ = timezone(timedelta(hours=8))

from src.data.calendar import is_trading_day
from src.data.collector import collect_all_data
from src.data.cleaner import clean_data_for_ai
from src.analysis.deepseek_client import generate_report, format_data_for_prompt
from src.analysis.prompts import (
    SLOT_PROMPT_MAP, SLOT_LABEL, SYSTEM_PROMPT,
)
from src.web.renderer import (
    render_report, render_index_page, render_archives_page,
    save_report_html, save_index_html, save_archives_html,
)
from src.web.indexer import add_report_to_index, load_index
from src.utils.logger import setup_logger, report_time
from src.utils.sanitizer import sanitize_html

logger = setup_logger()

VALID_SLOTS = ["0925", "1030", "1130", "1400", "1500"]


def parse_args():
    parser = argparse.ArgumentParser(description="A 股量化报告生成器")
    parser.add_argument(
        "--slot",
        type=str,
        required=False,
        choices=VALID_SLOTS,
        help="报告时段 (0925/1030/1130/1400/1500)，留空则自动判断",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行（跳过交易日和时段检查）",
    )
    return parser.parse_args()


def determine_slot(arg_slot: str | None) -> str | None:
    """确定当前应生成的报告时段"""
    if arg_slot:
        return arg_slot

    # 自动判断当前时段
    from src.data.calendar import get_current_slot
    return get_current_slot()


def run(slot: str):
    """执行单次报告生成流程（同步）"""
    logger.info(f"=== A 股量化报告生成开始 (slot={slot}) === [{report_time()}]")

    # 1. 检查交易日
    if not is_trading_day():
        logger.info("今天不是交易日，跳过")
        return None

    # 2. 数据采集
    logger.info("Step 1/5: 采集市场数据...")
    raw_data = collect_all_data(slot)

    # 2.5 数据清洗
    data = clean_data_for_ai(raw_data)

    # 3. 构建 prompt
    logger.info("Step 2/5: 构建分析 prompt...")
    prompt_builder = SLOT_PROMPT_MAP.get(slot)
    if not prompt_builder:
        logger.error(f"未知时段: {slot}")
        return None
    user_prompt = prompt_builder(data)

    # 4. 调用 DeepSeek API
    logger.info("Step 3/5: 调用 DeepSeek 生成报告...")
    report_text = generate_report(SYSTEM_PROMPT, user_prompt)

    # 5. HTML 安全转义
    safe_report = sanitize_html(report_text)

    # 6. 渲染 HTML
    logger.info("Step 4/5: 渲染 HTML 报告...")
    sector_list = data.get("sectors", [])
    gainers_list = data.get("movers", {}).get("gainers", [])
    losers_list = data.get("movers", {}).get("losers", [])

    chart_data = {}
    if sector_list and isinstance(sector_list, list) and len(sector_list) > 0:
        chart_data["sectors"] = [
            {"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)}
            for s in sector_list[:20]
        ]
        logger.info(f"DEBUG: chart_data sectors={len(chart_data['sectors'])}")
    if gainers_list and isinstance(gainers_list, list) and len(gainers_list) > 0:
        chart_data["gainers"] = [
            {"name": (g.get("name", "") + " [新股]") if (g.get("name", "").startswith("N") or g.get("name", "").startswith("C")) else g.get("name", ""),
             "change_pct": g.get("change_pct", 0)}
            for g in gainers_list[:10]
        ]
        logger.info(f"DEBUG: chart_data gainers={len(chart_data['gainers'])}")
    if losers_list and isinstance(losers_list, list) and len(losers_list) > 0:
        chart_data["losers"] = [
            {"name": (l.get("name", "") + " [新股]") if (l.get("name", "").startswith("N") or l.get("name", "").startswith("C")) else l.get("name", ""),
             "change_pct": l.get("change_pct", 0)}
            for l in losers_list[:10]
        ]
        logger.info(f"DEBUG: chart_data losers={len(chart_data['losers'])}")
    if not chart_data:
        chart_data = None
        logger.warning("DEBUG: chart_data is None (no chart data)")

    report_html = render_report(slot, safe_report, data, chart_data)
    report_path = save_report_html(report_html, slot)

    # 7. 更新搜索索引
    logger.info("Step 5/5: 更新索引和首页...")
    now = datetime.now(BEIJING_TZ)
    title = f"{now.strftime('%Y-%m-%d')} {SLOT_LABEL.get(slot, slot)}"
    updated_index = add_report_to_index(slot, title, safe_report, data)

    # 8. 重新生成首页和归档页
    index_html = render_index_page(updated_index)
    save_index_html(index_html)
    archives_html = render_archives_page(updated_index)
    save_archives_html(archives_html)

    logger.info(f"=== 报告生成完成: {report_path} === [{report_time()}]")
    return report_path


def main():
    args = parse_args()
    slot = determine_slot(args.slot)

    if not slot:
        logger.info("当前不在报告时段内，跳过")
        return

    if not args.force and slot not in VALID_SLOTS:
        logger.error(f"无效时段: {slot}")
        sys.exit(1)

    run(slot)


if __name__ == "__main__":
    main()
