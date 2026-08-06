"""各时段 Prompt 模板"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

BEIJING_TZ = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent.parent.parent
SUMMARY_PATH = PROJECT_ROOT / "data" / "last_slot.json"

NORTH_FLOW_NOTE = (
    "⚠️ 外资监测说明：北向净买入自2024年证监会新规后不再公开发布。"
    "本报告以三维框架替代：① 北向成交总额（活跃度）+ ② 南向净买入（反向情绪）+ ③ 外部联动（方向推断）。"
    "分析时禁止使用'北向资金净买入/净流出'等说法。"
)

DISCLAIMER = (
    "⚠️ 免责声明：本报告由 AI 自动生成，仅供参考，"
    "不构成任何投资建议。投资有风险，入市需谨慎。"
    "报告中的数据来源于公开接口，不对其准确性做任何保证。"
)

SYSTEM_PROMPT = """你是一位资深量化交易分析师，专注于 A 股市场。
你的分析风格：
- 数据驱动，从数字中提取信号而非主观判断
- 关注量价关系、资金流向、板块轮动
- 技术分析结合市场微观结构
- 输出简洁有力，避免陈词滥调

格式要求（在每份报告中严格遵守）：
1. **市场概览**：2-3 句话概括当前市场状态
2. **核心指标**：关键数据（涨跌比、成交额、外资流向监测等）+ 解读
3. **板块热点**：领涨/领跌板块及驱动因素分析
4. **技术信号**：关键指数的技术指标状态（MA/MACD/RSI/KDJ）+ 信号解读
5. **量化视角**：资金流向、量价关系、市场宽度等量化分析
6. **宏观背景**：CPI/PPI/PMI/M2/LPR 等宏观数据解读，结合当前市场环境分析政策面和流动性
7. **风险提示**：当前市场的主要风险和关注点

## 重要数据说明
- **外资监测**（三维框架——活跃度+南向+外部联动）：
  ① 活跃度：北向成交总额（turnover_total，沪+深合计，mx-source）→ 外资参与热度
     高活跃度（>300亿）=外资积极参与；低活跃度（<100亿）=外资观望，内资主导
  ② 外资占比：北向成交/两市成交（participation_pct）→ 外资定价权
     占比>10%=外资主导盘面；占比<3%=外资影响微弱
  ③ 沪/深偏好：沪市成交占比（sh_ratio）→ 偏价值防御（>55%）vs 偏成长进攻（<45%）
  ④ 南向资金：港股通净买入（south_flow.south_net）→ A股情绪反向指标
     南向大幅净买入（>30亿）=内资南下抄底港股，A股情绪偏弱；
     南向净卖出=内资回流A股，A股情绪偏强
  ⑤ 外部联动：A50/恒生科技/离岸人民币 → 外资方向推断
     三者同向时信号强（如A50涨+恒生涨+CNH升值=外资risk-on）；
     背离时信号弱，以外资活跃度为主要参考
  ⑥ 分析口诀：
     - 北向高活跃+南向净卖出=内外资都在A股，偏多
     - 北向高活跃+南向大幅净买入=外资活跃但内资南下，分歧加大
     - 北向低活跃+外部联动强势=外资缺席但外盘带动，内资跟涨
     - 北向低活跃+南向净买入+外部联动弱=全面观望，谨慎
- **数据限制**：北向净买入方向自2024年证监会新规后不再公开发布。
  所有'北向净买入/净流出'类说法均为推测，不得以确定语气表述。
  分析时一律使用'外资监测'或分项指标名称。

