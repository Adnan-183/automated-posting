"""Platform registry. Platform selection is handled here, not by the API caller."""

from app.config import Settings
from app.platforms.base import Platform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.github_gist import GitHubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform

PLATFORM_CLASSES: tuple[type[Platform], ...] = (
    BlueskyPlatform,
    MastodonPlatform,
    TelegramPlatform,
    GitHubGistPlatform,
    DevToPlatform,
    DiscordPlatform,
)


def build_platforms(settings: Settings) -> list[Platform]:
    return [platform_class(settings) for platform_class in PLATFORM_CLASSES]
