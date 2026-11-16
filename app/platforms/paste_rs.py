"""paste.rs, a public pastebin, through its HTTP API.

Docs: https://paste.rs/web (API: POST the raw text to https://paste.rs/)
No account needed. The response body is the paste URL as plain text:
201 means the paste was stored in full, 206 means it was cut short by the
size limit, which is treated as a failure here.
"""

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
