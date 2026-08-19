"""一次性历史数据清理脚本（2026-08-19）

背景：系统历史上有两类假数据沉积在已发布内容中——
  1. 7-29 ~ 8-5  hexin dayChart 静态缓存 → "沪股通净买入/北向资金"全部为假值
  2. 8-6 ~ 8-14  mx-source 返回 A 股板块成交额 → "北向活跃度/外资占比/沪深偏好"全部为假值
  3. 8-19 午盘    东财 fs 参数错误 → 行业板块返回风格/概念板块垃圾数据

清理对象：
  - reports/{date}/{slot}.html  删除正文中含假数据关键词的句子/<li> 项 + 顶部插入更正声明条
  - data/index.json             清理旧条目的摘要句与关键词
  - data/last_slot.json         删除历史假字段（死数据卫生）+ 8-19/1130 板块回填
  - 8-19/1130.html              单独处理：chartData.sectors 用当日 1030 真实板块替换

用法（服务器 C:\\a-share-report 下执行，需 GH_TOKEN 环境变量）：
  python -B scripts/cleanup_fake_data.py --dry-run       # 预览改动，不写盘
  python -B scripts/cleanup_fake_data.py --apply         # 应用本地改动（reports/ + data/）
  python -B scripts/cleanup_fake_data.py --push          # 推送改动后的文件到 gh-pages

--push 依赖 --apply 生成的 data/cleanup_report.json 文件清单。
"""

import argparse
import json
import logging
import re
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cleanup")

PROJECT_ROOT = Path(__file__).parent.parent

# ── 配置 ─────────────────────────────────────────────────────────────────────

# 假北向/假沪股通关键词（7-29 ~ 8-14 全时段适用）
FAKE_KEYWORDS = [
    "北向", "沪股通", "深股通",
    "外资占比", "外资偏好", "外资呈",
    "沪市占比", "沪/深占比",
]
# 8-19 午盘垃圾板块关键词（东财返回的风格/概念板块名）
SECTOR_FAKE_0819 = ["价值股", "大盘价值", "金融地产风格", "煤化工概念", "红利破净股", "红利股"]

TARGET_DATES = [
    "2026-07-29", "2026-07-30", "2026-07-31",
    "2026-08-04", "2026-08-05",
    "2026-08-06", "2026-08-07", "2026-08-10",
    "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
]

BANNER = (
    '<div style="background:#fff8e1;border:1px solid #f0c36d;border-left:4px solid #f0a030;'
    'padding:12px 16px;border-radius:6px;margin-bottom:16px;font-size:14px;line-height:1.6;">'
    '⚠️ <strong>数据更正声明（2026-08-19）</strong>：本报告部分原始数据源经核实有误'
    '（北向资金/沪股通为静态缓存数据，非真实流向；2026-08-19 午盘行业板块为错误分类数据），'
    '正文中相关错误表述已由系统自动删除。历史数据请以 '
    '<a href="/a-share-report/reports/stats.html" style="color:var(--accent-blue);">统计面板</a> 为准。'
    'Word 下载版仍含未更正数据，谨慎参考。'
    "</div>\n"
)

# last_slot.json 中需要保留的 north_flow 子键（南向/共识为真实数据）
KEEP_NORTH_KEYS = {"south_flow", "consensus_score", "confidence", "consensus"}

SENT_SPLIT = re.compile(r"(?<=[。！？；])")
BLOCK_RE = re.compile(r"(<(?:p|li)\b[^>]*>)(.*?)(</(?:p|li)>)", re.S)


# ── HTML 正文清理 ────────────────────────────────────────────────────────────

def clean_html_text(html: str, keywords: list[str]) -> tuple[str, int]:
    """删除含假数据关键词的句子/<li> 项，返回 (新html, 删除句子数)"""
    removed = 0

    def repl(m: re.Match) -> str:
        nonlocal removed
        open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
        kept_parts = []
        for part in SENT_SPLIT.split(inner):
            if any(k in part for k in keywords):
                removed += 1
                continue
            kept_parts.append(part)
        new_inner = "".join(kept_parts)
        # 清理后只剩空白/标签残留 → 整个 <p>/<li> 块删除
        if not re.sub(r"<[^>]+>", "", new_inner).strip():
            return ""
        return open_tag + new_inner + close_tag

    new_html = BLOCK_RE.sub(repl, html)
    # 变空的 <ul> 整体删除
    new_html = re.sub(r"<ul[^>]*>\s*</ul>", "", new_html)
    return new_html, removed


