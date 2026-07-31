"""新浪财经龙虎榜数据源 —— 每日上榜列表（替代东财 push2）

新浪龙虎榜页面返回 HTML 表格（GB2312 编码），列：
  序号 | 股票代码 | 股票名称 | 收盘价(元) | 对应值(%) | 成交量(万股) | 成交额(万元)
"对应值(%)" 的语义取决于上榜原因（涨跌幅偏离值/换手率/振幅等），报告中保留此字段供 AI 自行解读。

使用方式：
  from src.data.sources.sina_lhb_source import fetch_daily_lhb
  data = fetch_daily_lhb("2026-07-30")  # 指定日期
  data = fetch_daily_lhb()              # 默认今天（北京时间）
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

BEIJING_TZ = timezone(timedelta(hours=8))

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://vip.stock.finance.sina.com.cn",
}

LHB_URL = (
    "https://vip.stock.finance.sina.com.cn"
    "/q/go.php/vInvestConsult/kind/lhb/index.phtml"
)


def fetch_daily_lhb(date_str: Optional[str] = None) -> list[dict[str, Any]]:
    """获取某日龙虎榜上榜股票列表。

    Args:
        date_str: 日期 "YYYY-MM-DD"，默认今天（北京时间）

    Returns:
        [{code, name, close, change_pct, volume, amount, reason}, ...]
        - code: 股票代码（纯数字字符串，如 "920685"）
        - name: 股票名称
        - close: 收盘价（元）
        - change_pct: 对应值（%，语义取决于上榜原因）
        - volume: 成交量（万股）
        - amount: 成交额（万元）
        - reason: 上榜原因（空字符串表示新浪页面未提供）
    """
    if date_str is None:
        date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    url = f"{LHB_URL}?date={date_str}"
    logger.info(f"龙虎榜(新浪) 请求: date={date_str}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"龙虎榜(新浪) HTTP {resp.status_code}")
            return []

        # 新浪页面编码为 GB2312（兼容 GBK）
        _set_encoding(resp)
        html = resp.text

        if not html or len(html) < 500:
            logger.warning(f"龙虎榜(新浪) 返回内容过短 ({len(html)} 字节)，可能非交易日")
            return []

        return _parse_lhb_table(html, date_str)

    except requests.exceptions.Timeout:
        logger.error("龙虎榜(新浪) 请求超时")
        return []
    except Exception as e:
        logger.error(f"龙虎榜(新浪) 获取失败: {e}")
        return []


def _set_encoding(resp: requests.Response) -> None:
    """尝试设置正确的编码（gb2312 → gbk → utf-8 降级）"""
    for enc in ("gb2312", "gbk", "utf-8"):
        try:
            resp.encoding = enc
            resp.text  # 触发解码
            return
        except (UnicodeDecodeError, LookupError):
            continue
    # 最终兜底
    resp.encoding = "utf-8"


def _parse_lhb_table(html: str, date_str: str) -> list[dict[str, Any]]:
    """从新浪龙虎榜 HTML 页面解析上榜股票列表。

    页面结构：
      <table id="dataTable">
        <tr class="head">表头</tr>
        <tr class="head">序号/代码/名称/收盘价/对应值/成交量/成交额/详情</tr>   ← 可见行
        <tr style="display:none" id="stock{type}_{code}">                  ← 隐藏行（上榜原因）
            ...
            上榜原因：&emsp;&emsp;<a>查看XXX股票行情</a>
            ...
        </tr>
        ...重复...
      </table>

    注意：新浪页面的"上榜原因"文本通常是空的（只有股票链接），不像东财有明确的
    原因文字。`reason` 字段在大多数情况下为空字符串。
    """
    # 1. 定位所有 dataTable（页面有多个，按上榜类型分组）
    table_matches = re.findall(
        r'<table[^>]*id="dataTable"[^>]*>(.*?)</table>', html, re.DOTALL
    )
    if not table_matches:
        logger.warning("龙虎榜(新浪): 未找到 id=dataTable，可能页面结构变更")
        return []

    result: list[dict[str, Any]] = []

    for table_html in table_matches:
        _parse_one_table(table_html, result)

    # 按成交额降序排列（与东财一致）
    result.sort(key=lambda x: x.get("amount", 0), reverse=True)

    logger.info(f"龙虎榜(新浪): {date_str} 解析 {len(result)} 条上榜记录")
    return result


def _parse_one_table(table_html: str, result: list) -> None:
    """解析单个 dataTable，结果追加到 result 列表。"""
    # 2. 按 <tr 分割成行块
    row_blocks = re.findall(r'<tr\b(.*?)</tr>', table_html, re.DOTALL)
    if not row_blocks:
        return

    # 3. 第一遍：收集隐藏行中的上榜原因
    hidden_reasons: dict[str, str] = {}
    for block in row_blocks:
        id_match = re.search(r'id="stock(\d+)_(\d+)"', block)
        if not id_match:
            continue
        key = f"{id_match.group(1)}_{id_match.group(2)}"
        reason = _extract_reason_text(block)
        hidden_reasons[key] = reason

    # 4. 第二遍：解析可见数据行
    for block in row_blocks:
        # 只处理包含 showDetail 的行（可见数据行）
        sd_match = re.search(
            r"showDetail\('(\d+)','(\d+)','([^']+)'", block
        )
        if not sd_match:
            continue

        lhb_type = sd_match.group(1)
        code = sd_match.group(2)

        # 提取股票名称（行内第二个 <a> 标签）
        links = re.findall(r'<a[^>]*>([^<]+)</a>', block)
        name = links[1] if len(links) >= 2 else code

        # 提取 4 个数值列（共同特征：style 含 text-align:right）
        td_values = re.findall(
            r'text-align:right[^"]*"[^>]*>([^<]*)</td>', block
        )
        if len(td_values) < 4:
            logger.debug(f"龙虎榜(新浪): {code} {name} 数值列不足 ({len(td_values)}<4)，跳过")
            continue

        try:
            close_price = float(td_values[0].strip() or 0)
            change_pct = float(td_values[1].strip() or 0)
            volume = float(td_values[2].strip() or 0)
            amount = float(td_values[3].strip() or 0)
        except (ValueError, TypeError) as e:
            logger.debug(f"龙虎榜(新浪): {code} {name} 数值解析失败: {e}")
            continue

        reason_key = f"{lhb_type}_{code}"
        reason = hidden_reasons.get(reason_key, "")

        result.append({
            "code": code,
            "name": name,
            "close": round(close_price, 2),
            "change_pct": round(change_pct, 2),
            "volume": round(volume, 2),      # 万股
            "amount": round(amount, 2),       # 万元
            "reason": reason,
        })


def _extract_reason_text(block: str) -> str:
    """从隐藏行中提取上榜原因文本。

    新浪页面结构：
      上榜原因：&emsp;&emsp;涨幅偏离值达7%的证券<a>查看XXX股票行情</a>
    或者：
      上榜原因：&emsp;&emsp;<a>查看XXX股票行情</a>  （无实际原因）

    返回清理后的纯文本原因，无原因时返回空字符串。
    """
    # 捕获 "上榜原因：" 后到 <a 标签或 </div> 之间的文本
    reason_match = re.search(
        r'上榜原因[：:]\s*(.*?)(?:<a\b|</div>|$)', block, re.DOTALL
    )
    if not reason_match:
        return ""

    raw = reason_match.group(1)

    # 解码 HTML 实体
    raw = raw.replace("&emsp;", "").replace("&nbsp;", " ").replace("\r\n", "")

    # 去掉所有残留 HTML 标签
    text = re.sub(r'<[^>]+>', '', raw).strip()

    # 过滤无效文本
    if not text:
        return ""
    if text in ("　", "  ", ""):
        return ""

    return text
