"""Unified AI service layer.

All business modules call models through this class so that:
- prompts carry explicit versions;
- every real/mock call is audited with user, purpose, model, duration and usage;
- failures surface as typed LLM errors instead of silent fallbacks.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.ai.prompts import PromptSpec
from app.core.llm import LLMClient, LLMError, LLMUsage, get_llm_client
from app.db.ai_repository import AIRepository, ai_repository

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class AIResultMeta:
    provider: str
    model: str
    prompt_key: str
    prompt_version: str
    duration_ms: int
    usage: LLMUsage
    finish_reason: str | None
    llm_mode: str


class AIService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        repository: AIRepository | None = None,
    ) -> None:
        self.llm = llm_client or get_llm_client()
        self.repository = repository or ai_repository
        self.settings = self.llm.settings

    @property
    def mode(self) -> str:
        return self.llm.mode

    def structured(
        self,
        *,
        user_id: UUID,
        purpose: str,
        prompt: PromptSpec,
        user_prompt: str,
        schema: type[SchemaT],
        mock_payload: dict[str, Any] | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
    ) -> tuple[SchemaT, AIResultMeta]:
        started = time.perf_counter()
        try:
            result = self.llm.complete_structured_with_meta(
                prompt.system,
                user_prompt,
                schema,
                mock_payload=mock_payload,
            )
        except LLMError as exc:
            self._log(
                user_id=user_id,
                purpose=purpose,
                prompt=prompt,
                status="failed",
                error_code=exc.code,
                duration_ms=self._elapsed_ms(started),
                source_type=source_type,
                source_id=source_id,
            )
            raise
        meta = AIResultMeta(
            provider=self.settings.llm_provider,
            model=result.model or self.settings.llm_model,
            prompt_key=prompt.key,
            prompt_version=prompt.version,
            duration_ms=self._elapsed_ms(started),
            usage=result.usage,
            finish_reason=result.finish_reason,
            llm_mode=self.mode,
        )
        self._log(
            user_id=user_id,
            purpose=purpose,
            prompt=prompt,
            status="succeeded",
            duration_ms=meta.duration_ms,
            usage=result.usage,
            source_type=source_type,
            source_id=source_id,
        )
        return result.value, meta

    def record_stream(
        self,
        *,
        user_id: UUID,
        purpose: str,
        prompt: PromptSpec,
        model: str,
        duration_ms: int,
        usage: LLMUsage | None,
        status: str = "succeeded",
        error_code: str | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
    ) -> None:
        self._log(
            user_id=user_id,
            purpose=purpose,
            prompt=prompt,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
            usage=usage,
            model=model,
            source_type=source_type,
            source_id=source_id,
        )

    def _log(
        self,
        *,
        user_id: UUID,
        purpose: str,
        prompt: PromptSpec,
        status: str,
        duration_ms: int,
        usage: LLMUsage | None = None,
        error_code: str | None = None,
        model: str | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
    ) -> None:
        self.repository.record(
            user_id=user_id,
            purpose=purpose,
            provider=self.settings.llm_provider,
            model=model or self.settings.llm_model,
            llm_mode=self.mode,
            prompt_version=prompt.version,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
            usage=usage,
            source_type=source_type,
            source_id=source_id,
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


def reset_ai_service() -> None:
    global _ai_service
    _ai_service = None
