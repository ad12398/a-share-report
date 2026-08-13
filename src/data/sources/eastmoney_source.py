"""东方财富数据源 —— 南向资金 & 资金流聚合（纯 HTTP API）

龙虎榜已迁移至 sina_lhb_source.py（新浪源）。
融资融券已由新浪资金流聚合替代（fetch_market_fund_flow）。
北向活跃度用 mx_source.fetch_north_turnover()。
"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# 东财 API 端点（仅 run_diagnostics 手动诊断用，push2 阿里云 IP 已被封）
EM_BASE_URLS = [
    "https://push2.eastmoney.com",
]


# ═══ 南向资金（港股通） ═══

EM_DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def fetch_south_bound() -> dict[str, Any]:
    """获取南向资金当日净流向（东财 datacenter RPT_MUTUAL_QUOTA，纯 HTTP）。

    港股通净买入数据仍公开发布，可作为 A 股外资情绪的反向参考：
    南向大幅净买入 → 内资南下抄底港股 → A 股情绪偏弱；
    南向净卖出 → 内资回流 A 股 → A 股情绪偏强。

    返回: {
        "south_net": float,        # 南向合计净买入（亿）
        "south_sh_net": float,     # 港股通(沪)净买入（亿）
        "south_sz_net": float,     # 港股通(深)净买入（亿）
        "south_direction": str,    # "大幅净流入" / "净流入" / "净流出" / "大幅净流出"
        "date": str,               # 数据日期
    }
    """
    try:
        params = {
            "reportName": "RPT_MUTUAL_QUOTA",
            "columns": "TRADE_DATE,MUTUAL_TYPE_NAME,BOARD_TYPE,FUNDS_DIRECTION,BOARD_CODE",
            "quoteColumns": "netBuyAmt~07~BOARD_CODE",
            "quoteType": "0",
            "pageNumber": "1",
            "pageSize": "10",
            "sortTypes": "1",
            "sortColumns": "MUTUAL_TYPE",
            "source": "WEB",
            "client": "WEB",
        }
        resp = requests.get(
            EM_DATACENTER,
            params=params,
            headers={**HEADERS, "Referer": "https://data.eastmoney.com/hsgt/index.html"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"南向资金 HTTP {resp.status_code}")
            return {}

        data = resp.json()
        if not data.get("success"):
            logger.warning(f"南向资金 API: success=False, code={data.get('code')}")
            return {}

        items = data.get("result", {}).get("data", [])
        if not items:
            return {}

        # API 可能返回多日数据，先筛出最大 TRADE_DATE，避免跨交易日混算
        all_dates = [str(i.get("TRADE_DATE", "")) for i in items]
        all_dates = [d for d in all_dates if d]
        if not all_dates:
            return {}
        max_date = max(all_dates)
        items = [i for i in items if str(i.get("TRADE_DATE", "")) == max_date]
        trade_date = max_date[:10]

        south_sh_net = 0.0  # 港股通(沪)
        south_sz_net = 0.0  # 港股通(深)

        for item in items:
            mt_name = item.get("MUTUAL_TYPE_NAME", "")
            funds_dir = item.get("FUNDS_DIRECTION", "")
            if "南向" not in str(funds_dir):
                continue  # 跳过北向条目（数据全零）
            raw_net = item.get("netBuyAmt")
            if raw_net is None:
                continue
            # netBuyAmt 单位: 万元 → 亿（/10000）
            net_yi = round(float(raw_net) / 10000, 2)
            if "沪" in str(mt_name):
                south_sh_net = net_yi
            elif "深" in str(mt_name):
                south_sz_net = net_yi

        south_net = round(south_sh_net + south_sz_net, 2)

        # 方向判定
        if south_net > 30:
            direction = "大幅净流入"
        elif south_net > 0:
            direction = "净流入"
        elif south_net > -30:
            direction = "净流出"
        else:
            direction = "大幅净流出"

        result = {
            "south_net": south_net,
            "south_sh_net": south_sh_net,
            "south_sz_net": south_sz_net,
            "south_direction": direction,
            "date": trade_date,
        }
        logger.info(
            f"南向资金: 合计={south_net:+.1f}亿 "
            f"沪={south_sh_net:+.1f}亿 深={south_sz_net:+.1f}亿 ({direction})"
        )
        return result
    except Exception as e:
        logger.error(f"南向资金获取失败: {e}")
        return {}


# ═══ 新浪资金流聚合（替代融资融券） ═══

# 代表性大盘股（覆盖 30 只，横跨 20+ 行业），用于聚合市场资金流向
FUND_FLOW_STOCKS = [
    # 金融（银行+保险+券商）
    "sh601398",  # 工商银行
    "sh600036",  # 招商银行
    "sh601166",  # 兴业银行
    "sz000001",  # 平安银行
    "sh601318",  # 中国平安
    "sh600030",  # 中信证券
    # 消费（白酒+家电）
    "sh600519",  # 贵州茅台
    "sz000858",  # 五粮液
    "sh600809",  # 山西汾酒
    "sz000333",  # 美的集团
    "sz000651",  # 格力电器
    # 医药+科技
    "sh600276",  # 恒瑞医药
    "sz300750",  # 宁德时代
    "sz002415",  # 海康威视
    "sz002230",  # 科大讯飞
    "sh688981",  # 中芯国际
    # 能源+资源
    "sh601857",  # 中国石油
    "sh601088",  # 中国神华
    "sh601225",  # 陕西煤业
    "sh601899",  # 紫金矿业
    "sh600019",  # 宝钢股份
    # 基建+地产+建材
    "sh601668",  # 中国建筑
    "sz000002",  # 万科A
    "sh600585",  # 海螺水泥
    # 制造+航运
    "sh600031",  # 三一重工
    "sz002594",  # 比亚迪
    "sh601919",  # 中远海控
    # 公用事业+农业+通信
    "sh600900",  # 长江电力
    "sz002714",  # 牧原股份
    "sh600050",  # 中国联通
]

SINA_FLOW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://vip.stock.finance.sina.com.cn",
}


def _fetch_stock_fund_flow(code: str) -> dict[str, Any] | None:
    """获取单只股票最近一个交易日资金流向"""
    try:
        url = (
            f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"MoneyFlow.ssl_qsfx_lscjfb?page=1&num=1&sort=opendate&asc=0&daima={code}"
        )
        resp = requests.get(url, headers=SINA_FLOW_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            return {
                "code": code,
                "date": str(item.get("opendate", "")),
                "net_amount": float(item.get("netamount", 0) or 0),           # 净流入（元）
                "r0_net": float(item.get("r0_net", 0) or 0),                  # 特大单净流入
                "r1_net": float(item.get("r1_net", 0) or 0),                  # 大单净流入
                "r2_net": float(item.get("r2_net", 0) or 0),                  # 中单净流入
                "r3_net": float(item.get("r3_net", 0) or 0),                  # 小单净流入
                "net_ratio": float(item.get("ratioamount", 0) or 0),          # 净流入占比
                "turnover": float(item.get("turnover", 0) or 0),              # 换手率
            }
        return None
    except Exception as e:
        logger.debug(f"资金流 {code} 获取失败: {e}")
        return None


def fetch_market_fund_flow() -> dict[str, Any]:
    """
    聚合代表性个股的资金流向，作为市场资金面代理指标（替代融资融券）。

    返回: {
        "sample_count": int,          # 成功采样的股票数
        "total_net_amount": float,    # 聚合净流入（亿）
        "big_order_net": float,       # 大单+特大单净流入（亿）
        "inflow_count": int,          # 净流入个股数
        "outflow_count": int,         # 净流出个股数
        "date": str,                  # 数据日期
        "source": "sina_moneyflow",   # 数据源标注
        "_note": str,                 # 说明这是替代指标
    }
    """
    results = []
    for code in FUND_FLOW_STOCKS:
        item = _fetch_stock_fund_flow(code)
        if item:
            results.append(item)
        time.sleep(0.2)  # 友好节流，避免触发新浪反爬

    if not results:
        logger.warning("新浪资金流: 所有股票采样失败")
        return {}

    inflow = [r for r in results if r["net_amount"] > 0]
    outflow = [r for r in results if r["net_amount"] < 0]

    total_net = sum(r["net_amount"] for r in results) / 1e8  # 转亿
    big_net = sum(r["r0_net"] + r["r1_net"] for r in results) / 1e8  # 特大+大单，转亿

    result = {
        "sample_count": len(results),
        "total_net_amount": round(total_net, 2),
        "big_order_net": round(big_net, 2),
        "inflow_count": len(inflow),
        "outflow_count": len(outflow),
        "date": results[0]["date"] if results else "",
        "source": "sina_moneyflow",
        "_note": "数据来自新浪资金流（大单/特大单估算），非融资融券官方数据，仅供参考大资金方向",
    }
    logger.info(f"资金流(替代两融): {len(results)}股聚合 net={total_net:.1f}亿 big_order={big_net:.1f}亿 "
                f"涨{len(inflow)}/跌{len(outflow)}")
    return result


# ═══ 诊断工具 ═══

def run_diagnostics() -> dict[str, Any]:
    """运行东财 API 连通性诊断，返回每个端点的测试结果"""
    results = {}

    # 测试 push2 端点
    for base in EM_BASE_URLS:
        label = base.replace("https://", "")
        try:
            test_url = f"{base}/api/qt/kamt.kline/get?fields1=f1&fields2=f2&klt=1&lmt=1"
            resp = requests.get(test_url, headers=HEADERS, timeout=10)
            results[label] = {
                "status": resp.status_code,
                "len": len(resp.text) if resp.text else 0,
                "ok": resp.status_code == 200 and len(resp.text) > 50,
            }
        except requests.exceptions.Timeout:
            results[label] = {"status": "TIMEOUT", "len": 0, "ok": False}
        except requests.exceptions.ConnectionError as e:
            results[label] = {"status": f"CONN_ERR: {e}", "len": 0, "ok": False}
        except Exception as e:
            results[label] = {"status": f"ERR: {e}", "len": 0, "ok": False}

    # 测试 datacenter 端点
    try:
        test_url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPTA_WEB_MARGIN_TRADE&columns=TRADE_DATE&sortColumns=TRADE_DATE&sortTypes=-1&pageSize=1"
        )
        resp = requests.get(test_url, headers={**HEADERS, "Referer": "https://data.eastmoney.com/rzrq/total.html"}, timeout=10)
        results["datacenter-web"] = {
            "status": resp.status_code,
            "len": len(resp.text) if resp.text else 0,
            "ok": resp.status_code == 200 and len(resp.text) > 50,
        }
    except Exception as e:
        results["datacenter-web"] = {"status": f"ERR: {e}", "len": 0, "ok": False}

    return results
