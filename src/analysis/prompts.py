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
6. **风险提示**：当前市场的主要风险和关注点

输出使用 HTML 段落格式（<p>、<h3>、<ul><li>），避免使用 ``` 代码块。"""


def build_pre_market_prompt(data: dict[str, Any]) -> str:
    """盘前简报 prompt (09:25)"""
    return f"""请生成一份 A 股盘前简报（开盘前）。

## 隔夜全球市场数据
{_format_json(data.get("global", {}))}

## 今日关注
请重点分析：
1. 隔夜美股表现对 A 股开盘的传导效应
2. 富时 A50 期货的指向意义
3. 今日可能影响市场的重大事件或数据发布
4. 昨日 A 股主要指数位置及技术含义
5. 今日开盘前需要关注的板块和个股

{DISCLAIMER}"""


def build_morning_prompt(data: dict[str, Any]) -> str:
    """早盘分析 prompt (10:30)"""
    return f"""请生成一份 A 股早盘分析报告（开盘后 1 小时）。

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


def build_midday_prompt(data: dict[str, Any]) -> str:
    """午盘总结 prompt (11:30)"""
    return f"""请生成一份 A 股午盘总结报告（上午收盘后）。

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


def build_afternoon_prompt(data: dict[str, Any]) -> str:
    """午后更新 prompt (14:00)"""
    return f"""请生成一份 A 股午后市场更新报告。

## 实时数据
{_format_json(data)}

## 分析要点
1. 下午盘面与上午的对比变化
2. 北向资金的最新动向（是否出现拐点）
3. 龙虎榜数据解读（如有）
4. 尾盘展望（最后 1 小时的预判）
5. 需要盯防的关键价位和技术信号

{DISCLAIMER}"""


def build_close_prompt(data: dict[str, Any]) -> str:
    """收盘报告 prompt (15:00)"""
    return f"""请生成一份完整的 A 股收盘复盘报告。

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


def _format_json(data: dict[str, Any]) -> str:
    """将数据格式化为 prompt 友好文本"""
    import json
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
