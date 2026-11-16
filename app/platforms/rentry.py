"""Rentry (rentry.co), a markdown publishing service, through its API.

Docs: https://github.com/radude/rentry#usage-api
No account needed: `/api/new` is anonymous and CSRF-exempt. Rentry always
answers with HTTP 200 and puts the real status in the JSON body, so that is
what gets checked here.
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error
from app.platforms.text import make_title, markdown_link


# Rentry rejects a PAGE_TITLE longer than 60 characters.
MAX_PAGE_TITLE_LENGTH = 60


class RentryPlatform(Platform):
    name = "Rentry"
    required_settings = ()

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        data = {
            "text": markdown_link(message, cta_url),
            "metadata": f"PAGE_TITLE = {make_title(message, cta_url, MAX_PAGE_TITLE_LENGTH)}",
        }
        # A fixed edit code lets you edit or delete the pages later on rentry.co.
        # Without one, Rentry generates a random code per page.
        if self.settings.rentry_edit_code:
            data["edit_code"] = self.settings.rentry_edit_code

        response = await client.post("https://rentry.co/api/new", data=data)
        raise_for_api_error(response)

        body = response.json()
        status = str(body.get("status", ""))
        if status != "200":
            reason = body.get("errors") or body.get("content") or "Rentry rejected the page."
            raise PlatformError(f"Rentry status {status or 'unknown'}: {reason}")

        # The page details may be at the top level or nested under "content".
        details = body["content"] if isinstance(body.get("content"), dict) else body
        url = details.get("url")
        if not url:
            raise PlatformError("Page created but no URL was returned.")
        return PublishedPost(url=url, public_access=True)
