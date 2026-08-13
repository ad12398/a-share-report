"""A 股交易日历 —— 判断今天是否为交易日"""

from datetime import datetime, date, timezone, timedelta
import logging

logger = logging.getLogger("a-share-report")

BEIJING_TZ = timezone(timedelta(hours=8))

# A 股 2026 年节假日休市安排（需每年更新）
# 来源：上交所/深交所公告
HOLIDAYS_2026: set[str] = set()

# 春节: 2026-02-16(除夕) 至 2026-02-24，共 7 个交易日
_spring_festival = ["2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19",
                    "2026-02-20", "2026-02-23", "2026-02-24"]
# 清明节: 2026-04-05, 2026-04-06
_qingming = ["2026-04-05", "2026-04-06"]
# 劳动节: 2026-05-01, 2026-05-04, 2026-05-05
_labor = ["2026-05-01", "2026-05-04", "2026-05-05"]
# 端午节: 2026-06-19
_dragon = ["2026-06-19"]
# 中秋节: 2026-09-25
_mid_autumn = ["2026-09-25"]
# 国庆节: 2026-10-01 至 2026-10-07
_national = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"]

for _holidays in [_spring_festival, _qingming, _labor, _dragon, _mid_autumn, _national]:
    HOLIDAYS_2026.update(_holidays)


def is_trading_day(check_date: date | None = None) -> bool:
    """
    判断是否为 A 股交易日。

    规则：
    1. 非周六周日
    2. 非法定节假日休市日
    """
    if check_date is None:
        # 用北京时间判断今天（服务器可能不在中国时区）
        check_date = datetime.now(BEIJING_TZ).date()

    # 周末不交易
    if check_date.weekday() >= 5:  # 5=周六, 6=周日
        return False

    # 节假日不交易
    date_str = check_date.strftime("%Y-%m-%d")
    if date_str in HOLIDAYS_2026:
        logger.info(f"{date_str} 是节假日休市日，跳过")
        return False

    return True


def get_current_slot() -> str | None:
    """
    根据当前北京时间判断处于哪个报告时段。
    返回: "0925" | "1030" | "1130" | "1400" | "1500" | None
    """
    from datetime import datetime, timezone, timedelta

    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)

    if not is_trading_day(now.date()):
        return None

    hour = now.hour
    minute = now.minute

    # 盘前简报 9:20–9:30
    if hour == 9 and 20 <= minute <= 30:
        return "0925"
    # 早盘分析 10:25–10:35
    if hour == 10 and 25 <= minute <= 35:
        return "1030"
    # 午盘总结 11:25–11:35
    if hour == 11 and 25 <= minute <= 35:
        return "1130"
    # 午后更新 13:55–14:05
    if (hour == 13 and minute >= 55) or (hour == 14 and minute <= 5):
        return "1400"
    # 收盘报告 14:55–15:05
    if (hour == 14 and minute >= 55) or (hour == 15 and minute <= 5):
        return "1500"

    return None
