"""环境变量配置。所有敏感值只从环境或本地 .env 读取。"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ROOT / ".env"), str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CareerPilot AI"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    default_user_id: str = "demo-user"

    database_url: str = (
        "postgresql://careerpilot:change-me-careerpilot@localhost:5433/careerpilot"
    )
    test_database_url: str = (
        "postgresql://careerpilot:change-me-careerpilot@localhost:5433/careerpilot_test"
    )
    db_pool_min_size: int = Field(default=1, ge=0)
    db_pool_max_size: int = Field(default=5, ge=1)
    db_pool_timeout: float = Field(default=10.0, gt=0)

    llm_provider: str = "zhipu"
    llm_mode: Literal["mock", "real"] = "mock"
    llm_model: str = "glm-4.7-flash"
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_api_key: str = ""
    llm_timeout: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_tokens: int = Field(default=4096, ge=1, le=65536)
    llm_temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    llm_thinking: Literal["enabled", "disabled"] = "enabled"
    llm_reasoning_effort: str | None = None

    resume_storage_dir: str = ""
    resume_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    resume_max_text_chars: int = Field(default=20000, ge=1000, le=200000)

    checkpoint_backend: str = "memory"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
