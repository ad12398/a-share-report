"""宏观数据加载器 —— 从本地 JSON 文件读取"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("a-share-report")

_MACRO_PATH = Path(__file__).parent.parent.parent / "data" / "macro_data.json"


def load_macro_data() -> dict[str, Any]:
    """加载宏观数据文件，返回 dict。文件不存在则返回空。"""
    try:
        if not _MACRO_PATH.exists():
            logger.warning("宏观数据文件不存在: macro_data.json")
            return {}
        with open(_MACRO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"宏观数据已加载 (updated={data.get('_updated', '?')})")
        return data
    except Exception as e:
        logger.error(f"宏观数据加载失败: {e}")
        return {}
