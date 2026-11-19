"""Bluesky (AT Protocol). Docs: https://docs.bsky.app/docs/advanced-guides/posts"""

from datetime import datetime, timezone

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class BlueskyPlatform(Platform):
    name = "Bluesky"
    required_settings = ("bluesky_handle", "bluesky_app_password")

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        service = self.settings.bluesky_service_url.rstrip("/")

        session_response = await client.post(
            f"{service}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": self.settings.bluesky_handle,
                "password": self.settings.bluesky_app_password,
            },
        )
        raise_for_api_error(session_response)
        session = session_response.json()

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "facets": [link_facet(message, cta_url)],
        }
        post_response = await client.post(
            f"{service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        )
        raise_for_api_error(post_response)

        uri = post_response.json().get("uri")
        if not uri:
            raise PlatformError("Post created but no record URI was returned.")
        rkey = uri.rsplit("/", 1)[-1]
        return PublishedPost(
            url=f"https://bsky.app/profile/{session['handle']}/post/{rkey}",
            public_access=True,
        )


def link_facet(text: str, url: str) -> dict:
    """Make the URL clickable. Bluesky facets use UTF-8 *byte* offsets."""
    start_char = text.find(url)
    byte_start = len(text[:start_char].encode("utf-8"))
    byte_end = byte_start + len(url.encode("utf-8"))
    return {
        "index": {"byteStart": byte_start, "byteEnd": byte_end},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
    }
