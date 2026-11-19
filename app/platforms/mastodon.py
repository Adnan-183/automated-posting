"""Mastodon statuses. Docs: https://docs.joinmastodon.org/methods/statuses/#create"""

import uuid

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class MastodonPlatform(Platform):
    name = "Mastodon"
    required_settings = ("mastodon_instance_url", "mastodon_access_token")

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        instance = self.settings.mastodon_instance_url.rstrip("/")
        response = await client.post(
            f"{instance}/api/v1/statuses",
            headers={
                "Authorization": f"Bearer {self.settings.mastodon_access_token}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            data={"status": message, "visibility": "public"},
        )
        raise_for_api_error(response)

        status = response.json()
        if not status.get("url"):
            raise PlatformError("Status created but no URL was returned.")
        return PublishedPost(url=status["url"], public_access=status.get("visibility") == "public")
