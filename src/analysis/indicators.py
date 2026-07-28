"""技术指标计算 —— 量化分析用"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger("a-share-report")


def calc_ma(prices: list[float], period: int = 20) -> float | None:
    """计算移动均线"""
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def calc_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Any]:
    """计算 MACD 指标"""
    if len(prices) < slow + signal:
        return {"dif": None, "dea": None, "macd": None, "signal": "insufficient_data"}

    # EMA 计算
    def _ema(data: list[float], period: int) -> np.ndarray:
        alpha = 2 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    prices_arr = np.array(prices, dtype=float)
    ema_fast = _ema(prices_arr, fast)
    ema_slow = _ema(prices_arr, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    macd = 2 * (dif - dea)

    latest_dif = float(dif[-1])
    latest_dea = float(dea[-1])
    latest_macd = float(macd[-1])

    signal_type = "多头" if latest_dif > latest_dea else "空头"
    if latest_macd > 0:
        signal_type += "，红柱（加速）" if latest_macd > dif[-2] - dea[-2] else "，红柱（减速）"
    else:
        signal_type += "，绿柱（加速）" if latest_macd < dif[-2] - dea[-2] else "，绿柱（减速）"

    return {
        "dif": round(latest_dif, 4),
        "dea": round(latest_dea, 4),
        "macd": round(latest_macd, 4),
        "signal": signal_type,
    }


def calc_rsi(prices: list[float], period: int = 14) -> float | None:
    """计算 RSI 指标"""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices[-period - 1:])
    gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0
    losses = -np.sum(deltas[deltas < 0]) if np.any(deltas < 0) else 0
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(float(100 - 100 / (1 + rs)), 2)


def calc_kdj(prices: list[float], highs: list[float], lows: list[float], period: int = 9) -> dict[str, Any]:
    """计算 KDJ 指标"""
    if len(prices) < period:
        return {"k": None, "d": None, "j": None, "signal": "insufficient_data"}

    # 最近一个周期
    recent_high = max(highs[-period:])
    recent_low = min(lows[-period:])

    if recent_high == recent_low:
        rsv = 50
    else:
        rsv = (prices[-1] - recent_low) / (recent_high - recent_low) * 100

    # 简化版 KDJ（单点计算）
    k = rsv * 1 / 3 + 50 * 2 / 3
    d = k * 1 / 3 + 50 * 2 / 3
    j = 3 * k - 2 * d

    k_signal = "超买" if k > 80 else ("超卖" if k < 20 else "中性")
    return {
        "k": round(k, 2),
        "d": round(d, 2),
        "j": round(j, 2),
        "signal": k_signal,
    }


def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """计算 ATR（平均真实波幅）"""
    if len(closes) < period + 1:
        return None
    tr_list = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    return round(float(np.mean(tr_list[-period:])), 2) if tr_list else None
