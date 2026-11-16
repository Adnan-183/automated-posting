"""DEV Community (dev.to), through the Forem API.

Docs: https://developers.forem.com/api/v1#tag/articles/operation/createArticle
API key: dev.to -> Settings -> Extensions -> "DEV Community API Keys".
"""

import re

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error

MAX_TITLE_LENGTH = 80


class DevToPlatform(Platform):
    name = "DEV Community"
    required_settings = ("devto_api_key",)

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        response = await client.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": self.settings.devto_api_key,
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                    "title": make_title(message, cta_url),
                    "body_markdown": message.replace(cta_url, f"[{cta_url}]({cta_url})"),
                    "published": True,
                }
            },
        )
        raise_for_api_error(response)

        article = response.json()
        if not article.get("url"):
            raise PlatformError("Article created but no URL was returned.")
        return PublishedPost(url=article["url"], public_access=bool(article.get("published", True)))


def make_title(message: str, cta_url: str) -> str:
    """Articles need a title: use the first sentence of the message, minus the link."""
    text = " ".join(message.replace(cta_url, "").split())
    first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    title = first_sentence or "Update"
    if len(title) > MAX_TITLE_LENGTH:
        title = title[: MAX_TITLE_LENGTH - 1].rstrip() + "…"
    return title
