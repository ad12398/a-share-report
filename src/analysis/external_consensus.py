"""外部联动方向一致性引擎 —— 三层信号分析

第一层：单项信号质量（方向 × 幅度加权）
第二层：一致性评分 + 背离检测
第三层：边际变化（与历史对比）
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("a-share-report")

PROJECT_ROOT = Path(__file__).parent.parent.parent
SUMMARY_PATH = PROJECT_ROOT / "data" / "last_slot.json"


# ═══ 单项信号判定 ═══

def _single_signal(name: str, change_pct: float) -> dict[str, Any]:
    """对单个外部指标：方向 × 幅度加权 → 信号强度

    返回: {
        "name": str,         # 指标名称
        "value": float,      # 原始涨跌幅%
        "direction": str,    # "看多" / "看空" / "中性"
        "weight": float,     # 信号强度 -3 ~ +3（方向×幅度）
        "magnitude": str,    # "强" / "中等" / "弱"
    }
    """
    # 方向判断（不同指标方向含义不同）
    is_cnh = "人民币" in name or "CNH" in name
    if is_cnh:
        # 离岸人民币：贬值（+）= 看空A股，升值（-）= 看多A股
        raw_dir = -change_pct
    else:
        # 指数/期货：涨（+）= 看多，跌（-）= 看空
        raw_dir = change_pct

    # 幅度加权
    abs_pct = abs(change_pct)
    if abs_pct >= 1.0:
        magnitude = "强"
        weight_mult = 1.0
    elif abs_pct >= 0.3:
        magnitude = "中等"
        weight_mult = 0.6
    elif abs_pct >= 0.05:
        magnitude = "弱"
        weight_mult = 0.3
    else:
        magnitude = "微弱"
        weight_mult = 0.1

    # 方向判定（带阈值，避免噪点）
    threshold = 0.05  # <0.05% 视为中性
    if raw_dir > threshold:
        direction = "看多"
        weight = round(raw_dir / abs_pct * weight_mult * 3, 1)  # 0 ~ +3
    elif raw_dir < -threshold:
        direction = "看空"
        weight = round(raw_dir / abs_pct * weight_mult * 3, 1)  # 0 ~ -3
    else:
        direction = "中性"
        weight = 0.0

    return {
        "name": name,
        "value": change_pct,
        "direction": direction,
        "weight": weight,
        "magnitude": magnitude,
    }


# ═══ 一致性评估 ═══

def _consensus_score(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """计算一致性评分和置信度

    返回: {
        "score": float,          # -4 ~ +4 加权一致性分数
        "confidence": str,       # "强" / "中" / "弱" / "分歧"
        "bull_count": int,       # 看多数量
        "bear_count": int,       # 看空数量
        "neutral_count": int,    # 中性数量
        "total": int,            # 有效指标总数
    }
    """
    total_weight = 0.0
    bull_count = 0
    bear_count = 0
    neutral_count = 0
    active_count = 0

    for s in signals:
        if s["direction"] == "看多":
            bull_count += 1
            total_weight += s["weight"]
            active_count += 1
        elif s["direction"] == "看空":
            bear_count += 1
            total_weight += s["weight"]  # weight 已经是负数
            active_count += 1
        else:
            neutral_count += 1

    total = active_count + neutral_count
    if total == 0:
        return {"score": 0, "confidence": "数据不足", "bull_count": 0, "bear_count": 0, "neutral_count": 0, "total": 0}

    # 多数方向
    if bull_count > bear_count + 1:
        majority = "bull"
    elif bear_count > bull_count + 1:
        majority = "bear"
    else:
        majority = "mixed"

    # 置信度评估
    if active_count >= 3 and abs(bull_count - bear_count) >= 3:
        confidence = "强"
    elif active_count >= 2 and abs(bull_count - bear_count) >= 2:
        confidence = "中"
    elif majority == "mixed":
        confidence = "分歧"
    else:
        confidence = "弱"

    return {
        "score": round(total_weight, 1),
        "confidence": confidence,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "neutral_count": neutral_count,
        "total": total,
    }


# ═══ 背离检测 ═══

def _detect_divergence(
    consensus: dict[str, Any],
    sh_pct: float,
    signals: list[dict[str, Any]],
) -> list[str]:
    """检测外部信号与 A 股的背离

    返回背离信号列表（为空则无背离）
    """
    alerts: list[str] = []

    score = consensus["score"]
    confidence = consensus["confidence"]

    # 上证涨跌幅与外部共识方向不一致
    if confidence in ("强", "中"):
        if score > 1.5 and sh_pct < -0.3:
            alerts.append(f"外部一致看多（score={score:+.1f}）但上证 {sh_pct:+.2f}%，内盘不认可外盘涨势，偏空信号")
        elif score < -1.5 and sh_pct > 0.3:
            alerts.append(f"外部一致看空（score={score:+.1f}）但上证 {sh_pct:+.2f}%，内盘逆外盘走强，短期偏多但需警惕补跌")

    # 单指标极端与上证背离
    for s in signals:
        if s["magnitude"] != "强":
            continue
        if s["direction"] == "看多" and sh_pct < -1.0:
            alerts.append(f"{s['name']} {s['value']:+.2f}% 强看多，但上证 {sh_pct:+.2f}%，外盘信号不被内盘认可")
        elif s["direction"] == "看空" and sh_pct > 1.0:
            alerts.append(f"{s['name']} {s['value']:+.2f}% 强看空，但上证 {sh_pct:+.2f}%，内盘逆势走强")

    return alerts


# ═══ 边际变化 ═══

def _marginal_change(consensus: dict[str, Any]) -> str:
    """对比上一时段的共识变化（从 last_slot.json 读取）"""
    if not SUMMARY_PATH.exists():
        return "暂无历史对比数据（需 1 个交易日积累）"

    try:
        raw = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        latest = raw.get("latest", {})
        prev_consensus = latest.get("external_consensus", {})
    except Exception:
        return "历史数据读取失败，跳过边际对比"

    if not prev_consensus:
        return "暂无历史对比数据（需 1 个时段积累）"

    prev_score = prev_consensus.get("score", 0) or 0
    prev_conf = prev_consensus.get("confidence", "未知")
    curr_score = consensus["score"]
    curr_conf = consensus["confidence"]

    delta = round(curr_score - prev_score, 1)
    lines = []

    if abs(delta) >= 1.5:
        direction = "加强" if (curr_score > 0 and delta > 0) or (curr_score < 0 and delta < 0) else "减弱"
        lines.append(f"外部共识较上一时段明显{direction}（{prev_score:+.1f} → {curr_score:+.1f}，Δ{delta:+.1f}）")
        if prev_conf != curr_conf:
            lines.append(f"置信度变化：{prev_conf} → {curr_conf}")
    elif abs(delta) >= 0.5:
        lines.append(f"外部共识微调（{prev_score:+.1f} → {curr_score:+.1f}，Δ{delta:+.1f}）")
    else:
        lines.append(f"外部共识与上一时段基本持平（{curr_score:+.1f}）")

    return "\n".join(lines)


# ═══ 诊断文本生成 ═══

def build_consensus_diagnosis(
    linked_data: dict[str, Any],
    sh_pct: float = 0,
) -> dict[str, Any]:
    """三层信号引擎主入口。

    Args:
        linked_data: fetch_linked_markets() 的返回结果
        sh_pct: 上证指数涨跌幅（用于背离检测）

    返回: {
        "diagnosis_text": str,        # 结构化诊断文本（注入 AI prompt）
        "consensus_score": float,     # 一致性分数
        "consensus_confidence": str,  # 置信度
        "divergence_alerts": list,    # 背离警告列表
        "signals": list,              # 各指标明细
    }
    """
    # 第一层：单项信号分析
    signals: list[dict[str, Any]] = []
    lines: list[str] = []
    lines.append("**外部方向推断**：")

    for key, data in linked_data.items():
        if not isinstance(data, dict):
            continue
        name = data.get("name", key)
        pct = data.get("change_pct", 0) or 0
        sig = _single_signal(name, pct)
        signals.append(sig)

    # 第二层：一致性
    consensus = _consensus_score(signals)

    score = consensus["score"]
    confidence = consensus["confidence"]
    bull = consensus["bull_count"]
    bear = consensus["bear_count"]
    total = consensus["total"]

    # 诊断标题
    if confidence == "强":
        if score > 2:
            lines.append(f"外部一致看多（{bull}/{total}，置信度高）")
        elif score < -2:
            lines.append(f"外部一致看空（{bear}/{total}，置信度高）")
    elif confidence == "中":
        lines.append(f"外部偏{'多' if score > 0 else '空'}（{bull}看多/{bear}看空/{consensus['neutral_count']}中性，置信度中等）")
    elif confidence == "分歧":
        lines.append(f"外部方向分歧（{bull}看多/{bear}看空，信号不可靠）")
    else:
        lines.append(f"外部信号{'偏多但较弱' if score > 0 else '偏空但较弱' if score < 0 else '中性'}（{bull}看多/{bear}看空，置信度低）")

    # 各指标明细
    lines.append("├─ 指标明细：")
    for s in signals:
        icon = {"强": "●", "中等": "◉", "弱": "○", "微弱": "·"}.get(s["magnitude"], "○")
        lines.append(
            f"│  {icon} {s['name']}: {s['value']:+.2f}% "
            f"（{s['direction']}，{s['magnitude']}信号，权重 {s['weight']:+.1f}）"
        )

    # 第三层：背离检测
    alerts = _detect_divergence(consensus, sh_pct, signals)
    if alerts:
        lines.append("├─ ⚠️ 背离信号：")
        for a in alerts:
            lines.append(f"│  ‼ {a}")
    else:
        lines.append("├─ 背离检测：无显著背离")

    # 边际变化
    marginal = _marginal_change(consensus)
    lines.append(f"└─ 边际变化：{marginal}")

    diagnosis_text = "\n".join(lines)

    logger.info(
        f"外部共识: score={score:+.1f} conf={confidence} "
        f"bull={bull} bear={bear} alerts={len(alerts)}"
    )

    return {
        "diagnosis_text": diagnosis_text,
        "consensus_score": score,
        "consensus_confidence": confidence,
        "divergence_alerts": alerts,
        "signals": signals,
    }
