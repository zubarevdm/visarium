from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    webhook_url: str = ""
    webhook_secret: str = ""

    # LLM: anthropic (прямой Anthropic API) | openai_compatible (Polza.AI и другие агрегаторы)
    llm_provider: str = "openai_compatible"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.polza.ai/api/v1"
    llm_model: str = "openai/gpt-5.4-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    database_url: str = "postgresql+asyncpg://legal:legal@localhost:5432/legal"
    redis_url: str = "redis://localhost:6379/0"

    sentry_dsn: str = ""

    embedding_backend: str = "local"  # local | fake
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384

    # Платежи: false — сервис полностью бесплатный (Stars-подписка отключена).
    # Позже включить обратно (true) при подключении оплаты (ЮKassa/Stars).
    payments_enabled: bool = False

    subscription_price_stars: int = 250
    subscription_period_days: int = 30

    rate_limit_per_minute: int = 20

    reminder_hour_utc: int = 6  # ~9:00 МСК


@lru_cache
def get_settings() -> Settings:
    return Settings()
