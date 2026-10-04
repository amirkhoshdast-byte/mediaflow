from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://ncr:change-me-db@db:5432/ncr"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str
    encryption_key: str = ""
    cookie_secure: bool = False
    session_hours: int = 8
    max_failed_attempts: int = 5
    lock_minutes: int = 15

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""

    # AI gateway
    ai_provider_classify: str = "ollama"
    ai_provider_generate: str = "anthropic"
    ai_provider_sensitive: str = "ollama"
    ai_timeout_seconds: float = 60.0

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_model: str = ""
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Daily targets shown in the header band
    target_posts_per_day: int = 3
    target_replies_per_day: int = 5
    timezone: str = "Asia/Tehran"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
