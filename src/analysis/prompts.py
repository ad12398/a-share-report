"""各时段 Prompt 模板"""

from typing import Any

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
2. **核心指标**：关键数据（涨跌比、成交额、北向资金等）+ 解读
3. **板块热点**：领涨/领跌板块及驱动因素分析
4. **技术信号**：关键指数的技术指标状态（MA/MACD/RSI/KDJ）+ 信号解读
5. **量化视角**：资金流向、量价关系、市场宽度等量化分析
6. **宏观背景**：CPI/PPI/PMI/M2/LPR 等宏观数据解读，结合当前市场环境分析政策面和流动性
7. **风险提示**：当前市场的主要风险和关注点

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
5. 北向资金开盘动向（如有）
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
4. 北向资金的半日流向分析
5. 下午盘面展望（结合上午走势和历史模式）
6. 需要注意的异常信号

{DISCLAIMER}"""


def build_afternoon_prompt(data: dict[str, Any], comparison_text: str = "") -> str:
    """午后实战快评 prompt (14:00) — 四模块 + 红黄绿灯"""
    warning_text = _compute_warning_lights(data, comparison_text)

    return f"""请生成一份 A 股午后实战快评（14:00 时段）。

{comparison_text + chr(10) + chr(10) if comparison_text else ""}
## 实时数据
{_format_json(data)}

## ⚠️ 本时段使用「实战快评」格式（四模块）

请严格按以下顺序输出，每模块不得跳过，各至少 2 句话：

### 模块一：边际速览
从上面的对比数据中提取核心变化：
- 指数方向：较上一时段是加速还是衰竭？
- 量能：放量/缩量幅度，判断市场参与度
- 涨跌比变化：市场宽度是扩张还是收缩

### 模块四：内外联动
- A50/恒生/离岸人民币较上一时段的变化方向
- 外部指标与 A 股是同向还是背离？
- 如有背离（如 A50 跌但上证涨），重点解读

### 模块二：量价结构
- 权重股成交占比判断虹吸效应（沪深300成交额/两市成交额）
- 若权重占比 > 70%，说明资金集中大票，个股活跃度下降
- 结合板块轮动数据，判断资金是在权重防御还是题材进攻

### 模块六：红黄绿灯

{warning_text}

## 输出规则
- 每个模块的标题用 <h3>，内容用 <p> + <ul><li>
- 模块一放在最前面，后面顺序可调整
- 模块三（盘口博弈）和模块五（持续性评估）本版本暂不输出，不要自行编造
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
5. **资金面**：北向资金全日净流向、龙虎榜信号
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


def _compute_warning_lights(data: dict[str, Any], comparison_text: str) -> str:
    """根据数据计算红黄绿灯信号，返回 prompt 可注入的文本。

    在 Python 端计算保证一致性，AI 只做解读不做判断。
    """
    red: list[str] = []
    yellow: list[str] = []
    green: list[str] = []

    overview = data.get("overview", {})
    north = data.get("north_flow", {})
    index_data = data.get("index", {})
    linked = data.get("linked_markets", {})

    up_ratio = overview.get("up_ratio", 0) or 0
    net_flow = north.get("net_flow", 0) or 0
    total_amount = overview.get("total_amount", 0) or 0

    # 上证涨跌幅
    上证 = index_data.get("000001", {})
    if isinstance(上证, dict):
        sh_pct = 上证.get("change_pct", 0) or 0
    else:
        sh_pct = 0

    # ── 红灯条件 ──
    if net_flow < -20 and sh_pct < -0.5:
        red.append(f"北向大幅净流出 {net_flow:+.1f} 亿，上证 {sh_pct:+.2f}%，外资撤退+指数承压，警惕尾盘继续走弱")
    elif net_flow < -10 and up_ratio < 40:
        red.append(f"北向净流出 {net_flow:+.1f} 亿 + 涨跌比仅 {up_ratio:.0f}%，市场情绪接近冰点")
    if "北向反转" in comparison_text or "北向资金反转" in comparison_text:
        red.append("北向资金方向逆转，可能触发程序化止损盘")

    # ── 黄灯条件 ──
    if 45 <= up_ratio <= 55:
        yellow.append(f"涨跌比 {up_ratio:.0f}% 处于多空平衡区，方向待选，减少仓位等待信号")
    if -10 <= net_flow <= 5 and net_flow != 0:
        yellow.append(f"北向 {net_flow:+.1f} 亿不温不火，外资观望中")
    if "板块快速轮动" in comparison_text or "板块部分轮动" in comparison_text:
        yellow.append("板块轮动加速，主线不清晰，追涨易被套")

    # ── 绿灯条件 ──
    if up_ratio > 65 and net_flow > 10:
        green.append(f"涨跌比 {up_ratio:.0f}% + 北向 {net_flow:+.1f} 亿，量价配合良好，趋势健康")
    elif up_ratio > 60:
        green.append(f"涨跌比 {up_ratio:.0f}% 偏暖，多头占主导")
    if "加速上涨" in comparison_text and net_flow >= 0:
        green.append(f"动能加速+北向未出货，上升趋势延续中")
    if not red and not yellow:
        green.append("无红灯或黄灯信号，当前盘面暂时无忧")

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
