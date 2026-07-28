"""HTML 安全工具 —— 将 AI 生成的文本安全嵌入 HTML"""

import html
import re


def sanitize_html(text: str) -> str:
    """
    对 LLM 输出做 HTML 实体转义，防止 XSS。
    但保留安全的 markdown 样式标记。
    """
    if not text:
        return ""

    # HTML 实体转义
    safe = html.escape(text, quote=True)

    # 将转义后的 markdown 标记还原（它们本身是安全的字符）
    # **bold** → <strong>bold</strong>
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    # 换行保留
    safe = safe.replace("\n", "<br>")

    return safe


def sanitize_dict(data: dict) -> dict:
    """递归清洗字典中的所有字符串值"""
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = sanitize_html(v)
        elif isinstance(v, dict):
            result[k] = sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = [sanitize_dict(item) if isinstance(item, dict) else sanitize_html(str(item)) if isinstance(item, str) else item for item in v]
        else:
            result[k] = v
    return result
