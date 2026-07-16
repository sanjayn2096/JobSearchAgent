"""Typed configuration. Fails loudly at startup, never mid-request."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "job-application-agent"
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    openrouter_api_key: str = Field(default="", description="Required unless using FakeLLM")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    llm_timeout_seconds: float = 45.0

    # Job sources. Empty key = source is skipped at wiring time.
    jsearch_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    use_fake_llm: bool = False
    use_mock_sources: bool = False

    per_source_timeout_seconds: float = 20.0
    max_results_default: int = 25


@lru_cache
def get_settings() -> Settings:
    return Settings()
