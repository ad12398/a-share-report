"""DeepSeek API 客户端"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("a-share-report")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MAX_RETRIES = 3
TIMEOUT = 60


def get_api_key() -> str:
    """获取 DeepSeek API Key（仅从环境变量读取）"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 环境变量未设置。"
            "请在 GitHub Secrets 或本地 .env 中设置。"
        )
    return key


def generate_report(
    system_prompt: str,
    user_prompt: str,
    model: str = "deepseek-v4-pro",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    调用 DeepSeek API 生成报告文本。

    参数:
        system_prompt: 系统级提示词
        user_prompt: 用户数据提示词
        model: 模型名称
        temperature: 生成温度（量化分析建议 0.3）
        max_tokens: 最大输出 token 数

    返回:
        生成的报告文本
    """
    api_key = get_api_key()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            logger.info(
                f"DeepSeek API 调用成功 "
                f"(input={usage.get('prompt_tokens', 0)}, "
                f"output={usage.get('completion_tokens', 0)})"
            )
            return content
        except requests.exceptions.Timeout:
            logger.warning(f"DeepSeek API 超时 (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES - 1:
                return "⚠️ API 调用超时，请稍后重试。"
        except requests.exceptions.HTTPError as e:
            logger.error(f"DeepSeek API HTTP 错误: {e}")
            if attempt == MAX_RETRIES - 1:
                return f"⚠️ API 调用失败: {e}"
        except Exception as e:
            logger.error(f"DeepSeek API 未知错误: {e}")
            if attempt == MAX_RETRIES - 1:
                return f"⚠️ API 调用异常: {e}"

    return "⚠️ 无法获取分析结果。"


def format_data_for_prompt(data: dict[str, Any]) -> str:
    """将结构化行情数据格式化为可注入 prompt 的文本"""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
