"""东方财富妙想 API — 北向资金成交总额 & 方向补充（替代深股通 + 增强沪股通）

API: mkapi2.dfcfs.com/finskillshub/api/claw/query
认证: 环境变量 MX_APIKEY
返回: JSON（原始 API 响应，由调用方解析）

⚠️ 注意：2024年证监会新规后，北向净买入实时数据不再公开。
本模块获取的是成交总额+方向，非净买入金额。
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"


def _api_key() -> str:
    key = os.environ.get("MX_APIKEY", "")
    if not key:
        logger.warning("MX_APIKEY 未设置，mx_source 不可用")
    return key


def fetch_north_turnover() -> dict[str, Any]:
    """获取北向资金成交额、方向、领涨股（补充 hgt 净买入的上下文）

    返回: {
        "total_amount": float,      # 北向成交总额（亿）
        "sh_amount": float,          # 沪股通成交额（亿）
        "sz_amount": float,          # 深股通成交额（亿）
        "sh_direction": str,         # 沪股通方向（"净买入"/"净卖出"）
        "sz_direction": str,         # 深股通方向
        "sh_leader": str,            # 沪股通领涨股
        "sz_leader": str,            # 深股通领涨股
        "date": str,                 # 数据日期
    }
    """
    key = _api_key()
    if not key:
        return {}

    try:
        resp = requests.post(
            MX_API_URL,
            json={"toolQuery": "北向资金成交总额 沪股通 深股通"},
            headers={"Content-Type": "application/json", "apikey": key},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"mx_source HTTP {resp.status_code}")
            return {}

        raw = resp.json()
        return _parse_north_turnover(raw)
    except Exception as e:
        logger.error(f"mx_source 北向成交额查询失败: {e}")
        return {}


def _parse_north_turnover(raw: dict[str, Any]) -> dict[str, Any]:
    """解析 mx-data API 返回的北向成交数据。

    API 返回多个表，取第一个摘要表（含总量/沪/深分拆）。
    值可能是 "2.039万亿"、"8406亿" 等中文格式。
    """
    try:
        inner = raw.get("data", {}).get("data", {}).get("searchDataResultDTO", {})
        tables = inner.get("dataTableDTOList", [])
        if not tables:
            logger.debug("mx_source: dataTableDTOList 为空")
            return {}

        table = tables[0].get("table", {})
        name_map = tables[0].get("nameMap", {})
        dates = table.get("headName", [])
        if not dates:
            return {}
        latest_idx = -1

        result: dict[str, Any] = {"date": _clean_date(str(dates[latest_idx]))}

        # 按表键匹配（兼容两种情况：数字 ID 需走 nameMap，中文字段名直接匹配）
        for key, values in table.items():
            if key == "headName" or not values:
                continue
            val = str(values[latest_idx]) if latest_idx < len(values) else ""

            # 先试 nameMap 翻译 → 再剥离括号后缀
            label = name_map.get(key, key)
            clean_label = label.split("(")[0] if "(" in label else label

            # 顺序很重要：先精确匹配沪/深股通（它们标签里也含"成交"），
            # 再匹配"北向/全部A股"总额行。泛"成交"不再匹配，
            # 避免"两市成交额"被误当北向成交。
            if "沪股通" in clean_label:
                result["sh_amount"] = _parse_amount(val)
            elif "深股通" in clean_label:
                result["sz_amount"] = _parse_amount(val)
            elif "北向" in clean_label or "全部A股" in clean_label:
                amt = _parse_amount(val)
                # 多个总额行时取最大值（summary 表的总额最大）
                if amt > (result.get("total_amount", 0) or 0):
                    result["total_amount"] = amt

        if "total_amount" not in result:
            sh = result.get("sh_amount", 0) or 0
            sz = result.get("sz_amount", 0) or 0
            result["total_amount"] = round(sh + sz, 2) if sh or sz else 0

        logger.info(
            f"mx_source: total={result.get('total_amount')}亿 "
            f"沪={result.get('sh_amount')}亿 深={result.get('sz_amount')}亿"
        )
        return result
    except Exception as e:
        logger.warning(f"mx_source 解析失败: {e}")
        return {}


def _clean_date(raw: str) -> str:
    """清理日期格式：'2026-07-30(四)' -> '2026-07-30'"""
    import re as _re
    m = _re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    return m.group(1) if m else raw


def _parse_amount(val: str) -> float:
    """解析中文金额：'2.039万亿' -> 20390, '8406亿' -> 8406, '9838万' -> 0.98"""
    try:
        val = str(val).strip().replace(",", "").replace("，", "")
        if "万亿" in val:
            return round(float(val.replace("万亿", "")) * 10000, 2)
        elif "亿" in val:
            return round(float(val.replace("亿", "")), 2)
        elif "万" in val:
            return round(float(val.replace("万", "")) / 10000, 2)
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _parse_float(val: Any) -> float:
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.0
