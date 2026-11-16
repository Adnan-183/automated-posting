"""Telegram channel, through the Bot API.

Docs: https://core.telegram.org/bots/api#sendmessage
The bot must be an administrator of the channel. A channel with a public
@username gets a public t.me link; a private one gets no public URL.
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class TelegramPlatform(Platform):
    name = "Telegram"
    required_settings = ("telegram_bot_token", "telegram_chat_id")

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        response = await client.post(
            f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage",
            json={"chat_id": self.settings.telegram_chat_id, "text": message},
        )
        raise_for_api_error(response)

        body = response.json()
        if not body.get("ok"):
            raise PlatformError(body.get("description", "Telegram rejected the message."))

        result = body["result"]
        username = result.get("chat", {}).get("username")
        if not username:
            # Private channel or group: the message exists but has no public link.
            return PublishedPost(url=None, public_access=False)
        return PublishedPost(url=f"https://t.me/{username}/{result['message_id']}", public_access=True)