输出使用 HTML 段落格式（<p>、<h3>、<ul><li>），避免使用 ``` 代码块。"""


def build_pre_market_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """盘前简报 prompt (09:25)"""
    return f"""请生成一份 A 股盘前简报（开盘前）。

    {comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 隔夜全球市场数据
{_format_json(data.get("global", {}))}

## 宏观经济背景
{_format_json(data.get("macro", {}))}

## 今日关注
请重点分析：
1. 隔夜美股表现对 A 股开盘的传导效应
2. 富时 A50 期货的指向意义
3. 当日宏观背景（CPI/PPI/PMI/M2等指标）对市场情绪的潜在影响
4. 今日可能影响市场的重大事件或数据发布
5. 昨日 A 股主要指数位置及技术含义
6. 今日开盘前需要关注的板块和个股

{DISCLAIMER}"""


def build_morning_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """早盘分析 prompt (10:30)"""
    return f"""请生成一份 A 股早盘分析报告（开盘后 1 小时）。

    {comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 实时行情数据
{_format_json(data)}

## 分析要点
1. 开盘走势特征（高开/低开/平开，幅度和原因分析）
2. 量能异动（成交量是否有超常规放大或萎缩）
3. 板块轮动方向（资金在哪些板块聚集，哪些流出）
4. 涨跌比和涨跌停家数的信号意义
5. 外资监测：北向成交活跃度（高/中/低）+ 外资占比 + 南向资金反向信号
6. 技术面关键位置（主要指数靠近支撑还是阻力位）

{DISCLAIMER}"""


def build_midday_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """午盘总结 prompt (11:30)"""
    return f"""请生成一份 A 股午盘总结报告（上午收盘后）。

    {comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 行情数据
{_format_json(data)}

## 分析要点
1. 上午盘面整体特征（强势/弱势/震荡）
2. 涨跌比和成交额解读（今日量能水平）
3. 领涨/领跌板块的持续性判断
4. 外资监测：半日北向活跃度变化 + 外资占比趋势 + 南向资金流向 + 沪/深偏好
5. 下午盘面展望（结合上午走势和历史模式）
6. 需要注意的异常信号

{DISCLAIMER}"""


def build_afternoon_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """午后实战快评 prompt (14:00) — 五模块 + 红黄绿灯"""
    persistence_text = _compute_persistence(data)
    warning_text = _compute_warning_lights(data, comparison_text, persistence_text)

    return f"""请生成一份 A 股午后实战快评（14:00 时段）。

{comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 实时数据
{_format_json(data)}

## ⚠️ 本时段使用「实战快评」格式（五模块）

请严格按照一→二→四→五→六的顺序输出，不得调整，每模块各至少 2 句话：

### 模块一：边际速览
从上面的对比数据中提取核心变化：
- 指数方向：较上一时段是加速还是衰竭？
- 量能：放量/缩量幅度，判断市场参与度
- 涨跌比变化：市场宽度是扩张还是收缩

### 模块二：量价结构
- 权重股成交占比判断虹吸效应（沪深300成交额/两市成交额）
- 若权重占比 > 70%，说明资金集中大票，个股活跃度下降
- 结合板块轮动数据，判断资金是在权重防御还是题材进攻

### 模块四：内外联动
- A50/恒生/离岸人民币较上一时段的变化方向
- 外部指标与 A 股是同向还是背离？
- 如有背离（如 A50 跌但上证涨），重点解读

### 模块五：持续性评估

{persistence_text}

### 模块六：红黄绿灯

{warning_text}

## 输出规则
- 每个模块的标题用 <h3>，内容用 <p> + <ul><li>
- 严格按照一→二→四→五→六的顺序，不得重排
- 模块三（盘口博弈）本版本暂不输出，不要自行编造
- 所有边际变化必须引用对比数据中的具体数字

{DISCLAIMER}"""


def build_close_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """收盘报告 prompt (15:00)"""
    return f"""请生成一份完整的 A 股收盘复盘报告。

    {comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 全日行情数据
{_format_json(data)}

## 分析要点
1. **全日综述**：用 3-4 句话概括今日市场
2. **指数分析**：上证/深证/创业板/科创50 分别分析，关注技术指标信号
3. **量价分析**：今日量能与涨跌幅的匹配程度
4. **板块轮动**：今日主线板块和杀跌板块的驱动逻辑
5. **资金面**：外资监测（全日活跃度+外资占比+南向资金+沪/深偏好）、龙虎榜信号
6. **市场宽度**：涨跌比、新高新低比
7. **技术信号**：主要指数的 MA/MACD/RSI/KDJ 指标状态
8. **明日关注**：明日需要重点关注的板块、个股、技术位

{DISCLAIMER}"""


# 时段 → Prompt 构建函数映射
SLOT_PROMPT_MAP = {
    "0925": build_pre_market_prompt,
    "1030": build_morning_prompt,
    "1130": build_midday_prompt,
    "1400": build_afternoon_prompt,
    "1500": build_close_prompt,
}

# 时段 → 中文标签映射
SLOT_LABEL = {
    "0925": "盘前简报",
    "1030": "早盘分析",
    "1130": "午盘总结",
    "1400": "午后更新",
    "1500": "收盘报告",
}


def _format_json(data: dict[str, Any], comparison_text: str = "") -> str:
    """将数据格式化为 prompt 友好文本"""
    import json
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _compute_persistence(data: dict[str, Any]) -> str:
    """模块五：持续性评估——从 last_slot.json 历史计算。

    输出两个信号：
    1. 涨跌比连续偏多(>70%)或偏空(<40%)的小时数
    2. 市场宽度方向反转（昨多今空/昨空今多）
    """
    if not SUMMARY_PATH.exists():
        return "暂无历史数据，持续性评估需要至少 1 个交易日积累。"

    try:
        raw = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        history = raw.get("history", {})
    except Exception:
        return "历史数据读取失败，跳过持续性评估。"

    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    yesterday = (datetime.now(BEIJING_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. 连续偏多/偏空小时数
    lines: list[str] = []
    today_data = history.get(today, {})
    consecutive_bull = 0
    consecutive_bear = 0
    for slot in ["1130", "1030"]:  # 从最近往前数，0925 不参与
        entry = today_data.get(slot, {})
        up_ratio = entry.get("overview", {}).get("up_ratio", 0) or 0
        if up_ratio > 70:
            consecutive_bull += 1
            if consecutive_bear > 0:
                break  # 方向变了，停
        elif up_ratio < 40:
            consecutive_bear += 1
            if consecutive_bull > 0:
                break
        else:
            break  # 中间时段，不连续

    if consecutive_bull >= 2:
        lines.append(f"- ⚠️ 涨跌比已连续 {consecutive_bull} 小时偏多（>70%），持续超 2 小时反转概率大增")
    elif consecutive_bull == 1:
        lines.append(f"- 涨跌比连续偏多 1 小时，暂未达到反转预警阈值，下一小时需关注")
    if consecutive_bear >= 2:
        lines.append(f"- ⚠️ 涨跌比已连续 {consecutive_bear} 小时偏空（<40%），持续超 2 小时可能出现冰点反弹")
    elif consecutive_bear == 1:
        lines.append(f"- 涨跌比连续偏空 1 小时，暂未达到反转预警阈值")

    if not consecutive_bull and not consecutive_bear:
        lines.append("- 涨跌比未出现连续极端偏多或偏空，市场宽度正常波动")

    # 2. 方向反转判断
    yesterday_data = history.get(yesterday, {})
    yesterday_close = yesterday_data.get("1500", yesterday_data.get("1130", {}))

    if yesterday_close:
        yest_up = yesterday_close.get("overview", {}).get("up_ratio", 0) or 0
        today_latest = today_data.get("1130", today_data.get("1030", {}))
        today_up = today_latest.get("overview", {}).get("up_ratio", 0) or 0

        if yest_up and today_up:
            delta = round(today_up - yest_up, 1)
            if yest_up > 65 and today_up < 45:
                lines.append(f"- 🚨 市场宽度反转：昨日偏多（{yest_up:.0f}%）→ 今日转空（{today_up:.0f}%），跌幅 {abs(delta):.0f}pp，追涨亏钱效应扩散")
            elif yest_up < 35 and today_up > 55:
                lines.append(f"- 🔄 市场宽度反转：昨日偏空（{yest_up:.0f}%）→ 今日转多（{today_up:.0f}%），情绪修复")
            elif yest_up > 60 and today_up > 60:
                lines.append(f"- ✅ 市场宽度延续偏多：昨日 {yest_up:.0f}% → 今日 {today_up:.0f}%，多头情绪持续")
            elif yest_up < 40 and today_up < 40:
                lines.append(f"- 市场宽度延续偏空：昨日 {yest_up:.0f}% → 今日 {today_up:.0f}%，弱势未改")
            else:
                lines.append(f"- 市场宽度方向：昨日 {yest_up:.0f}% → 今日 {today_up:.0f}%（变化 {delta:+.0f}pp）")
    else:
        lines.append("- 昨日数据暂缺，方向反转评估跳过（需 1 个交易日积累后生效）")

    # 3. 昨日涨停溢价率（标准算法：中位数）
    yest_codes = _get_yesterday_limit_codes(yesterday, history)
    if yest_codes:
        premium = _calc_limit_up_premium(yest_codes)
        if premium is not None:
            prefix = "+" if premium >= 0 else ""
            if premium >= 3:
                lines.append(f"- ✅ 昨日涨停溢价率 {prefix}{premium:.1f}%（中位数），打板赚钱效应良好")
            elif premium >= 0:
                lines.append(f"- 昨日涨停溢价率 {prefix}{premium:.1f}%（中位数），打板盈亏平衡，追涨需谨慎")
            else:
                lines.append(f"- 🚨 昨日涨停溢价率 {prefix}{premium:.1f}%（中位数），打板亏钱效应扩散，短线情绪恶化")
        else:
            lines.append("- 昨日涨停溢价率暂缺（部分代码尚未收录在行情源中）")
    else:
        lines.append("- 昨日涨停股列表暂缺（需 1 个交易日积累后生效）")

    return "\n".join(lines)


def _get_yesterday_limit_codes(yesterday: str, history: dict) -> list[dict[str, str]]:
    """从历史数据中获取昨日涨停股代码列表（优先取 1500 收盘时段）。"""
    yest_data = history.get(yesterday, {})
    close = yest_data.get("1500", yest_data.get("1130", yest_data.get("1030", {})))
    return close.get("limit_up_codes", [])


def _calc_limit_up_premium(codes: list[dict[str, str]]) -> float | None:
    """计算昨日涨停股今日的中位数涨幅（标准算法）。

    通过 hq.sinajs.cn 批量查询实时行情，一次 HTTP 请求。
    返回 None 表示数据不可用。
    """
    if not codes:
        return None

    # 拼接新浪行情查询代码（sh/sz 前缀由函数判断）
    symbols = [_sina_symbol(c["code"]) for c in codes if c.get("code")]
    if not symbols:
        return None

    # 批量查询（hq.sinajs.cn 单次最多约 50 个）
    batch_size = 40
    all_changes: list[float] = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            url = f"http://hq.sinajs.cn/list={','.join(batch)}"
            resp = requests.get(
                url,
                headers={"Referer": "https://finance.sina.com.cn"},
                timeout=8,
            )
            if resp.status_code != 200:
                continue
            resp.encoding = "gbk"

            import re
            for line in resp.text.strip().split("\n"):
                m = re.search(r'="(.+)"', line)
                if not m or not m.group(1).strip():
                    continue
                vals = m.group(1).split(",")
                if len(vals) < 4:
                    continue
                try:
                    price = float(vals[1] or 0)
                    prev_close = float(vals[2] or 0)
                    if prev_close > 0:
                        change = (price - prev_close) / prev_close * 100
                        if abs(change) < 20:  # 过滤异常值（新股/复牌暴涨等）
                            all_changes.append(change)
                except (ValueError, ZeroDivisionError):
                    continue
        except Exception as e:
            logger.debug(f"溢价率查询失败: {e}")
            continue

    if not all_changes:
        return None

    # 中位数
    sorted_changes = sorted(all_changes)
    n = len(sorted_changes)
    if n % 2 == 1:
        return round(sorted_changes[n // 2], 1)
    return round((sorted_changes[n // 2 - 1] + sorted_changes[n // 2]) / 2, 1)


def _sina_symbol(code: str) -> str:
    """将纯数字代码转为新浪行情前缀格式（sh600xxx / sz000xxx / sz300xxx 等）。"""
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _compute_warning_lights(data: dict[str, Any], comparison_text: str, persistence_text: str = "") -> str:
    """根据数据计算红黄绿灯信号，返回 prompt 可注入的文本。

    在 Python 端计算保证一致性，AI 只做解读不做判断。
    外资监测使用三维框架：活跃度（成交总额）+ 南向（反向情绪）+ 外部联动（方向推断）。
    """
    red: list[str] = []
    yellow: list[str] = []
    green: list[str] = []

    overview = data.get("overview", {})
    north = data.get("north_flow", {})
    index_data = data.get("index", {})
    linked = data.get("linked_markets", {})

    up_ratio = overview.get("up_ratio", 0) or 0
    total_amount = overview.get("total_amount", 0) or 0

    # 外资监测指标
    turnover_total = north.get("turnover_total", 0) or 0    # 北向成交总额（亿）
    participation = north.get("participation_pct", 0) or 0   # 外资占比（%）
    sh_ratio = north.get("sh_ratio", 0) or 0                 # 沪市成交占比（%）
    south = north.get("south_flow", {}) or {}                 # 南向数据
    south_net = south.get("south_net", 0) or 0               # 南向净买入（亿）

    # 外部联动
    a50 = (linked.get("a50", {}) or {}).get("change_pct", 0) or 0
    hstech = (linked.get("hstech", {}) or {}).get("change_pct", 0) or 0
    cnh = (linked.get("cnh", {}) or {}).get("change_pct", 0) or 0

    # 上证涨跌幅
    上证 = index_data.get("000001", {})
    if isinstance(上证, dict):
        sh_pct = 上证.get("change_pct", 0) or 0
    else:
        sh_pct = 0

    # ── 红灯条件 ──
    # 外资高活跃+南向大幅流出 = 外资在A股活跃但内资跑了
    if turnover_total > 300 and south_net > 50 and sh_pct < -0.5:
        red.append(f"北向高活跃（{turnover_total:.0f}亿）但南向大幅净买入 {south_net:.0f} 亿，内资加速南下+指数承压，内外资分歧加剧")
    # 极低活跃度+指数大跌 = 外资撤退+内资踩踏
    if turnover_total > 0 and turnover_total < 150 and sh_pct < -1.5:
        red.append(f"北向成交仅 {turnover_total:.0f} 亿（低活跃）+ 上证 {sh_pct:+.2f}%，外资撤出+跌势加速")
    # 外资占比骤降 = 外资出货
    if participation > 0 and participation < 2 and up_ratio < 40:
        red.append(f"外资占比仅 {participation:.1f}%（极低），外资基本退出定价，内资踩踏中")

    # ── 黄灯条件 ──
    if 45 <= up_ratio <= 55:
        yellow.append(f"涨跌比 {up_ratio:.0f}% 处于多空平衡区，方向待选，减少仓位等待信号")
    # 北向低活跃 = 外资观望
    if 0 < turnover_total < 200:
        yellow.append(f"北向成交 {turnover_total:.0f} 亿（低活跃度），外资整体观望，内资主导盘面")
    # 沪/深偏好极端 = 外资偏防御
    if sh_ratio > 70:
        yellow.append(f"沪市占北向成交 {sh_ratio:.0f}%，外资极度偏向价值防御，成长股缺乏外资支撑")
    # 南向大幅流入 = 内资外流
    if south_net > 30:
        yellow.append(f"南向净买入 {south_net:.0f} 亿（内资南下），A 股短线资金被分流")
    # 外部联动背离
    if a50 < -0.3 and sh_pct > 0.3:
        yellow.append(f"⚠️ A50跌{a50:+.2f}%但上证涨{sh_pct:+.2f}%，外盘不认可内盘涨势，偏空信号")
    if "板块快速轮动" in comparison_text or "板块部分轮动" in comparison_text:
        yellow.append("板块轮动加速，主线不清晰，追涨易被套")

    # ── 绿灯条件 ──
    if up_ratio > 65:
        green.append(f"涨跌比 {up_ratio:.0f}% 偏暖，多头占主导")
    # 外资高活跃+南向净卖出 = 内外资都在A股
    if turnover_total > 300 and south_net < 0:
        green.append(f"北向高活跃（{turnover_total:.0f}亿）+ 南向净卖出 {south_net:.0f} 亿，内外资都在A股，偏多")
    # 外资占比高+外部联动同向
    if participation > 8 and a50 > 0 and hstech > 0:
        green.append(f"外资占比 {participation:.1f}% + A50和恒生科技同向上涨，外资主导+外盘配合")
    # 沪/深均衡 = 外资全面参与
    if 40 <= sh_ratio <= 60 and turnover_total > 250:
        green.append(f"沪/深成交均衡（沪{sh_ratio:.0f}%），外资全面参与，价值成长都有支撑")
    if not red and not yellow:
        green.append("无红灯或黄灯信号，当前盘面暂时无忧")

    # ── 持续性信号 ──
    if "连续 2 小时偏多" in persistence_text or "连续 2 小时偏空" in persistence_text:
        yellow.append("涨跌比连续极端，尾盘反转概率上升，建议减仓观望")
    if "追涨亏钱效应扩散" in persistence_text:
        red.append("昨日追涨今日亏损，亏钱效应扩散中，短线资金加速离场")

    # 降级：如果红灯 <= 0 and 黄灯 <= 0 and 绿灯 <= 0
    if not red and not yellow and not green:
        yellow.append("今日数据无明显极端信号，建议按原计划执行，不做额外调仓")

    parts = []
    parts.append(f"🔴 **红灯**（危险信号）：{chr(10)}" +
                 chr(10).join(f"  - {r}" for r in red) if red else "🔴 **红灯**：暂无触发")
    parts.append(f"🟡 **黄灯**（观望信号）：{chr(10)}" +
                 chr(10).join(f"  - {y}" for y in yellow) if yellow else "🟡 **黄灯**：暂无触发")
    parts.append(f"🟢 **绿灯**（进攻信号）：{chr(10)}" +
                 chr(10).join(f"  - {g}" for g in green) if green else "🟢 **绿灯**：暂无触发")

    return chr(10).join(parts)
