"""数据采集主逻辑 —— 多源聚合 + 交叉校验（纯 HTTP，无 akshare 依赖）"""

import logging
import re
from typing import Any

import requests

from src.data.sources import akshare_source, sina_source, eastmoney_source, commodities_source, linked_markets_source, sina_lhb_source
from src.data.validator import validate_index_quotes
from src.data.macro_loader import load_macro_data
from src.analysis.external_consensus import build_consensus_diagnosis

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def collect_all_data(slot: str) -> dict[str, Any]:
    """采集所有数据，按报告时段调整内容。"""
    logger.info(f"开始采集数据 (slot={slot})")

    # 指数行情（主源 + 备用源）
    index_data = akshare_source.fetch_index_quotes()
    index_backup = sina_source.fetch_index_quotes()

    # 板块表现
    sector_data = akshare_source.fetch_sector_performance()

    # 涨跌榜
    movers_data = akshare_source.fetch_top_movers()

    # 市场概况
    overview_data = akshare_source.fetch_market_overview()

    # 大宗商品 & 汇率
    commodities_data = commodities_source.fetch_all_commodities()

    # 外围市场联动（A50 + 恒生科技 + 离岸人民币）
    linked_data = linked_markets_source.fetch_linked_markets()

    # 交叉校验指数
    if index_backup:
        index_data = validate_index_quotes(index_data, index_backup)

    # 两市成交额（亿）：上证+深证指数成交额（amount 单位万元），
    # 在采集阶段就计算好，供外资参与度和 overview 使用
    total_market_amount = 0.0
    for code in ("000001", "399001"):
        info = index_data.get(code, {})
        if isinstance(info, dict):
            total_market_amount += float(info.get("amount", 0) or 0) / 1e4  # 万元 → 亿
    total_market_amount = round(total_market_amount, 0)
    if total_market_amount > 0:
        overview_data["total_amount"] = total_market_amount

    # 盘中及收盘数据：外资监测 + 资金流（新浪，替代两融）+ 龙虎榜 + 南向
    north_data: dict = {}
    dragon_data: list = []
    fund_flow_data: dict = {}
    if slot in ("1030", "1130", "1400", "1500"):
        # ── 外资监测 ──
        # ⚠️ 北向净买入自2024年证监会新规后不再公开发布。
        # mx-source 的"北向成交总额"查询实际返回的是 A 股板块成交额
        # （"全部A股(板块)"=全市场成交），曾被误当北向活跃度——已废弃。
        # 外资监测 = 南向资金（真实）+ 外部联动共识（linked_markets）。
        north_data = {
            "source": "em_datacenter_south",
            "_note": (
                "北向净买入自2024年证监会新规后不再公开发布。"
                "本报告外资监测由南向资金（港股通净买入，A股情绪反向指标）"
                "和外部联动（A50/恒生科技/恒生指数/离岸人民币方向推断）构成。"
            ),
        }

        # ── 南向资金（港股通，反向参考）──
        south_data = eastmoney_source.fetch_south_bound()
        if south_data:
            north_data["south_flow"] = south_data

        fund_flow_data = eastmoney_source.fetch_market_fund_flow()
        if slot in ("1400", "1500"):
            dragon_data = sina_lhb_source.fetch_daily_lhb()

    # 盘前简报特殊数据：隔夜美股
    global_data: dict = {}
    if slot == "0925":
        global_data = _fetch_overnight_global()

    # 清理校验标记——不要传给 DeepSeek，仅供内部日志使用
    validation_info = index_data.pop("_validation", {})
    if validation_info.get("warnings"):
        logger.warning(f"数据校验警告: {validation_info['warnings']}")

    # 宏观数据（从本地 JSON 加载）
    macro_data = load_macro_data()

    # 外部联动一致性诊断（三层信号引擎）
    # 提取上证涨跌幅用于背离检测
    sh_pct = 0.0
    sh_info = index_data.get("000001", {})
    if isinstance(sh_info, dict):
        sh_pct = sh_info.get("change_pct", 0) or 0
    consensus_diagnosis = build_consensus_diagnosis(linked_data, sh_pct)

    result = {
        "slot": slot,
        "index": index_data,
        "sectors": sector_data,
        "movers": movers_data,
        "overview": overview_data,
        "north_flow": north_data,
        "dragon_tiger": dragon_data,
        "fund_flow": fund_flow_data,
        "commodities": commodities_data,
        "linked_markets": linked_data,
        "external_consensus": consensus_diagnosis,
        "global": global_data,
        "macro": macro_data,
    }

    logger.info(f"数据采集完成 (slot={slot})")
    return result


def _fetch_overnight_global() -> dict[str, Any]:
    """获取隔夜全球市场数据（新浪）"""
    result = {}

    # 纳斯达克指数（新浪 gb_ 格式: [0]名称 [1]价格 [2]涨跌幅% ...）
    try:
        url = "http://hq.sinajs.cn/list=gb_ixic"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = re.search(r'="(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 3:
                result["us"] = {
                    "index": "纳斯达克",
                    "price": float(vals[1] or 0),
                    "change_pct": float(vals[2] or 0),
                }
    except Exception as e:
        logger.debug(f"隔夜美股获取失败: {e}")

    # 富时A50期货（复用 linked_markets 的解析，格式: [0]最新价 [2]涨跌幅% [3]昨收）
    try:
        url = "http://hq.sinajs.cn/list=nf_A50"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = re.search(r'="(.+)"', resp.text)
        if m:
            a50 = linked_markets_source._parse_a50(m.group(1))
            if a50:
                result["a50"] = a50
            else:
                logger.debug("nf_A50 数据为空（非新加坡交易时段）")
    except Exception as e:
        logger.debug(f"隔夜A50获取失败: {e}")

    return result
