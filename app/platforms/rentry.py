"""Rentry markdown pages, no account needed. Docs: https://github.com/radude/rentry#usage-api"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error
from app.platforms.text import make_title, markdown_link


MAX_PAGE_TITLE_LENGTH = 60


class RentryPlatform(Platform):
    name = "Rentry"
    required_settings = ()

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        data = {
            "text": markdown_link(message, cta_url),
            "metadata": f"PAGE_TITLE = {make_title(message, cta_url, MAX_PAGE_TITLE_LENGTH)}",
        }
        if self.settings.rentry_edit_code:
            data["edit_code"] = self.settings.rentry_edit_code

        response = await client.post("https://rentry.co/api/new", data=data)
        raise_for_api_error(response)

        body = response.json()
        status = str(body.get("status", ""))
        if status != "200":
            reason = body.get("errors") or body.get("content") or "Rentry rejected the page."
            raise PlatformError(f"Rentry status {status or 'unknown'}: {reason}")

        details = body["content"] if isinstance(body.get("content"), dict) else body
        url = details.get("url")
        if not url:
            raise PlatformError("Page created but no URL was returned.")
        return PublishedPost(url=url, public_access=True)
