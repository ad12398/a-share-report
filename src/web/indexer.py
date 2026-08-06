"""搜索索引生成器 —— 构建客户端搜索用的 JSON 索引"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("a-share-report")

PROJECT_ROOT = Path(__file__).parent.parent.parent
INDEX_PATH = PROJECT_ROOT / "data" / "index.json"


def load_index() -> list[dict[str, Any]]:
    """加载已有索引"""
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("索引文件损坏，重建")
    return []


def save_index(index: list[dict[str, Any]]):
    """保存索引到文件"""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"索引已更新: {len(index)} 条记录")


def add_report_to_index(
    slot: str,
    title: str,
    report_text: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    将新报告添加到搜索索引。

    索引条目结构:
    {
        "date": "2026-07-28",
        "time": "09:25",
        "slot": "0925",
        "title": "...",
        "url": "reports/2026-07-28/0925.html",
        "summary": "报告前100字摘要...",
        "keywords": ["上证指数", "MACD", "沪股通净买入", ...]
    }
    """
    from src.analysis.prompts import SLOT_LABEL

    index = load_index()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    # 提取关键词（简单分词 + 技术指标名）
    keywords = _extract_keywords(report_text, data)

    # 摘要取前 120 字
    summary = report_text.replace("<br>", " ").replace("**", "")[:120]

    entry = {
        "date": date_str,
        "time": time_str,
        "slot": slot,
        "title": title,
        "url": f"reports/{date_str}/{slot}.html",
        "summary": summary,
        "keywords": keywords[:10],
    }

    # 如果当天的同一时段已有报告，更新而非新增
    for i, existing in enumerate(index):
        if existing.get("date") == date_str and existing.get("slot") == slot:
            index[i] = entry
            save_index(index)
            return index

    index.insert(0, entry)
    # 按日期倒序排列
    index.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
    save_index(index)
    return index


def _extract_keywords(text: str, data: dict[str, Any]) -> list[str]:
    """从报告文本和数据中提取关键词"""
    keywords = set()

    # 技术指标关键词
    indicators = [
        "MACD", "RSI", "KDJ", "BOLL", "MA", "EMA",
        "金叉", "死叉", "超买", "超卖", "背离",
        "放量", "缩量", "突破", "支撑", "阻力",
    ]
    for word in indicators:
        if word.lower() in text.lower():
            keywords.add(word)

    # 从指数数据中提取
    for code, info in data.get("index", {}).items():
        if isinstance(info, dict):
            keywords.add(info.get("name", ""))

    # 从板块数据中提取
    for sector in data.get("sectors", [])[:5]:
        if isinstance(sector, dict):
            keywords.add(sector.get("name", ""))

    # 外资流向监测
    if data.get("north_flow"):
        keywords.add("外资流向监测")

    return list(keywords)
