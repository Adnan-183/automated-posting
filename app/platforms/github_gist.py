"""GitHub Gists, through the REST API.

Docs: https://docs.github.com/en/rest/gists/gists#create-a-gist
Token needed: a fine-grained token with "Gists: read and write",
or a classic token with the `gist` scope.
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishedPost, raise_for_api_error


class GitHubGistPlatform(Platform):
    name = "GitHub Gist"
    required_settings = ("github_token",)

    async def publish(self, message: str, cta_url: str, client: httpx.AsyncClient) -> PublishedPost:
        response = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {self.settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": message,
                "public": True,
                "files": {"post.md": {"content": f"{message}\n"}},
            },
        )
        raise_for_api_error(response)

        gist = response.json()
        if not gist.get("html_url"):
            raise PlatformError("Gist created but no URL was returned.")
        return PublishedPost(url=gist["html_url"], public_access=bool(gist.get("public")))
