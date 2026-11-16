"""Text helpers shared by platforms that need more than the raw message."""

import re

MAX_TITLE_LENGTH = 80


def make_title(message: str, cta_url: str, max_length: int = MAX_TITLE_LENGTH) -> str:
    """Build a title from the first sentence of the message, without the link."""
    text = " ".join(message.replace(cta_url, "").split())
    first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    title = first_sentence or "Update"
    if len(title) > max_length:
        title = title[: max_length - 1].rstrip() + "…"
    return title


def markdown_link(message: str, cta_url: str) -> str:
    """Return the message with its CTA link written as a markdown link."""
    return message.replace(cta_url, f"[{cta_url}]({cta_url})")
