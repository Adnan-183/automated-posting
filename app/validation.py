"""Message validation helpers: CTA link extraction and URL checks."""

import ipaddress
import re
from urllib.parse import urlsplit

MAX_MESSAGE_LENGTH = 200
MAX_URL_LENGTH = 2048

LINK_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

TRAILING_PUNCTUATION = ".,;:!?)]}'\""

HOSTNAME_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
TOP_LEVEL_DOMAIN = re.compile(r"^(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$", re.IGNORECASE)


def extract_links(text: str) -> list[str]:
    """Return every link found in `text`, with trailing punctuation removed."""
    return [match.group(0).rstrip(TRAILING_PUNCTUATION) for match in LINK_PATTERN.finditer(text)]


def validate_url(url: str) -> str:
    """Raise ValueError unless url is a well-formed public http(s) URL."""
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"CTA link is too long (max {MAX_URL_LENGTH} characters).")

    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError(f"CTA link '{url}' must start with http:// or https://.")

    try:
        parts.port
    except ValueError:
        raise ValueError(f"CTA link '{url}' has an invalid port.") from None

    host = parts.hostname
    if not host:
        raise ValueError(f"CTA link '{url}' has no host name.")

    if parts.username or parts.password:
        raise ValueError(f"CTA link '{url}' must not contain credentials.")

    if _is_ip_address(host):
        raise ValueError(f"CTA link '{url}' must use a domain name, not an IP address.")

    labels = host.rstrip(".").split(".")
    if len(labels) < 2 or not all(HOSTNAME_LABEL.match(label) for label in labels):
        raise ValueError(f"CTA link '{url}' has an invalid domain name.")
    if not TOP_LEVEL_DOMAIN.match(labels[-1]):
        raise ValueError(f"CTA link '{url}' has an invalid top-level domain.")

    return url


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
