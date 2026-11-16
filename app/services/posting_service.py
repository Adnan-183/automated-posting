"""Publishes one message to every platform, concurrently and independently."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost
from app.schemas import PlatformResult, PostingResponse, PostStatus, Summary

logger = logging.getLogger("posting")

USER_AGENT = "automated-posting/1.0 (+https://github.com)"

# A freshly published page can take a moment to appear, so a failed public
# check is retried once after a short pause before it is reported.
PUBLIC_CHECK_ATTEMPTS = 2
PUBLIC_CHECK_RETRY_DELAY_SECONDS = 1.5


class PostingService:
    def __init__(
        self,
        platforms: list[Platform],
        timeout_seconds: float = 15.0,
        verify_public_access: bool = True,
    ) -> None:
        self.platforms = platforms
        self.timeout_seconds = timeout_seconds
        self.verify_public_access = verify_public_access

    async def publish(self, message: str, cta_url: str) -> PostingResponse:
        async with (
            httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"User-Agent": USER_AGENT},
            ) as client,
            # Separate client for public checks: no credentials, no cookies,
            # follows redirects - it sees what an anonymous visitor sees.
            httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as anonymous_client,
        ):
            # Each platform runs in its own task and catches its own errors,
            # so one failure never stops the others.
            results = await asyncio.gather(
                *(
                    self._publish_one(platform, message, cta_url, client, anonymous_client)
                    for platform in self.platforms
                )
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
        self,
        platform: Platform,
        message: str,
        cta_url: str,
        client: httpx.AsyncClient,
        anonymous_client: httpx.AsyncClient,
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
        public_access, note = await self._check_public_access(post, anonymous_client)
        logger.info(
            "%s: success %s (public: %s)%s",
            platform.name,
            post.url or "(no public URL)",
            public_access,
            f" - {note}" if note else "",
        )
        return PlatformResult(
            platform=platform.name,
            status=PostStatus.success,
            posted_url=post.url,
            public_access=public_access,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
            error=None,
            note=note,
        )

    async def _check_public_access(
        self, post: PublishedPost, anonymous_client: httpx.AsyncClient
    ) -> tuple[bool, str | None]:
        """Confirm the post opens for an anonymous visitor.

        The platform's own claim is only the starting point: a platform can
        report a post as public while the account is hidden or the page is
        not live yet. Only a successful anonymous GET counts as public.
        """
        if not post.url or not post.public_access:
            return False, None
        if not self.verify_public_access:
            return True, "Public access reported by the platform, not checked."

        problem = None
        for attempt in range(PUBLIC_CHECK_ATTEMPTS):
            if attempt:
                await asyncio.sleep(PUBLIC_CHECK_RETRY_DELAY_SECONDS)
            try:
                response = await anonymous_client.get(post.url)
            except httpx.TimeoutException:
                problem = "timed out"
                continue
            except httpx.RequestError as exc:
                problem = f"could not be reached ({type(exc).__name__})"
                continue
            if response.is_success:
                return True, None
            problem = f"returned HTTP {response.status_code}"

        return False, f"Posted, but the URL {problem} for an anonymous visitor."

    @staticmethod
    def _failed(platform: Platform, error: str) -> PlatformResult:
        logger.warning("%s: failed - %s", platform.name, error)
        return PlatformResult(platform=platform.name, status=PostStatus.failed, error=error)
