"""Corbits proxy URL mapping for x402 micropayment endpoints."""

from typing import Optional


# Corbits proxy URL mapping
PROXY_MAP = {
    "https://api.openai.com": "https://openai.api.corbits.dev",
    "https://api.x.ai": "https://xai.alez-848f79.api.corbits.dev",
    "https://openrouter.ai": "https://openrouter.abklabs.api.corbits.dev",
    "https://api.parallel.ai": "https://parallelai.abklabs.api.corbits.dev",
    "https://api.scrapecreators.com": "https://scrapecreators.abklabs.api.corbits.dev",
    "https://api.search.brave.com": "https://brave.abklabs.api.corbits.dev",
}


def get_proxy_url(original_url: str) -> str:
    """Return the Corbits proxy equivalent of a full API URL.

    Replaces only the base URL portion, preserving the path.

    Args:
        original_url: Full original API URL
            (e.g. "https://api.openai.com/v1/responses")

    Returns:
        Proxy URL with path preserved
            (e.g. "https://openai.api.corbits.dev/v1/responses")

    Raises:
        ValueError: If the URL has no known Corbits proxy.
    """
    for base, proxy in PROXY_MAP.items():
        if original_url.startswith(base):
            return original_url.replace(base, proxy, 1)
    raise ValueError(f"No Corbits proxy mapped for: {original_url}")


def get_proxy_base(original_base: str) -> Optional[str]:
    """Return the proxy base URL, or None if not mapped.

    Args:
        original_base: Base URL (e.g. "https://api.openai.com")
    """
    return PROXY_MAP.get(original_base)


def is_proxied(original_url: str) -> bool:
    """Check if a URL has a known Corbits proxy."""
    return any(original_url.startswith(base) for base in PROXY_MAP)
