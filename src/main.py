"""A 股量化报告系统 — 主入口"""

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BEIJING_TZ = timezone(timedelta(hours=8))

from src.data.calendar import is_trading_day
from src.data.collector import collect_all_data
from src.data.cleaner import clean_data_for_ai
from src.analysis.deepseek_client import generate_report, ReportGenerationError
from src.analysis.prompts import (
    SLOT_PROMPT_MAP, SLOT_LABEL, SYSTEM_PROMPT,
)
from src.analysis.slot_summary import save_summary, load_previous, build_comparison
from src.web.renderer import (
    render_report, render_index_page, render_archives_page,
    save_report_html, save_index_html, save_archives_html,
)
from src.web.docx_renderer import render_docx, save_docx
from src.web.indexer import add_report_to_index
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

    # 两市成交额已在 collector.py 采集阶段计算并注入 overview（供清洗层和统计使用）
    logger.info(f"两市总成交额: {data['overview'].get('total_amount', 0):.0f} 亿")

    # 2.7 加载上一时段 / 昨日同期摘要，构建边际对比
    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y-%m-%d")
    prev_data = load_previous(slot, date_str)
    comparison = build_comparison(prev_data, data)
    if comparison:
        logger.info(f"边际对比: 已加载 {'上一时段' if prev_data.get('prev') else ''} {'昨日同期' if prev_data.get('yesterday') else ''}")

    # 3. 构建 prompt
    logger.info("Step 2/5: 构建分析 prompt...")
    prompt_builder = SLOT_PROMPT_MAP.get(slot)
    if not prompt_builder:
        logger.error(f"未知时段: {slot}")
        return None
    user_prompt = prompt_builder(data, comparison_text=comparison)

    # 4. 调用 DeepSeek API（失败时写错误页，不发布错误文案当报告）
    logger.info("Step 3/5: 调用 DeepSeek 生成报告...")
    try:
        report_text = generate_report(SYSTEM_PROMPT, user_prompt)
    except ReportGenerationError as e:
        logger.error(f"DeepSeek 报告生成失败: {e}")
        return _save_error_report(slot, str(e), data)

    # 5. HTML 安全转义
    safe_report = sanitize_html(report_text)

    # 6. 渲染 HTML
    logger.info("Step 4/5: 渲染 HTML 报告...")
    sector_list = data.get("sectors", [])
    gainers_list = data.get("movers", {}).get("gainers", [])
    losers_list = data.get("movers", {}).get("losers", [])

    # 0925 盘前：板块/涨跌榜数据全零（未开盘），用昨日收盘数据替代
    movers_note = ""
    sector_note = ""
    if slot == "0925":
        yesterday_sectors = _load_yesterday_sectors(date_str)
        if yesterday_sectors:
            sector_list = yesterday_sectors
            sector_note = "昨日收盘数据"
            logger.info(f"0925 使用昨日板块数据: {len(sector_list)} 条")

        # 涨跌榜回填：盘前新浪返回全零或空，用昨日收盘涨跌榜
        if _movers_invalid(gainers_list) or _movers_invalid(losers_list):
            yest_movers = _load_yesterday_movers(date_str)
            if yest_movers:
                gainers_list = yest_movers.get("gainers", [])
                losers_list = yest_movers.get("losers", [])
                movers_note = "昨日收盘数据"
                # 同步更新 data["movers"]，让页面表格与图表一致
                data["movers"] = {
                    "gainers": gainers_list,
                    "losers": losers_list,
                }
                logger.info(f"0925 使用昨日涨跌榜: 涨{len(gainers_list)}/跌{len(losers_list)}")
            else:
                logger.warning("0925 涨跌榜数据无效，且昨日摘要无 movers 字段（可能摘要由旧版本代码保存），报告涨跌榜将为空")

    chart_data = {}
    if sector_list and isinstance(sector_list, list) and len(sector_list) > 0:
        chart_data["sectors"] = [
            {"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)}
            for s in sector_list[:20]
        ]
        logger.debug(f"chart_data sectors={len(chart_data['sectors'])}")
    if gainers_list and isinstance(gainers_list, list) and len(gainers_list) > 0:
        chart_data["gainers"] = [
            {"name": g.get("name", ""), "change_pct": g.get("change_pct", 0),
             "is_ipo": g.get("name", "").startswith("N") or g.get("name", "").startswith("C")}
            for g in gainers_list[:10]
        ]
        logger.debug(f"chart_data gainers={len(chart_data['gainers'])}")
    if losers_list and isinstance(losers_list, list) and len(losers_list) > 0:
        chart_data["losers"] = [
            {"name": l.get("name", ""), "change_pct": l.get("change_pct", 0),
             "is_ipo": l.get("name", "").startswith("N") or l.get("name", "").startswith("C")}
            for l in losers_list[:10]
        ]
        logger.debug(f"chart_data losers={len(chart_data['losers'])}")
    if not chart_data:
        chart_data = None
        logger.debug("chart_data is None (no chart data)")

    report_html = render_report(slot, safe_report, data, chart_data, movers_note, sector_note)
    report_path = save_report_html(report_html, slot)

    # 6.5 生成 Word 文档
    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y-%m-%d")
    try:
        slot_label = SLOT_LABEL.get(slot, slot)
        doc = render_docx(
            slot, slot_label, date_str,
            safe_report,
            data.get("index", {}),
            data.get("movers", {}),
            data.get("north_flow", {}),
            data.get("fund_flow", {}),
            data.get("macro", {}),
        )
        docx_path = save_docx(doc, slot, date_str)
        logger.info(f"Word 文档已生成: {docx_path}")
    except Exception as e:
        logger.warning(f"Word 文档生成失败（非致命）: {e}")
        docx_path = None

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

    # 9. 保存时段摘要（供下一时段 + 明日同期边际对比）
    try:
        save_summary(slot, date_str, data)
    except Exception as e:
        logger.warning(f"时段摘要保存失败（非致命）: {e}")

    logger.info(f"=== 报告生成完成: {report_path} === [{report_time()}]")
    return report_path


def _load_yesterday_sectors(today_str: str) -> list[dict[str, Any]] | None:
    """从 last_slot.json 加载昨日收盘时的板块数据（供 0925 盘前展示）。

    优先取 1500 收盘时段，缺失则取最后可用时段。
    """
    import json
    from datetime import datetime as _dt

    summary_path = Path(__file__).parent.parent / "data" / "last_slot.json"
    if not summary_path.exists():
        return None

    try:
        d = _dt.strptime(today_str, "%Y-%m-%d")
        yesterday = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        history = payload.get("history", {})
        yest_data = history.get(yesterday, {})
    except Exception:
        return None

    if not yest_data:
        return None

    # 优先 1500 → 最后可用时段
    entry = yest_data.get("1500") or list(yest_data.values())[-1]
    raw = entry.get("sectors", entry.get("sectors_top", []))
    if not raw:
        return None

    # 统一格式：list of {name, change_pct}
    result = []
    for s in raw:
        if isinstance(s, dict):
            result.append({"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)})
        elif isinstance(s, str):
            result.append({"name": s, "change_pct": 0})
    return result if result else None


def _movers_invalid(movers: list[dict[str, Any]] | None) -> bool:
    """判断涨跌榜数据是否无效（盘前新浪返回空列表或全零）"""
    if not movers:
        return True
    non_zero = [m for m in movers if m.get("change_pct", 0) != 0]
    return len(non_zero) == 0


def _load_yesterday_movers(today_str: str) -> dict[str, Any] | None:
    """从 last_slot.json 加载昨日收盘的涨跌榜（供 0925 盘前展示）。

    优先取 1500 收盘时段，缺失则取最后可用时段。
    """
    import json
    from datetime import datetime as _dt

    summary_path = Path(__file__).parent.parent / "data" / "last_slot.json"
    if not summary_path.exists():
        return None

    try:
        d = _dt.strptime(today_str, "%Y-%m-%d")
        yesterday = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        history = payload.get("history", {})
        yest_data = history.get(yesterday, {})
    except Exception:
        return None

    if not yest_data:
        return None

    # 优先 1500 → 最后可用时段
    entry = yest_data.get("1500") or list(yest_data.values())[-1]
    movers = entry.get("movers", {})
    if not movers or not (movers.get("gainers") or movers.get("losers")):
        return None

    return movers


def _save_error_report(slot: str, error_msg: str, data: dict[str, Any]) -> str:
    """DeepSeek 生成失败时保存错误页。

    与正常报告的区别（避免污染）：
    - 不生成 docx
    - 不入搜索索引
    - 不保存时段摘要（防止污染统计面板和边际对比）
    """
    error_text = (
        "<p>⚠️ 本时段 AI 分析生成失败。</p>"
        f"<p>原因：{error_msg}</p>"
        "<p>行情数据已正常采集，可在下方图表中查看。其它时段报告请访问归档页。</p>"
    )
    safe_report = sanitize_html(error_text)
    report_html = render_report(slot, safe_report, data, None)
    report_path = save_report_html(report_html, slot)
    logger.info(f"错误页已保存: {report_path}")
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
