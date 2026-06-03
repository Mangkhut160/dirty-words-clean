"""LLM API 封装 — OpenAI 兼容格式，异步调用 + 重试机制。"""
import asyncio
import time
from openai import AsyncOpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

MAX_RETRIES = 2


def get_client():
    if not LLM_API_KEY:
        return None
    return AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


async def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """异步调用 LLM，空响应自动重试最多 MAX_RETRIES 次。"""
    client = get_client()
    if not client:
        return _mock_response(system_prompt, user_prompt)

    start = time.time()
    last_error = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            if not content.strip() and attempt < MAX_RETRIES:
                last_error = "empty_response"
                await asyncio.sleep(0.5)
                continue

            latency_ms = int((time.time() - start) * 1000)
            return {
                "content": content,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "latency_ms": latency_ms,
                "retries": attempt,
            }
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)
                continue

            latency_ms = int((time.time() - start) * 1000)
            return {
                "content": f"[LLM 调用失败] {last_error}",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latency_ms": latency_ms,
                "retries": attempt,
            }

    latency_ms = int((time.time() - start) * 1000)
    return {
        "content": f"[LLM 重试耗尽] {last_error}",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": latency_ms,
        "retries": MAX_RETRIES,
    }


def _mock_response(system_prompt: str, user_prompt: str) -> dict:
    """Mock 模式 — 无 API key 时用规则生成近似结果。"""
    sys_tokens = len(system_prompt) // 2
    user_tokens = len(user_prompt) // 2
    output = "[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容\n\n客户反馈对产品不满意，要求处理。"
    comp_tokens = len(output) // 2

    return {
        "content": output,
        "prompt_tokens": sys_tokens + user_tokens,
        "completion_tokens": comp_tokens,
        "total_tokens": sys_tokens + user_tokens + comp_tokens,
        "latency_ms": 50,
    }
