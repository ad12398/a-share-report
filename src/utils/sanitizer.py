"""HTML 安全工具 —— 移除危险内容，保留安全标签"""

import re


def sanitize_html(text: str) -> str:
    """
    安全清洗 LLM 输出：
    - 移除 <script>、<iframe>、<object> 等危险标签
    - 移除 on* 事件属性
    - 保留安全的 HTML 标签（p, h3, ul, li, strong, br, table 等）
    """
    if not text:
        return ""

    safe = text

    # 1. 移除危险标签（包括内容）
    for tag in ["script", "iframe", "object", "embed", "style", "link", "meta"]:
        safe = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", safe, flags=re.DOTALL | re.IGNORECASE)
        safe = re.sub(rf"<{tag}\b[^>]*/?>", "", safe, flags=re.IGNORECASE)

    # 2. 移除 on* 事件属性
    safe = re.sub(r'\bon\w+\s*=\s*"[^"]*"', "", safe, flags=re.IGNORECASE)
    safe = re.sub(r"\bon\w+\s*=\s*'[^']*'", "", safe, flags=re.IGNORECASE)
    safe = re.sub(r"\bon\w+\s*=\s*\S+", "", safe, flags=re.IGNORECASE)

    # 3. 移除 javascript: 伪协议
    safe = re.sub(r'href\s*=\s*["\']\s*javascript:', 'href="', safe, flags=re.IGNORECASE)

    # 4. 移除 markdown 代码块标记（DeepSeek 有时会输出 ```html 包裹）
    safe = re.sub(r'```html\s*', '', safe)
    safe = re.sub(r'```\s*$', '', safe)

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
