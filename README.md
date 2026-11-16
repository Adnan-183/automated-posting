# Automated Multi-Platform Posting System

A FastAPI service with one endpoint, `POST /posting`. It takes a short message with one call-to-action link and publishes it to six third-party platforms through their official APIs. It returns a result for every platform: the posted URL, whether the post is publicly accessible, and when it was posted or why it failed.

- **Stack:** Python 3.10+, FastAPI, Uvicorn, Pydantic v2, HTTPX (async)
- **Platforms:** Bluesky, Mastodon, Telegram, GitHub Gist, DEV Community, Discord
- **Behaviour:** platforms are posted to concurrently and independently, so one failure never blocks the rest
- **Tests:** 28 pytest tests, with every platform API mocked (no credentials needed)

---

## Contents

1. [Quick start](#quick-start)
2. [API](#api)
3. [Input validation](#input-validation)
4. [Platform research](#platform-research)
5. [Getting credentials](#getting-credentials)
6. [How it works](#how-it-works)
7. [Error handling](#error-handling)
8. [Tests](#tests)
9. [Logs and screenshots](#logs-and-screenshots)
10. [Project structure](#project-structure)

---

## Quick start

```bash
git clone <this-repo-url> automated-posting
cd automated-posting

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then fill in the credentials you have
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

- Interactive docs: http://localhost:4000/docs
- Which platforms are configured: http://localhost:4000/platforms

You don't need every credential. Any platform without credentials is reported as `failed` with a "Not configured" error, and the others still post.

---

## API

### `POST /posting`

**Request**

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Check out our latest business platform and grow your online visibility. https://example.com"}'
```

**Response `200`** (with all six platforms configured)

```json
{
  "success": true,
  "message": "Check out our latest business platform and grow your online visibility. https://example.com",
  "cta_url": "https://example.com",
  "summary": { "total": 6, "succeeded": 5, "failed": 1 },
  "results": [
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/<handle>/post/<rkey>",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:00",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "HTTP 401: The access token is invalid"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `platform` | Platform name |
| `status` | `success` or `failed` |
| `posted_url` | Link to the published post (`null` on failure, or where no public link exists) |
| `public_access` | `true` if anyone can open the post without an account or membership |
| `date` / `time` | When the post was published, in **UTC** (`YYYY-MM-DD`, `HH:MM:SS`) |
| `error` | Why it failed, taken from the platform's own error message where possible |

The top-level `success` is `true` when at least one platform succeeded. `summary` gives the counts. The status code is `200` whenever the input is valid, because the per-platform outcome is in the body.

### `GET /platforms`

This lists each platform with whether it's configured and which environment variables are missing. It's useful for checking your `.env` before posting.

### `GET /health`

Returns `{"status": "ok"}`.

---

## Input validation

Invalid input returns **`422`** with one consistent error shape:

```json
{
  "success": false,
  "error": "validation_error",
  "details": [
    {
      "field": "message",
      "message": "Message must include exactly one CTA link (found 2: https://a.com, https://b.com)."
    }
  ]
}
```

| Rule | Example that fails | Error |
|---|---|---|
| Required, a string, not empty | `{}`, `{"message": ""}` | `Message must not be empty.` |
| At most 200 characters (after trimming spaces) | 213 chars | `Message must not exceed 200 characters (got 213).` |
| Exactly one link | no link / two links | `... exactly one CTA link (none found)` / `(found 2: ...)` |
| Link must be http(s) | `www.example.com` | `... must start with http:// or https://.` |
| Real domain with a valid TLD | `https://localhost`, `https://example.c0m` | `... invalid domain name` / `invalid top-level domain` |
| No IP addresses, credentials or bad ports | `https://1.2.3.4`, `https://u:p@x.com`, `:99999` | specific message for each |
| No extra fields | `{"message": "...", "platforms": [...]}` | `Extra inputs are not permitted` |

Notes:
- Bare `www.` links count towards the one-link rule, so `"https://a.com and www.b.com"` is rejected as two links.
- Sentence punctuation after a link is not treated as part of it: in `"... https://example.com/blog."` the link is `https://example.com/blog`.
- The last rule enforces the brief's "platform selection must be handled internally": callers can't pick platforms.

---

## Platform research

### Chosen platforms

I chose these six because each has an official, documented, free write API that an individual developer can use without a partner or app review, and five of them return a public URL for the post.

| Platform | API used | Auth | Public URL | Docs |
|---|---|---|---|---|
| **Bluesky** | AT Protocol XRPC: `com.atproto.server.createSession`, then `com.atproto.repo.createRecord` | Handle and app password, giving a session JWT | ✅ `bsky.app/profile/<handle>/post/<rkey>` | [Posts](https://docs.bsky.app/docs/advanced-guides/posts), [Rich text](https://docs.bsky.app/docs/advanced-guides/post-richtext) |
| **Mastodon** | `POST /api/v1/statuses` | Bearer token (`write:statuses`) | ✅ status `url` | [Statuses](https://docs.joinmastodon.org/methods/statuses/#create) |
| **Telegram** | Bot API `sendMessage` to a channel | Bot token | ✅ `t.me/<channel>/<id>` for public channels | [sendMessage](https://core.telegram.org/bots/api#sendmessage) |
| **GitHub Gist** | `POST /gists` (public gist) | Personal access token | ✅ gist `html_url` | [Create a gist](https://docs.github.com/en/rest/gists/gists#create-a-gist) |
| **DEV Community** | Forem `POST /api/articles` (published) | `api-key` header | ✅ article `url` | [Forem API](https://developers.forem.com/api/v1#tag/articles) |
| **Discord** | Execute webhook with `?wait=true` | Webhook URL | ⚠️ link only works for server members, so `public_access: false` | [Execute webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook) |

Platform-specific details handled:
- **Bluesky:** a plain-text URL is not clickable. The code adds a *link facet*, which needs **UTF-8 byte offsets**, not character offsets, so messages with emoji still link correctly (there's a test for this).
- **Mastodon:** sends an `Idempotency-Key`, so a retried request can't create a duplicate post.
- **Telegram:** a private channel has no public link, so the post is reported as `success` with `posted_url: null` and `public_access: false`.
- **DEV Community:** articles need a title, so the first sentence of the message is used, without the link, capped at 80 characters.
- **Discord:** `allowed_mentions: {"parse": []}` stops a message from pinging `@everyone`. The execute response has no guild id, so it's read from the webhook to build the message link.

### Considered and not used

| Platform | Why not |
|---|---|
| X (Twitter) | Write access is a paid API product |
| LinkedIn | Posting needs an approved app with the "Share on LinkedIn" / Community Management product |
| Facebook Pages / Instagram | Needs a Meta app, a business account and app review for publishing permissions |
| Reddit | New API apps need approval, and many subreddits block automated link posts |
| LLM platforms (OpenAI, Anthropic, etc.) | Their APIs generate text but don't host public posts, so there's nothing to publish to or link to |

### Adding a platform

1. Create `app/platforms/<name>.py` with a subclass of `Platform`. Set `name` and `required_settings`, and implement `publish()` to return a `PublishedPost`.
2. Add its settings to `app/config.py` and `.env.example`.
3. Register the class in `PLATFORM_CLASSES` in `app/platforms/__init__.py`.

Nothing else changes: validation, concurrency, error handling and the response format come from the shared service.

---

## Getting credentials

Each one takes about five minutes. Put the values in `.env`, which is git-ignored.

| Platform | Steps |
|---|---|
| **Bluesky** | Settings → Privacy and security → **App passwords** → Add. Set `BLUESKY_HANDLE` (e.g. `you.bsky.social`) and `BLUESKY_APP_PASSWORD`. |
| **Mastodon** | On your instance: Preferences → Development → **New application** with scope `write:statuses`, then copy *Your access token*. Set `MASTODON_INSTANCE_URL` (e.g. `https://mastodon.social`) and `MASTODON_ACCESS_TOKEN`. |
| **Telegram** | Message [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token. Create a **public** channel with a username, then add the bot as an **administrator** with "Post messages". Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID=@yourchannel`. |
| **GitHub Gist** | Settings → Developer settings → Personal access tokens → **Fine-grained** → Account permissions → *Gists: Read and write*. Set `GITHUB_TOKEN`. |
| **DEV Community** | dev.to → Settings → Extensions → **DEV Community API Keys** → Generate. Set `DEVTO_API_KEY`. |
| **Discord** | Server Settings → Integrations → **Webhooks** → New Webhook → pick a channel → Copy Webhook URL. Set `DISCORD_WEBHOOK_URL`. |

---

## How it works

```
POST /posting
   │
   ▼
PostRequest (Pydantic)  ── invalid ──► 422 {success:false, error, details[]}
   │ valid: message + cta_url
   ▼
PostingService.publish()
   │  one shared httpx.AsyncClient (timeout, User-Agent)
   │  asyncio.gather over every registered platform
   ├──► Bluesky.publish()      ─┐
   ├──► Mastodon.publish()      │  each wrapped in _publish_one():
   ├──► Telegram.publish()      │   - missing credentials → failed
   ├──► GitHubGist.publish()    │   - exceptions caught per platform
   ├──► DevTo.publish()         │   - success → URL + UTC timestamp
   └──► Discord.publish()      ─┘
   │
   ▼
PostingResponse {success, message, cta_url, summary, results[]}
```

Design decisions:
- **Concurrent.** The total time is roughly the slowest platform, not the sum of all six.
- **Isolated failures.** Each platform's call is wrapped on its own, so an exception, timeout or bad response affects only that platform's result.
- **Platform registry.** Selection is internal (`PLATFORM_CLASSES`), and the request model rejects any attempt to choose platforms.
- **Dependency injection.** Settings and the service are FastAPI dependencies, so tests override them without patching globals.
- **Optional credentials.** Settings come from environment variables or `.env` via `pydantic-settings`. Nothing is hard-coded.

---

## Error handling

| Situation | Reported `error` |
|---|---|
| Credentials missing | `Not configured: set MASTODON_INSTANCE_URL, MASTODON_ACCESS_TOKEN.` |
| API returns 4xx/5xx | `HTTP 401: <the platform's own message>` (read from `error`, `message`, `description`, …) |
| Timeout | `Request timed out after 15s.` (set with `HTTP_TIMEOUT_SECONDS`) |
| DNS or connection failure | `Network error (ConnectError).` |
| Response isn't the expected JSON | `Unexpected response format from the platform API.` |
| Anything else | `Unexpected error (<type>).`, with the full traceback logged on the server |

**Credentials never reach the response.** Telegram puts the bot token in the request URL, and Discord webhook URLs contain a secret. Error messages are therefore built from the status code and the API's reason only, never from the request URL or the raw exception text. A test checks that neither secret appears in the response.

---

## Tests

```bash
pytest -q
```

The 28 tests use [respx](https://lundberg.github.io/respx/) to mock every platform API, so they run offline in under a second. They cover:

- every validation rule, including the 200-character boundary, trailing punctuation, extra fields and malformed JSON
- all six platforms succeeding, and the exact URL built for each
- one platform failing while the rest still post
- timeouts and network errors
- secrets never appearing in error messages
- non-JSON responses
- a private Telegram chat (success with no public URL)
- the response when no platforms are configured
- the request payloads sent (auth header, `visibility=public`, `allowed_mentions`, public gist)
- Bluesky byte-offset facets with emoji, and the DEV title helper

---

## Logs and screenshots

Server log from a real run with no `.env` (each platform fails cleanly and the request still returns 200):

```
INFO:     Uvicorn running on http://0.0.0.0:4000 (Press CTRL+C to quit)
WARNING posting: Bluesky: failed - Not configured: set BLUESKY_HANDLE, BLUESKY_APP_PASSWORD.
WARNING posting: Mastodon: failed - Not configured: set MASTODON_INSTANCE_URL, MASTODON_ACCESS_TOKEN.
WARNING posting: Telegram: failed - Not configured: set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
WARNING posting: GitHub Gist: failed - Not configured: set GITHUB_TOKEN.
WARNING posting: DEV Community: failed - Not configured: set DEVTO_API_KEY.
WARNING posting: Discord: failed - Not configured: set DISCORD_WEBHOOK_URL.
INFO:     127.0.0.1:50217 - "POST /posting HTTP/1.1" 200 OK
INFO:     127.0.0.1:50219 - "POST /posting HTTP/1.1" 422 Unprocessable Content
```

With credentials set, each successful platform logs a line like `INFO posting: Bluesky: success https://bsky.app/profile/...`.

Screenshots from a live run are in [`docs/screenshots/`](docs/screenshots/): the Swagger UI, a full response, and the published posts on each platform.

---

## Project structure

```
automated-posting/
├── app/
│   ├── main.py                  # FastAPI app, routes, validation error handler
│   ├── schemas.py               # Request/response models (Pydantic)
│   ├── validation.py            # Link extraction and URL checks
│   ├── config.py                # Settings from environment / .env
│   ├── platforms/
│   │   ├── __init__.py          # Platform registry (internal selection)
│   │   ├── base.py              # Platform interface, PublishedPost, API error parsing
│   │   ├── bluesky.py
│   │   ├── mastodon.py
│   │   ├── telegram.py
│   │   ├── github_gist.py
│   │   ├── devto.py
│   │   └── discord.py
│   └── services/
│       └── posting_service.py   # Concurrent, failure-isolated publishing
├── tests/
│   ├── conftest.py              # Fixtures: settings overrides, mocked platform APIs
│   └── test_posting.py
├── docs/screenshots/
├── .env.example
├── requirements.txt
└── README.md
```

## Security

- `.env` is in `.gitignore`. Only `.env.example`, with empty values, is committed.
- Error messages never include tokens, webhook secrets or request URLs.
- Discord mentions are disabled, so a message can't ping `@everyone`.
- The validator rejects links with embedded credentials or raw IP addresses.
