"""
LLM API 客户端封装。
支持 OpenAI-compatible API（Kimi / OpenAI / DeepSeek / OpenRouter / 本地 vLLM）
和 Anthropic Messages API（原生 Claude）。
"""

import asyncio
from typing import Optional

import httpx

from src.config import LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT
from src.llm import prompts


_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


def _build_headers() -> dict:
    if LLM_PROVIDER == "anthropic":
        return {
            "x-api-key": LLM_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    return {
        "authorization": f"Bearer {LLM_API_KEY}",
        "content-type": "application/json",
    }


def _build_payload(system: str, user: str) -> dict:
    if LLM_PROVIDER == "anthropic":
        return {
            "model": LLM_MODEL,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    # OpenAI-compatible
    return {
        "model": LLM_MODEL,
        "temperature": 1,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def _extract_content(body: dict) -> Optional[str]:
    if LLM_PROVIDER == "anthropic":
        content = body.get("content", [])
        if content:
            return content[0].get("text", "")
        return None
    # OpenAI-compatible
    choices = body.get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content", "")


async def _call_api(system: str, user: str) -> str:
    """发起一次 API 调用，含重试逻辑。"""
    headers = _build_headers()
    payload = _build_payload(system, user)

    if LLM_PROVIDER == "anthropic":
        url = f"{LLM_BASE_URL.rstrip('/')}/messages"
    else:
        url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT, connect=15)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                body = resp.json()
                content = _extract_content(body)
                if content is None:
                    raise ValueError(f"无法从响应中提取内容: {body}")
                return content
        except httpx.HTTPStatusError as exc:
            try:
                err_body = exc.response.json()
            except Exception:
                err_body = exc.response.text
            print(f"[LLM] HTTP {exc.response.status_code} error: {err_body}")
            last_error = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY * attempt)
            continue
        except Exception as exc:
            print(f"[LLM] Request error ({type(exc).__name__}): {exc}")
            last_error = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY * attempt)
            continue

    raise last_error if last_error else RuntimeError("LLM API 调用失败，未知错误")


async def score_record(record: dict) -> dict:
    """
    调用 LLM 对单份病历进行评分。

    Returns:
        解析后的评分结果字典，结构与 engine.py 的 evaluate_record 输出一致。
        若解析失败则抛出异常，由调用方回退到规则评分。
    """
    system_msg = prompts.get_system_message()
    user_msg = prompts.build_scoring_prompt(record)

    raw_response = await _call_api(system_msg, user_msg)

    from src.llm.parser import parse_scoring_response
    return parse_scoring_response(raw_response)


def is_configured() -> bool:
    """检查 LLM 配置是否完整（有 API Key 且 Provider 合法）。"""
    if not LLM_API_KEY:
        return False
    valid_providers = ("moonshot", "anthropic", "openai", "deepseek", "openrouter")
    return LLM_PROVIDER in valid_providers or LLM_PROVIDER.startswith("custom_")
