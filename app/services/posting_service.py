"""Publishes one message to every platform, concurrently and independently."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.platforms.base import Platform, PlatformError
from app.schemas import PlatformResult, PostingResponse, PostStatus, Summary

logger = logging.getLogger("posting")

USER_AGENT = "automated-posting/1.0 (+https://github.com)"


class PostingService:
    def __init__(self, platforms: list[Platform], timeout_seconds: float = 15.0) -> None:
        self.platforms = platforms
        self.timeout_seconds = timeout_seconds

    async def publish(self, message: str, cta_url: str) -> PostingResponse:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            # Each platform runs in its own task and catches its own errors,
            # so one failure never stops the others.
            results = await asyncio.gather(
                *(self._publish_one(platform, message, cta_url, client) for platform in self.platforms)
            )

        succeeded = sum(result.status == PostStatus.success for result in results)
        return PostingResponse(
            success=succeeded > 0,
            message=message,
            cta_url=cta_url,
            summary=Summary(total=len(results), succeeded=succeeded, failed=len(results) - succeeded),
            results=list(results),
        )

    async def _publish_one(
        self, platform: Platform, message: str, cta_url: str, client: httpx.AsyncClient
    ) -> PlatformResult:
        missing = platform.missing_settings()
        if missing:
            return self._failed(platform, f"Not configured: set {', '.join(missing)}.")

        try:
            post = await platform.publish(message, cta_url, client)
        except PlatformError as exc:
            return self._failed(platform, str(exc))
        except httpx.TimeoutException:
            return self._failed(platform, f"Request timed out after {self.timeout_seconds:g}s.")
        except httpx.RequestError as exc:
            # Only the exception type: its text can include a URL holding a token.
            return self._failed(platform, f"Network error ({type(exc).__name__}).")
        except (KeyError, TypeError, ValueError):
            return self._failed(platform, "Unexpected response format from the platform API.")
        except Exception as exc:  # noqa: BLE001 - one platform must never break the rest
            logger.exception("%s: unexpected error", platform.name)
            return self._failed(platform, f"Unexpected error ({type(exc).__name__}).")

        now = datetime.now(timezone.utc)
        logger.info("%s: success %s", platform.name, post.url or "(no public URL)")
        return PlatformResult(
            platform=platform.name,
            status=PostStatus.success,
            posted_url=post.url,
            public_access=post.public_access,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
            error=None,
        )

    @staticmethod
    def _failed(platform: Platform, error: str) -> PlatformResult:
        logger.warning("%s: failed - %s", platform.name, error)
        return PlatformResult(platform=platform.name, status=PostStatus.failed, error=error)
