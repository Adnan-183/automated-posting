"""Common interface every platform integration implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import httpx

from app.config import Settings


@dataclass
class PublishedPost:
    """What a platform returns after a successful publish."""

    url: str | None
    public_access: bool


class PlatformError(Exception):
    """A platform rejected the post or returned something unusable.

    The message is shown to API callers, so it must never contain credentials.
    """


class Platform(ABC):
    #: Human-readable name used in the API response.
    name: ClassVar[str]
    #: Settings attributes that must be set for this platform to run.
    required_settings: ClassVar[tuple[str, ...]]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def missing_settings(self) -> list[str]:
        """Environment variable names that are required but empty."""
        return [
            field.upper()
            for field in self.required_settings
            if not getattr(self.settings, field)
        ]

    @abstractmethod
    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        """Publish `message` and return where it was posted."""


def raise_for_api_error(response: httpx.Response) -> None:
    """Turn a non-2xx response into a PlatformError with the API's own reason.

    The request URL is deliberately left out: some APIs (Telegram) put the
    token in the URL, and this message is returned to API callers.
    """
    if response.is_success:
        return

    detail = None
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        for key in ("description", "error_description", "message", "error", "errors"):
            value = body.get(key)
            if value:
                detail = value if isinstance(value, str) else str(value)
                break

    if not detail:
        detail = response.reason_phrase or "Unexpected response"

    raise PlatformError(f"HTTP {response.status_code}: {detail}")
