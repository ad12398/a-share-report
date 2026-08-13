"""东方财富 & 同花顺数据源 —— 外资监测 & 融资融券（纯 HTTP API）

龙虎榜已迁移至 sina_lhb_source.py（新浪源，东财 push2 阿里云 IP 被封）。

⚠️ 2024 年证监会新规后，北向净买入实时数据不再公开发布。
本模块中的 fetch_north_flow() 已废弃（同花顺 hexin 返回静态缓存数据），
北向活跃度改用 mx_source.fetch_north_turnover()，南向改用东财 datacenter API。
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

# 同花顺北向资金 API（零认证，替代东财 push2）
HEXIN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Host": "data.hexin.cn",
    "Referer": "https://data.hexin.cn/",
}

# 东财 API 端点（仅尝试 push2，失败快速降级）
EM_BASE_URLS = [
    "https://push2.eastmoney.com",
]


def _try_endpoints(url_path: str, timeout: int = 8, max_retries: int = 1) -> requests.Response | None:
    """尝试从东财端点获取数据（单次尝试，失败快速返回）"""
    for base in EM_BASE_URLS:
        url = base + url_path
        for attempt in range(max_retries):
            try:
                logger.info(f"东财请求: {url[:80]}...")
                resp = requests.get(url, headers=HEADERS, timeout=timeout)
                if resp.status_code == 200 and resp.text and resp.text.strip():
                    return resp
                logger.warning(f"东财返回异常: status={resp.status_code}, len={len(resp.text) if resp.text else 0}")
            except requests.exceptions.Timeout:
                logger.warning(f"东财超时: {url[:60]}...")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"东财连接失败: {e}")
            except Exception as e:
                logger.warning(f"东财请求异常: {e}")
    logger.warning(f"东财端点不可达: {url_path}")
    return None


def fetch_north_flow() -> dict[str, Any]:
    """[已废弃] 同花顺 hexin dayChart API 返回静态缓存数据，不可用于实时分析。

    北向净买入自 2024 年证监会新规后不再公开发布。
    北向活跃度数据请使用 mx_source.fetch_north_turnover()。
    南向资金请使用 fetch_south_bound()。
    """
    logger.warning("fetch_north_flow() 已废弃：hexin API 返回静态缓存数据。使用 mx_source + 南向替代。")
    return {}


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


def fetch_margin_trading() -> dict[str, Any]:
    """获取融资融券数据（东方财富）

    返回: {
        "margin_balance": float,      # 融资余额（亿）
        "short_balance": float,       # 融券余额（亿）
        "total_balance": float,       # 两融余额（亿）
        "margin_buy": float,          # 融资买入额（亿）
        "date": str,                  # 数据日期
    }
    """
    try:
        # 东财融资融券数据接口
        url_path = (
            "/api/qt/clist/get?"
            "pn=1&pz=1&po=1&np=1&fs=m:0+t:6&fid=f3"
            "&fields=f2,f3,f12,f14,f152,f124,f125,f126,f127"
        )
        resp = _try_endpoints(url_path, timeout=20)
        if resp is None:
            # 尝试备用接口：datacenter API
            return _fetch_margin_fallback()

        # push2 API 返回的可能只是标的列表，融资融券汇总需要用另一个接口
        return _fetch_margin_fallback()
    except Exception as e:
        logger.error(f"融资融券获取失败: {e}")
        return {}


def _fetch_margin_fallback() -> dict[str, Any]:
    """融资融券数据备用接口（datacenter）"""
    try:
        # 东方财富数据中心 — 融资融券交易汇总
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPTA_WEB_MARGIN_TRADE"
            "&columns=ALL"
            "&sortColumns=TRADE_DATE&sortTypes=-1"
            "&pageSize=1&pageNumber=1"
        )
        resp = requests.get(
            url,
            headers={**HEADERS, "Referer": "https://data.eastmoney.com/rzrq/total.html"},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"融资融券 datacenter 返回: status={resp.status_code}")
            return {}
        data = resp.json()
        if data.get("success") and data.get("result") and data["result"].get("data"):
            items = data["result"]["data"]
            if items:
                item = items[0]
                result = {
                    "margin_balance": float(item.get("FIN_BALANCE", 0) or 0) / 1e8,   # 转亿
                    "short_balance": float(item.get("SALE_BALANCE", 0) or 0) / 1e8,
                    "total_balance": float(item.get("TOTAL_BALANCE", 0) or 0) / 1e8,
                    "margin_buy": float(item.get("FIN_BUY_AMT", 0) or 0) / 1e8,
                    "date": str(item.get("TRADE_DATE", "")[:10]),
                }
                logger.info(f"融资融券: 两融余额 {result['total_balance']:.0f} 亿 (date={result['date']})")
                return result
        logger.warning(f"融资融券 datacenter 返回空数据")
        return {}
    except Exception as e:
        logger.error(f"融资融券备用接口失败: {e}")
        return {}


def fetch_margin_stocks() -> list[dict[str, Any]]:
    """获取融资净买入前10个股"""
    try:
        url_path = (
            "/api/qt/clist/get?"
            "pn=1&pz=10&po=1&np=1&fs=m:0+t:6&fid=f124"
            "&fields=f2,f3,f12,f14,f124,f125"
        )
        resp = _try_endpoints(url_path)
        if resp is None:
            return []
        data = resp.json()
        result = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                result.append({
                    "code": str(item.get("f12", "")),
                    "name": str(item.get("f14", "")),
                    "change_pct": float(item.get("f3", 0) or 0),
                    "margin_net_buy": float(item.get("f124", 0) or 0) / 1e4,  # 转万
                    "margin_balance": float(item.get("f125", 0) or 0) / 1e8,   # 转亿
                })
        logger.info(f"融资买入前10: {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"融资个股获取失败: {e}")
        return []


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
