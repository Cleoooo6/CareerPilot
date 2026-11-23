"""统一 LLM Client。

- 业务节点只依赖本模块，不绑定具体供应商。
- 支持 mock / real 两种模式；阶段一默认 mock，不发起真实请求。
- real 模式通过 OpenAI 兼容 /chat/completions 调用智谱 GLM。
- 只有显式配置 API Key 且 LLM_MODE=real 时才会发起网络请求。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Generic, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import redact

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMError(AppError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(code, message, status_code=status_code)


class LLMNotConfiguredError(LLMError):
    def __init__(self, message: str = "LLM 未配置：缺少 LLM_API_KEY") -> None:
        super().__init__("LLM_NOT_CONFIGURED", message, status_code=503)


class LLMRetryableError(LLMError):
    def __init__(
        self,
        message: str,
        *,
        retry_exhausted: bool = False,
        status_code: int = 502,
    ) -> None:
        super().__init__("LLM_RETRYABLE_ERROR", message, status_code=status_code)
        self.retry_exhausted = retry_exhausted


class LLMRateLimitError(LLMRetryableError):
    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        retry_exhausted: bool = False,
    ) -> None:
        super().__init__(message, retry_exhausted=retry_exhausted, status_code=429)
        self.retry_after = retry_after


class LLMTimeoutError(LLMRetryableError):
    def __init__(self, message: str = "LLM 请求超时") -> None:
        super().__init__(message, status_code=504)


class LLMServerError(LLMRetryableError):
    pass


class LLMNonRetryableError(LLMError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__("LLM_NON_RETRYABLE_ERROR", message, status_code=status_code)


class LLMOutputTruncatedError(LLMNonRetryableError):
    def __init__(self, message: str = "LLM 输出被 max_tokens 截断") -> None:
        super().__init__("LLM_OUTPUT_TRUNCATED", message)


class LLMSchemaError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("LLM_SCHEMA_ERROR", message)


class LLMUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model: str = ""
    finish_reason: str | None = None


class LLMStreamChunk(BaseModel):
    content: str = ""
    model: str = ""
    finish_reason: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)


@dataclass
class StructuredResult(Generic[SchemaT]):
    value: SchemaT
    usage: LLMUsage
    model: str
    finish_reason: str | None


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class LLMClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
        async_http_client: httpx.AsyncClient | None = None,
        mock_text: str | None = None,
        mock_payload: dict[str, Any] | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._http = http_client
        self._async_http = async_http_client
        self._mock_text = mock_text
        self._mock_payload = mock_payload
        self._sleep = sleep_func

    @property
    def mode(self) -> str:
        return self.settings.llm_mode

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.settings.llm_provider,
            "mode": self.settings.llm_mode,
            "model": self.settings.llm_model,
            "base_url": self.settings.llm_base_url,
            "api_key_configured": bool(self.settings.llm_api_key),
            "real_calls_enabled": self.settings.llm_mode == "real",
        }

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        if self.mode == "mock":
            return self._mock_text or f"【Mock LLM】{user_prompt.strip()}"
        response = self.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        if not response.content.strip():
            raise LLMSchemaError("LLM 返回空文本")
        return response.content.strip()

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT:
        return self.complete_structured_with_meta(system_prompt, user_prompt, schema).value

    def complete_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        *,
        mock_payload: dict[str, Any] | None = None,
    ) -> StructuredResult[SchemaT]:
        if self.mode == "mock":
            payload = mock_payload if mock_payload is not None else self._mock_payload
            if payload is None:
                raise LLMNotConfiguredError(
                    "Mock 模式未提供 mock_payload；业务节点必须提供确定性 Mock 数据"
                )
            return StructuredResult(
                value=schema.model_validate(payload),
                usage=LLMUsage(),
                model=self.settings.llm_model,
                finish_reason="stop",
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        last_error: Exception | None = None
        for attempt in range(1, self.settings.llm_max_retries + 2):
            try:
                response = self.chat(
                    messages,
                    response_format={"type": "json_object"},
                )
                payload = json.loads(_strip_code_fence(response.content))
                return StructuredResult(
                    value=schema.model_validate(payload),
                    usage=response.usage,
                    model=response.model,
                    finish_reason=response.finish_reason,
                )
            except (LLMNotConfiguredError, LLMNonRetryableError):
                raise
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt > self.settings.llm_max_retries:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一次输出未通过 JSON 或字段校验，请只输出完整 JSON 对象。"
                            f"错误摘要：{redact(str(exc))[:300]}"
                        ),
                    }
                )
        raise LLMSchemaError(
            "LLM 结构化输出失败："
            + redact(str(last_error) if last_error else "未知错误")
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self.mode == "mock":
            return LLMResponse(
                content=self._mock_text or "",
                model=self.settings.llm_model,
                finish_reason="stop",
            )
        self._require_real_config()
        attempts = 1 + self.settings.llm_max_retries
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self._post_once(
                    messages, response_format=response_format, tools=tools
                )
            except LLMRateLimitError as exc:
                last_error = exc
                if exc.retry_after is None or attempt >= attempts:
                    raise LLMRateLimitError(
                        f"{exc}（限流停止；已尝试 {attempt} 次）",
                        retry_after=exc.retry_after,
                        retry_exhausted=attempt >= attempts,
                    ) from exc
                self._sleep(min(exc.retry_after, 30.0))
            except (LLMTimeoutError, LLMServerError, LLMRetryableError) as exc:
                last_error = exc
                if attempt >= attempts:
                    raise LLMRetryableError(
                        f"{exc}（已重试 {self.settings.llm_max_retries} 次仍失败）",
                        retry_exhausted=True,
                    ) from exc
                self._sleep(min(2 ** (attempt - 1), 8))
        raise LLMRetryableError(
            f"LLM 调用失败：{redact(str(last_error) if last_error else '未知错误')}",
            retry_exhausted=True,
        )

    def _require_real_config(self) -> None:
        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", self.settings.llm_api_key),
                ("LLM_MODEL", self.settings.llm_model),
                ("LLM_BASE_URL", self.settings.llm_base_url),
            )
            if not value
        ]
        if missing:
            raise LLMNotConfiguredError(f"LLM 未配置：缺少 {', '.join(missing)}")

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        response_format: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
            "stream": stream,
        }
        if self.settings.llm_provider == "zhipu":
            payload["thinking"] = {"type": self.settings.llm_thinking}
            if self.settings.llm_reasoning_effort:
                payload["reasoning_effort"] = self.settings.llm_reasoning_effort
        if response_format is not None:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _post_once(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        payload = self._build_payload(
            messages,
            stream=False,
            response_format=response_format,
            tools=tools,
        )

        started = time.perf_counter()
        try:
            client = self._http or httpx.Client(timeout=self.settings.llm_timeout)
            response = client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.llm_timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM 请求超时") from exc
        except httpx.HTTPError as exc:
            raise LLMRetryableError(f"LLM 网络错误：{redact(str(exc))}") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                "LLM 服务返回 HTTP 429 限流",
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )
        if 500 <= response.status_code <= 599:
            raise LLMServerError(f"LLM 服务返回 HTTP {response.status_code}")
        if response.status_code >= 400:
            raise LLMNonRetryableError(
                f"LLM 服务拒绝请求 HTTP {response.status_code}："
                f"{redact(response.text[:200])}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMRetryableError("LLM 响应不是合法 JSON") from exc

        choices = data.get("choices") or []
        if not choices:
            raise LLMRetryableError("LLM 响应缺少 choices")
        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise LLMOutputTruncatedError(
                f"LLM 输出被 max_tokens={self.settings.llm_max_tokens} 截断"
            )
        if finish_reason == "sensitive":
            raise LLMNonRetryableError("LLM 输出被内容安全审核拦截")
        if finish_reason == "model_context_window_exceeded":
            raise LLMNonRetryableError("LLM 输入超出上下文窗口")

        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        result = LLMResponse(
            content=message.get("content") or "",
            tool_calls=message.get("tool_calls") or [],
            usage=LLMUsage(
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ),
            model=str(data.get("model") or self.settings.llm_model),
            finish_reason=finish_reason,
        )
        logger.info(
            "llm_call",
            extra={
                "event": "llm_call",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return result


    def _raise_http_error(
        self,
        status_code: int,
        body: str,
        headers: httpx.Headers,
    ) -> None:
        if status_code == 429:
            raise LLMRateLimitError(
                "LLM 服务返回 HTTP 429 限流",
                retry_after=_parse_retry_after(headers.get("Retry-After")),
            )
        if 500 <= status_code <= 599:
            raise LLMServerError(f"LLM 服务返回 HTTP {status_code}")
        raise LLMNonRetryableError(
            f"LLM 服务拒绝请求 HTTP {status_code}：{redact(body[:200])}"
        )

    async def astream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        mock_text: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """真实 Token 流式接口。

        Mock 模式只产生明确标注的本地文本分片，不伪造真实 token 用量；
        Real 模式必须收到 SSE 流，非 SSE 响应会明确报错，不静默降级。
        """
        if self.mode == "mock":
            text = mock_text if mock_text is not None else (self._mock_text or "")
            if not text:
                text = "【Mock LLM】当前为 Mock 模式，未调用真实模型。"
            for index in range(0, len(text), 12):
                yield LLMStreamChunk(
                    content=text[index : index + 12],
                    model=self.settings.llm_model,
                )
            yield LLMStreamChunk(
                model=self.settings.llm_model,
                finish_reason="stop",
                usage=LLMUsage(),
            )
            return

        self._require_real_config()
        attempts = 1 + self.settings.llm_max_retries
        for attempt in range(1, attempts + 1):
            emitted_content = False
            try:
                async for chunk in self._astream_once(
                    messages,
                    response_format=response_format,
                    tools=tools,
                    max_tokens=max_tokens,
                ):
                    if chunk.content:
                        emitted_content = True
                    yield chunk
                return
            except LLMRateLimitError as exc:
                if (
                    emitted_content
                    or exc.retry_after is None
                    or attempt >= attempts
                ):
                    raise LLMRateLimitError(
                        f"{exc}（限流停止；已尝试 {attempt} 次）",
                        retry_after=exc.retry_after,
                        retry_exhausted=attempt >= attempts,
                    ) from exc
                await asyncio.sleep(min(exc.retry_after, 30.0))
            except (LLMTimeoutError, LLMServerError, LLMRetryableError) as exc:
                if emitted_content or attempt >= attempts:
                    raise LLMRetryableError(
                        f"{exc}（流式重试 {attempt - 1} 次仍失败）",
                        retry_exhausted=True,
                    ) from exc
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

    async def _astream_once(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = self._build_payload(
            messages,
            stream=True,
            response_format=response_format,
            tools=tools,
            max_tokens=max_tokens,
        )
        started = time.perf_counter()
        client = self._async_http
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.llm_timeout)
            close_client = True
        try:
            async with client.stream(
                "POST",
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.llm_timeout,
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(
                        "utf-8", errors="replace"
                    )
                    self._raise_http_error(
                        response.status_code, body, response.headers
                    )

                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type.lower():
                    body = (await response.aread()).decode(
                        "utf-8", errors="replace"
                    )
                    raise LLMNonRetryableError(
                        "LLM Provider 未返回 SSE 流；拒绝把一次性响应伪装为流式输出。"
                        f"响应摘要：{redact(body[:200])}"
                    )

                model = self.settings.llm_model
                usage = LLMUsage()
                finish_reason: str | None = None
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if not data_text or data_text == "[DONE]":
                        continue
                    try:
                        data = json.loads(data_text)
                    except json.JSONDecodeError as exc:
                        raise LLMRetryableError(
                            "LLM 流式响应包含非法 JSON"
                        ) from exc
                    model = str(data.get("model") or model)
                    usage_data = data.get("usage") or {}
                    if usage_data:
                        usage = LLMUsage(
                            prompt_tokens=usage_data.get("prompt_tokens"),
                            completion_tokens=usage_data.get("completion_tokens"),
                            total_tokens=usage_data.get("total_tokens"),
                        )
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta") or {}
                    content = delta.get("content") or ""
                    if content:
                        yield LLMStreamChunk(content=content, model=model)
                    if finish_reason == "sensitive":
                        raise LLMNonRetryableError(
                            "LLM 输出被内容安全审核拦截"
                        )
                    if finish_reason == "model_context_window_exceeded":
                        raise LLMNonRetryableError(
                            "LLM 输入超出上下文窗口"
                        )

                yield LLMStreamChunk(
                    model=model,
                    finish_reason=finish_reason,
                    usage=usage,
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM 流式请求超时") from exc
        except httpx.HTTPError as exc:
            raise LLMRetryableError(
                f"LLM 流式网络错误：{redact(str(exc))}"
            ) from exc
        finally:
            if close_client:
                await client.aclose()

        logger.info(
            "llm_stream_call",
            extra={
                "event": "llm_stream_call",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )


def get_llm_client() -> LLMClient:
    return LLMClient()
