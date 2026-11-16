"""Application settings, loaded from environment variables (or a local `.env` file).

Every credential is optional: a platform whose credentials are missing is still
reported in the response, as `failed` with a "not configured" error, so one
missing key never stops the other platforms from posting.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    http_timeout_seconds: float = 15.0
    # After posting, open each URL without credentials and report
    # public_access=true only if it actually loads.
    verify_public_access: bool = True

    # Bluesky (AT Protocol) - https://docs.bsky.app/docs/get-started
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None
    bluesky_service_url: str = "https://bsky.social"

    # Mastodon - https://docs.joinmastodon.org/methods/statuses/#create
    mastodon_instance_url: str | None = None
    mastodon_access_token: str | None = None

    # Telegram Bot API - https://core.telegram.org/bots/api#sendmessage
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None  # e.g. "@my_public_channel"

    # GitHub Gists - https://docs.github.com/en/rest/gists/gists#create-a-gist
    github_token: str | None = None

    # DEV Community (Forem) - https://developers.forem.com/api/v1#tag/articles
    devto_api_key: str | None = None

    # Discord webhooks - https://discord.com/developers/docs/resources/webhook#execute-webhook
    discord_webhook_url: str | None = None

    # Rentry - https://github.com/radude/rentry#usage-api (no account needed)
    rentry_edit_code: str | None = None  # optional: lets you edit/delete pages later


@lru_cache
def get_settings() -> Settings:
    return Settings()
