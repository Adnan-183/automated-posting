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
    """Raised when a platform rejects a post. Never include credentials in the message."""


class Platform(ABC):
    name: ClassVar[str]
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
    """Raise PlatformError for non-2xx responses, without the request URL."""
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
