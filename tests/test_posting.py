import json

import httpx
import pytest

from app.platforms.bluesky import link_facet
from app.platforms.text import make_title
from tests.conftest import BOT_TOKEN, DISCORD_WEBHOOK

VALID_MESSAGE = (
    "Check out our latest business platform and grow your online visibility. https://example.com"
)


def results_by_platform(response) -> dict:
    return {result["platform"]: result for result in response.json()["results"]}


# --- Input validation -------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        ("", "must not be empty"),
        ("   ", "must not be empty"),
        ("x" * 190 + " https://example.com", "must not exceed 200 characters"),
        ("No link here at all", "none found"),
        ("Two links https://a.com and https://b.com", "found 2"),
        ("Visit www.example.com today", "must start with http:// or https://"),
        ("Bad host https://localhost/page", "invalid domain name"),
        ("IP host https://192.168.0.1/page", "not an IP address"),
        ("Bad TLD https://example.c0m", "invalid top-level domain"),
        ("Bad port https://example.com:99999/", "invalid port"),
        ("Creds https://user:pass@example.com", "must not contain credentials"),
    ],
)
def test_invalid_messages_are_rejected(client, message, expected_error):
    response = client.post("/posting", json={"message": message})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "validation_error"
    assert body["details"][0]["field"] == "message"
    assert expected_error in body["details"][0]["message"]


def test_missing_message_field_is_rejected(client):
    response = client.post("/posting", json={})
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "message"


def test_caller_cannot_choose_platforms(client):
    response = client.post("/posting", json={"message": VALID_MESSAGE, "platforms": ["Bluesky"]})
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "platforms"


def test_non_string_message_is_rejected(client):
    response = client.post("/posting", json={"message": 12345})
    assert response.status_code == 422


