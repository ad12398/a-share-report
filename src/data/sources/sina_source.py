"""新浪财经数据源 —— 备用数据"""

import logging
import re
from typing import Any

import requests

logger = logging.getLogger("a-share-report")


def _sina_code(market_code: str) -> str:
    """转换代码格式: '000001' → 'sh000001' or 'sz000001'"""
    code = market_code.strip()
    if code.startswith("6") or code.startswith("000"):
        return f"sh{code}"
    return f"sz{code}"


def fetch_index_quotes() -> dict[str, Any]:
    """从新浪获取指数行情（备用）"""
    try:
        codes = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300", "sh000905"]
        url = f"http://hq.sinajs.cn/list={','.join(codes)}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "gbk"
        text = resp.text
        result = {}
        name_map = {
            "sh000001": "000001", "sz399001": "399001", "sz399006": "399006",
            "sh000688": "000688", "sh000300": "000300", "sh000905": "000905",
        }
        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            match = re.search(r'hq_str_(\w+)="(.+)"', line)
            if match:
                sid = match.group(1)
                data = match.group(2).split(",")
                if len(data) >= 4:
                    # Sina 格式: [0]名字 [1]今开 [2]昨收 [3]当前价
                    price = float(data[3]) if len(data) > 3 else 0
                    prev_close = float(data[2]) if len(data) > 2 else 0
                    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                    result[name_map.get(sid, sid)] = {
                        "name": data[0] if len(data) > 0 else "",
                        "price": price,
                        "change_pct": change_pct,
                    }
        logger.info(f"sina: 获取指数行情 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"sina 指数行情获取失败: {e}")
        return {}
