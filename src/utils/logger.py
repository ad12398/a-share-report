"""日志工具模块"""

import logging
import sys
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))


def setup_logger(name: str = "a-share-report") -> logging.Logger:
    """配置并返回 logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # logging 的 asctime 默认用本地时间，改为北京时间
        formatter.converter = lambda *args: datetime.now(BEIJING_TZ).timetuple()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def report_time() -> str:
    """返回当前北京时间字符串"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