def test_malformed_json_is_rejected(client):
    response = client.post(
        "/posting", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["success"] is False


def test_message_of_exactly_200_characters_is_accepted(client, mock_platforms):
    message = "x" * 180 + " https://example.com"
    assert len(message) == 200
    response = client.post("/posting", json={"message": message})
    assert response.status_code == 200


def test_trailing_punctuation_is_not_part_of_the_link(client, mock_platforms):
    response = client.post("/posting", json={"message": "Read more at https://example.com/blog."})
    assert response.status_code == 200
    assert response.json()["cta_url"] == "https://example.com/blog"


# --- Posting ----------------------------------------------------------------


def test_posts_to_every_platform(client, mock_platforms):
    response = client.post("/posting", json={"message": VALID_MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["summary"] == {"total": 8, "succeeded": 8, "failed": 0}

    results = results_by_platform(response)
    assert results["Bluesky"]["posted_url"] == "https://bsky.app/profile/tester.bsky.social/post/3kpost"
    assert results["Mastodon"]["posted_url"] == "https://mastodon.example/@tester/1"
    assert results["Telegram"]["posted_url"] == "https://t.me/test_channel/42"
    assert results["GitHub Gist"]["posted_url"] == "https://gist.github.com/tester/abc"
    assert results["DEV Community"]["posted_url"] == "https://dev.to/tester/check-out-1abc"
    assert results["Discord"]["posted_url"] == "https://discord.com/channels/333/222/999"
    assert results["Rentry"]["posted_url"] == "https://rentry.co/abc123"
    assert results["paste.rs"]["posted_url"] == "https://paste.rs/Xy12z"

    assert results["Discord"]["public_access"] is False
    for name in ("Bluesky", "Mastodon", "Telegram", "GitHub Gist", "DEV Community", "Rentry", "paste.rs"):
        assert results[name]["public_access"] is True

    for result in body["results"]:
        assert result["status"] == "success"
        assert result["error"] is None
        assert len(result["date"]) == 10 and len(result["time"]) == 8


def test_one_failure_does_not_stop_the_others(client, mock_platforms):
    mock_platforms.post("https://mastodon.example/api/v1/statuses").respond(
        401, json={"error": "The access token is invalid"}
    )

    response = client.post("/posting", json={"message": VALID_MESSAGE})

    body = response.json()
    assert body["success"] is True
    assert body["summary"] == {"total": 8, "succeeded": 7, "failed": 1}
    mastodon = results_by_platform(response)["Mastodon"]
    assert mastodon == {
        "platform": "Mastodon",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "HTTP 401: The access token is invalid",
    }


def test_timeouts_and_network_errors_are_reported(client, mock_platforms):
    mock_platforms.post("https://api.github.com/gists").mock(side_effect=httpx.ReadTimeout("slow"))
    mock_platforms.post("https://dev.to/api/articles").mock(side_effect=httpx.ConnectError("down"))

    results = results_by_platform(client.post("/posting", json={"message": VALID_MESSAGE}))

    assert results["GitHub Gist"]["error"].startswith("Request timed out")
    assert results["DEV Community"]["error"] == "Network error (ConnectError)."
    assert results["Bluesky"]["status"] == "success"


def test_errors_never_leak_credentials(client, mock_platforms):
    mock_platforms.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage").mock(
        side_effect=httpx.ConnectError(f"failed https://api.telegram.org/bot{BOT_TOKEN}/sendMessage")
    )
    mock_platforms.post(DISCORD_WEBHOOK).respond(404, json={"message": "Unknown Webhook"})

    response = client.post("/posting", json={"message": VALID_MESSAGE})

    raw = json.dumps(response.json())
    assert BOT_TOKEN not in raw
    assert "SECRET-WEBHOOK-TOKEN" not in raw
    assert results_by_platform(response)["Discord"]["error"] == "HTTP 404: Unknown Webhook"


def test_unexpected_response_shape_is_handled(client, mock_platforms):
    mock_platforms.post("https://bsky.social/xrpc/com.atproto.server.createSession").respond(
        200, text="<html>not json</html>"
    )
    result = results_by_platform(client.post("/posting", json={"message": VALID_MESSAGE}))["Bluesky"]
    assert result["status"] == "failed"
    assert result["error"] == "Unexpected response format from the platform API."


def test_private_telegram_chat_has_no_public_url(client, mock_platforms):
    mock_platforms.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage").respond(
        200, json={"ok": True, "result": {"message_id": 7, "chat": {"type": "channel"}}}
    )
    telegram = results_by_platform(client.post("/posting", json={"message": VALID_MESSAGE}))["Telegram"]
    assert telegram["status"] == "success"
    assert telegram["posted_url"] is None
    assert telegram["public_access"] is False


def test_unconfigured_platforms_fail_with_a_clear_message(unconfigured_client, mock_platforms):
    response = unconfigured_client.post("/posting", json={"message": VALID_MESSAGE})

    body = response.json()
    assert response.status_code == 200
    # Only the two no-account platforms can post without credentials.
    assert body["success"] is True
    assert body["summary"] == {"total": 8, "succeeded": 2, "failed": 6}
    results = results_by_platform(response)
    assert results["Rentry"]["status"] == "success"
    assert results["paste.rs"]["status"] == "success"
    assert results_by_platform(response)["Mastodon"]["error"] == (
        "Not configured: set MASTODON_INSTANCE_URL, MASTODON_ACCESS_TOKEN."
    )


def test_requests_send_the_expected_payloads(client, mock_platforms):
    client.post("/posting", json={"message": VALID_MESSAGE})

    mastodon = mock_platforms.routes[2].calls.last.request
    assert mastodon.headers["Authorization"] == "Bearer mastodon-token"
    assert b"visibility=public" in mastodon.content

    discord = json.loads(mock_platforms.routes[6].calls.last.request.content)
    assert discord["allowed_mentions"] == {"parse": []}

    gist = json.loads(mock_platforms.routes[4].calls.last.request.content)
    assert gist["public"] is True


def test_rentry_error_status_inside_http_200_is_a_failure(client, mock_platforms):
    # Rentry always answers HTTP 200; the real status is in the body.
    mock_platforms.post("https://rentry.co/api/new").respond(
        200, json={"status": "429", "content": "Rate limited, slow down."}
    )
    rentry = results_by_platform(client.post("/posting", json={"message": VALID_MESSAGE}))["Rentry"]
    assert rentry["status"] == "failed"
    assert rentry["error"] == "Rentry status 429: Rate limited, slow down."


def test_rentry_page_gets_a_title_and_markdown_link(client, mock_platforms):
    client.post("/posting", json={"message": VALID_MESSAGE})
    request = mock_platforms.routes[8].calls.last.request
    sent = dict(httpx.QueryParams(request.content.decode()))
    assert sent["text"].endswith("[https://example.com](https://example.com)")
    title = sent["metadata"].removeprefix("PAGE_TITLE = ")
    # Rentry rejects titles over 60 characters (found in a live run).
    assert len(title) <= 60
    assert title.startswith("Check out our latest business platform")
    assert "edit_code" not in sent


def test_paste_rs_truncated_paste_is_a_failure(client, mock_platforms):
    mock_platforms.post("https://paste.rs/").respond(206, text="https://paste.rs/Cut01")
    paste = results_by_platform(client.post("/posting", json={"message": VALID_MESSAGE}))["paste.rs"]
    assert paste["status"] == "failed"
    assert paste["error"] == "Paste was truncated by the size limit."


# --- Platform helpers -------------------------------------------------------


def test_platforms_endpoint_lists_configuration(unconfigured_client):
    statuses = {s["platform"]: s for s in unconfigured_client.get("/platforms").json()}
    assert len(statuses) == 8
    assert statuses["Rentry"]["configured"] is True
    assert statuses["paste.rs"]["configured"] is True
    assert statuses["GitHub Gist"] == {
        "platform": "GitHub Gist",
        "configured": False,
        "missing_env_vars": ["GITHUB_TOKEN"],
    }


def test_bluesky_link_facet_uses_byte_offsets():
    text = "🚀 Launch day https://example.com"
    facet = link_facet(text, "https://example.com")
    encoded = text.encode("utf-8")
    start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
    assert encoded[start:end] == b"https://example.com"


def test_devto_title_comes_from_first_sentence():
    assert make_title(VALID_MESSAGE, "https://example.com") == "Check out our latest business platform and grow your online visibility."
    assert make_title("https://example.com", "https://example.com") == "Update"
