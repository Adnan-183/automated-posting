"""Discord channel, through an incoming webhook.

Docs: https://discord.com/developers/docs/resources/webhook#execute-webhook
`?wait=true` makes Discord return the created message, so we can build its
link. Discord messages are only visible to server members, so
`public_access` is always False.
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class DiscordPlatform(Platform):
    name = "Discord"
    required_settings = ("discord_webhook_url",)

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        webhook_url = self.settings.discord_webhook_url
        response = await client.post(
            webhook_url,
            params={"wait": "true"},
            # Never let the message ping @everyone, @here, users or roles.
            json={"content": message, "allowed_mentions": {"parse": []}},
        )
        raise_for_api_error(response)

        posted = response.json()
        if not posted.get("id"):
            raise PlatformError("Message sent but Discord returned no message id.")

        # The execute response has no guild id; the webhook itself does.
        webhook_response = await client.get(webhook_url)
        guild_id = webhook_response.json().get("guild_id") if webhook_response.is_success else None
        url = (
            f"https://discord.com/channels/{guild_id}/{posted['channel_id']}/{posted['id']}"
            if guild_id
            else None
        )
        return PublishedPost(url=url, public_access=False)
