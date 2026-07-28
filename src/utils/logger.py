"""日志工具模块"""

import logging
import sys
from datetime import datetime


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
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def report_time() -> str:
    """返回当前北京时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
