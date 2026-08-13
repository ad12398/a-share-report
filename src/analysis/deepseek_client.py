"""DeepSeek API 客户端"""

import logging
import os
import time

import requests

logger = logging.getLogger("a-share-report")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MAX_RETRIES = 3
TIMEOUT = 60
RETRY_BACKOFF_SECONDS = 5  # 重试退避间隔


class ReportGenerationError(Exception):
    """报告生成失败（重试后仍失败），调用方应写错误页而非发布错误文案当报告"""


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

    last_reasoning = ""  # 最后一次响应中的思考内容（兜底用）

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "") or ""
            reasoning = message.get("reasoning_content", "") or ""
            usage = data.get("usage", {})

            # 模型可能把分析放在 reasoning_content（思考模式），content 为空
            if not content.strip() and reasoning.strip():
                last_reasoning = reasoning
                logger.warning(
                    f"DeepSeek 返回空 content，reasoning_content={len(reasoning)} 字。"
                    f"模型进入思考模式未输出正文 (attempt {attempt + 1}/{MAX_RETRIES})。"
                )
                if attempt == MAX_RETRIES - 1:
                    logger.warning("所有重试均为空 content，使用 reasoning_content 兜底。")
                    return reasoning  # 兜底：思考内容也比空报告强
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue  # 重试

            logger.info(
                f"DeepSeek API 调用成功 "
                f"(input={usage.get('prompt_tokens', 0)}, "
                f"output={usage.get('completion_tokens', 0)}, "
                f"content={len(content)} 字, reasoning={len(reasoning)} 字)"
            )
            return content
        except requests.exceptions.Timeout:
            logger.warning(f"DeepSeek API 超时 (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES - 1:
                raise ReportGenerationError(f"API 连续 {MAX_RETRIES} 次超时") from None
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
        except requests.exceptions.HTTPError as e:
            logger.error(f"DeepSeek API HTTP 错误: {e}")
            if attempt == MAX_RETRIES - 1:
                raise ReportGenerationError(f"API HTTP 错误: {e}") from None
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
        except Exception as e:
            logger.error(f"DeepSeek API 未知错误: {e}")
            if attempt == MAX_RETRIES - 1:
                raise ReportGenerationError(f"API 未知错误: {e}") from None
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    # 所有重试都因空 content 而失败
    if last_reasoning.strip():
        logger.warning("所有重试均为空 content，使用 reasoning_content 兜底。")
        return last_reasoning
    raise ReportGenerationError("无法获取分析结果（空响应）")
