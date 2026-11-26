"""环境变量配置。所有敏感值只从环境或本地 .env 读取。"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    # Auth/session configuration. Production defaults are secure; tests may
    # explicitly set the test-only flags.
    auth_session_cookie: str = "cp_session"
    auth_csrf_cookie: str = "cp_csrf"
    auth_session_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=300)
    auth_cookie_secure: bool = True
    auth_csrf_enabled: bool = True
    auth_login_max_attempts: int = Field(default=10, ge=1, le=100)
    auth_login_window_seconds: int = Field(default=300, ge=1, le=3600)
    # Test-only compatibility for the existing isolated pytest/E2E harness.
    # Production rejects this mode unless APP_ENV=test.
    auth_test_mode: bool = False
    auth_email_from: str = ""
    auth_email_configured: bool = False
    auth_public_base_url: str = "http://localhost:5180"
    resume_ttl_hours: int = Field(default=24, ge=1, le=24 * 30)

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

    industry_pulse_ai_enabled: bool = False
    industry_pulse_fetch_timeout: float = Field(default=10.0, gt=0, le=60)
    industry_pulse_max_items_per_feed: int = Field(default=20, ge=1, le=100)
    industry_pulse_max_feed_bytes: int = Field(default=3_000_000, ge=100_000)
    industry_pulse_refresh_cooldown: int = Field(default=60, ge=0, le=3600)
    industry_pulse_collect_timeout: float = Field(default=90.0, gt=0, le=300)
    industry_pulse_user_agent: str = "CareerPilot/0.1 (+local RSS reader)"

    @model_validator(mode="after")
    def _guard_auth_cookie_settings(self) -> "Settings":
        if self.auth_test_mode and self.app_env != "test":
            raise ValueError("AUTH_TEST_MODE 仅允许在 APP_ENV=test 时启用")
        if os.getenv("AUTH_COOKIE_SECURE") is None:
            # Derive the default from the public scheme: HTTPS deployments get
            # Secure cookies automatically, plain HTTP stays usable in local
            # deployments (where Secure cookies would never be sent).
            self.auth_cookie_secure = self.auth_public_base_url.startswith("https://")
        if (
            self.app_env == "production"
            and self.auth_public_base_url.startswith("https://")
            and not self.auth_cookie_secure
        ):
            raise ValueError("HTTPS 部署必须启用 AUTH_COOKIE_SECURE")
        return self

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
