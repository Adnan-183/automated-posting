"""Settings loaded from environment variables or .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    http_timeout_seconds: float = 15.0
    verify_public_access: bool = True

    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None
    bluesky_service_url: str = "https://bsky.social"

    mastodon_instance_url: str | None = None
    mastodon_access_token: str | None = None

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    github_token: str | None = None

    devto_api_key: str | None = None

    discord_webhook_url: str | None = None

    rentry_edit_code: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
