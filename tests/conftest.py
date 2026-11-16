import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

BOT_TOKEN = "123456:SECRET-BOT-TOKEN"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/111/SECRET-WEBHOOK-TOKEN"


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        bluesky_handle="tester.bsky.social",
        bluesky_app_password="app-password",
        mastodon_instance_url="https://mastodon.example",
        mastodon_access_token="mastodon-token",
        telegram_bot_token=BOT_TOKEN,
        telegram_chat_id="@test_channel",
        github_token="github-token",
        devto_api_key="devto-key",
        discord_webhook_url=DISCORD_WEBHOOK,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = configured_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unconfigured_client():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_platforms():
    """Mock every platform API with a successful response."""
    with respx.mock(assert_all_called=False) as router:
        router.post("https://bsky.social/xrpc/com.atproto.server.createSession").respond(
            200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "tester.bsky.social"}
        )
        router.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").respond(
            200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kpost", "cid": "cid"}
        )
        router.post("https://mastodon.example/api/v1/statuses").respond(
            200, json={"url": "https://mastodon.example/@tester/1", "visibility": "public"}
        )
        router.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage").respond(
            200,
            json={
                "ok": True,
                "result": {"message_id": 42, "chat": {"username": "test_channel", "type": "channel"}},
            },
        )
        router.post("https://api.github.com/gists").respond(
            201, json={"html_url": "https://gist.github.com/tester/abc", "public": True}
        )
        router.post("https://dev.to/api/articles").respond(
            201, json={"url": "https://dev.to/tester/check-out-1abc", "published": True}
        )
        router.post(DISCORD_WEBHOOK).respond(200, json={"id": "999", "channel_id": "222"})
        router.get(DISCORD_WEBHOOK).respond(200, json={"guild_id": "333"})
        yield router

