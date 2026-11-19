"""paste.rs pastebin, no account needed. Docs: https://paste.rs/web"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class PasteRsPlatform(Platform):
    name = "paste.rs"
    required_settings = ()

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        response = await client.post(
            "https://paste.rs/",
            content=message.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        raise_for_api_error(response)

        if response.status_code == 206:
            raise PlatformError("Paste was truncated by the size limit.")
        url = response.text.strip()
        if not url.startswith("https://paste.rs/"):
            raise PlatformError("Paste created but no URL was returned.")
        return PublishedPost(url=url, public_access=True)