def insert_banner(html: str) -> str:
    marker = '<div class="container">'
    if marker in html:
        return html.replace(marker, marker + "\n" + BANNER, 1)
    logger.warning("未找到 container 标记，声明条插入失败")
    return html


def fix_1130_sectors(html: str, backup_sectors: list[dict]) -> tuple[str, bool]:
    """8-19/1130 的 chartData.sectors 用 1030 真实板块替换"""
    arr = json.dumps(
        [{"name": s.get("name", ""), "change_pct": s.get("change_pct", 0)}
         for s in backup_sectors[:20]],
        ensure_ascii=False,
    )
    new_html, n = re.subn(
        r'"sectors":\s*\[[^\]]*\]', '"sectors": ' + arr, html, count=1
    )
    return new_html, n > 0


# ── 数据文件清理 ─────────────────────────────────────────────────────────────

def clean_plain_text(text: str, keywords: list[str]) -> str:
    """纯文本按句清理（用于 index.json 摘要）"""
    return "".join(
        part for part in SENT_SPLIT.split(text)
        if not any(k in part for k in keywords)
    )


def strip_last_slot(history: dict) -> list[str]:
    """删除历史假字段 + 8-19/1130 板块回填，返回改动日志"""
    log_lines = []
    for date in TARGET_DATES:
        slots = history.get(date, {})
        for slot, entry in slots.items():
            if not isinstance(entry, dict):
                continue
            nf = entry.get("north_flow")
            if isinstance(nf, dict):
                keep = {k: v for k, v in nf.items() if k in KEEP_NORTH_KEYS}
                dropped = sorted(set(nf) - set(keep))
                if dropped:
                    log_lines.append(f"{date}/{slot}: north_flow 删除字段 {dropped}")
                entry["north_flow"] = keep
                if not keep:
                    del entry["north_flow"]
            elif "north_flow" in entry:
                log_lines.append(f"{date}/{slot}: north_flow 非字典结构 ({type(nf).__name__})，整体删除")
                del entry["north_flow"]
    # 8-19/1130 板块回填（用同日 1030 真实板块）
    h19 = history.get("2026-08-19", {})
    if "1030" in h19 and "1130" in h19 and h19["1030"].get("sectors"):
        h19["1130"]["sectors"] = h19["1030"]["sectors"]
        log_lines.append("2026-08-19/1130: sectors 用 1030 真实板块替换")
    return log_lines


# ── 文件处理 ─────────────────────────────────────────────────────────────────

def load_local_or_download(reports_dir: Path, date: str, slot: str) -> tuple[str, str]:
    """优先读服务器本地 reports/，缺失则从网站下载；报告不存在返回空串"""
    rel = f"reports/{date}/{slot}.html"
    local = reports_dir / date / f"{slot}.html"
    if local.exists():
        return local.read_text(encoding="utf-8"), rel
    url = f"https://ad12398.github.io/a-share-report/{rel}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8"), rel
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f"{rel}: 报告不存在，跳过")
        else:
            logger.error(f"无法获取 {rel}: HTTP {e.code}")
        return "", rel
    except Exception as e:
        logger.error(f"无法获取 {rel}: {e}")
        return "", rel


def process_htmls(reports_dir: Path, apply: bool) -> list[str]:
    """处理目标日期全部 5 时段 + 8-19/1130，返回变更文件相对路径列表"""
    changed: list[str] = []
    for date in TARGET_DATES:
        for slot in ["0925", "1030", "1130", "1400", "1500"]:
            html, rel = load_local_or_download(reports_dir, date, slot)
            if not html:
                continue
            new_html, removed = clean_html_text(html, FAKE_KEYWORDS)
            if removed == 0:
                logger.info(f"{rel}: 无需清理")
                continue
            new_html = insert_banner(new_html)
            if apply:
                (reports_dir / date / f"{slot}.html").write_text(new_html, encoding="utf-8")
            changed.append(rel)
            logger.info(f"{rel}: 删除 {removed} 个句子/条目")

    # 8-19/1130 特殊处理：垃圾板块关键词 + chartData 回填
    rel = "reports/2026-08-19/1130.html"
    html, _ = load_local_or_download(reports_dir, "2026-08-19", "1130")
    if html:
        new_html, removed = clean_html_text(html, SECTOR_FAKE_0819)
        backup: list[dict] = []
        last_path = PROJECT_ROOT / "data" / "last_slot.json"
        if last_path.exists():
            last_slot = json.loads(last_path.read_text(encoding="utf-8"))
            backup = last_slot.get("history", {}).get("2026-08-19", {}).get("1030", {}).get("sectors", [])
        else:
            logger.warning("本地无 data/last_slot.json，1130 chartData 回填跳过")
        new_html, fixed = fix_1130_sectors(new_html, backup)
        if removed or fixed:
            new_html = insert_banner(new_html)
            if apply:
                (reports_dir / "2026-08-19" / "1130.html").write_text(new_html, encoding="utf-8")
            changed.append(rel)
            logger.info(f"{rel}: 删除 {removed} 句 + chartData 回填 {'成功' if fixed else '失败'}")
        else:
            logger.info(f"{rel}: 无需清理")
    return changed


