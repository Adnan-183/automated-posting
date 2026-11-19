"""DEV Community (Forem API). Docs: https://developers.forem.com/api/v1#tag/articles"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error
from app.platforms.text import make_title, markdown_link


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
                    "body_markdown": markdown_link(message, cta_url),
                    "published": True,
                }
            },
        )
        raise_for_api_error(response)

        article = response.json()
        if not article.get("url"):
            raise PlatformError("Article created but no URL was returned.")
        return PublishedPost(url=article["url"], public_access=bool(article.get("published", True)))