def process_index(apply: bool) -> bool:
    """清理 index.json 旧条目，返回是否有改动"""
    idx_path = PROJECT_ROOT / "data" / "index.json"
    if not idx_path.exists():
        logger.warning("data/index.json 不存在，跳过索引清理")
        return False
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    changed = False
    for entry in index:
        date, slot = entry.get("date", ""), entry.get("slot", "")
        kws = entry.get("keywords", [])
        if date in TARGET_DATES:
            entry["summary"] = clean_plain_text(entry.get("summary", ""), FAKE_KEYWORDS)
            entry["keywords"] = [k for k in kws if not any(f in k for f in FAKE_KEYWORDS)]
            changed = True
            logger.info(f"index {date}/{slot}: 摘要与关键词已清理")
        elif date == "2026-08-19" and slot == "1130":
            entry["summary"] = clean_plain_text(entry.get("summary", ""), SECTOR_FAKE_0819)
            entry["keywords"] = [k for k in kws if k not in SECTOR_FAKE_0819]
            changed = True
            logger.info(f"index {date}/{slot}: 垃圾板块关键词已清理")
    if changed and apply:
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


# ── 推送 ─────────────────────────────────────────────────────────────────────

def push_changes(html_files: list[str], push_index: bool) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from deploy import put_file  # 复用 deploy.py 的 GitHub Contents API 封装

    msg = "数据更正：删除错误北向/沪股通数据（2026-08-19 清理）"
    ok = fail = 0
    for rel in html_files:
        path = Path(PROJECT_ROOT / rel)
        if not path.exists():
            logger.warning(f"本地缺失，跳过推送: {rel}")
            fail += 1
            continue
        if put_file(rel, path.read_text(encoding="utf-8"), msg):
            ok += 1
        else:
            fail += 1
    if push_index:
        idx_path = PROJECT_ROOT / "data" / "index.json"
        if put_file("data/index.json", idx_path.read_text(encoding="utf-8"), msg):
            ok += 1
        else:
            fail += 1
    logger.info(f"推送完成: {ok} 成功 / {fail} 失败")


# ── 主流程 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="历史假数据清理（2026-08-19）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="预览改动，不写盘不推送")
    group.add_argument("--apply", action="store_true", help="应用本地改动（reports/ + data/）")
    group.add_argument("--push", action="store_true", help="推送 apply 生成的改动到 gh-pages")
    args = parser.parse_args()

    if args.push:
        report_path = PROJECT_ROOT / "data" / "cleanup_report.json"
        if not report_path.exists():
            logger.error("未找到 data/cleanup_report.json，请先执行 --apply")
            sys.exit(1)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        push_changes(report.get("html_files", []), report.get("index_changed", False))
        return

    reports_dir = PROJECT_ROOT / "reports"
    apply = args.apply

    html_files = process_htmls(reports_dir, apply)
    index_changed = process_index(apply)

    # last_slot.json：加载一次、变更一次、写盘一次（避免重复加载丢失变更）
    last_path = PROJECT_ROOT / "data" / "last_slot.json"
    last = json.loads(last_path.read_text(encoding="utf-8"))
    slot_log = strip_last_slot(last.setdefault("history", {}))
    for line in slot_log:
        logger.info(f"last_slot {line}")
    if apply and slot_log:
        last_path.write_text(json.dumps(last, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"HTML 文件变更: {len(html_files)} 个")
    logger.info(f"index.json 变更: {index_changed}")

    if apply:
        report = {"html_files": html_files, "index_changed": index_changed, "last_slot_changed": bool(slot_log)}
        (PROJECT_ROOT / "data" / "cleanup_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("已写入 data/cleanup_report.json，可用 --push 推送到 gh-pages")
    else:
        logger.info("dry-run 完成，未写盘")


if __name__ == "__main__":
    main()
