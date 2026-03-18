"""Tests for Corbits proxy URL mapping."""
import pytest

from lib import corbits_urls


# ---------------------------------------------------------------------------
# get_proxy_url
# ---------------------------------------------------------------------------

def test_get_proxy_url_openai():
    result = corbits_urls.get_proxy_url("https://api.openai.com")
    assert result == "https://openai.api.corbits.dev"


def test_get_proxy_url_xai():
    result = corbits_urls.get_proxy_url("https://api.x.ai")
    assert result == "https://xai.alez-848f79.api.corbits.dev"


def test_get_proxy_url_preserves_path():
    result = corbits_urls.get_proxy_url("https://api.openai.com/v1/responses")
    assert result == "https://openai.api.corbits.dev/v1/responses"


def test_get_proxy_url_openrouter():
    result = corbits_urls.get_proxy_url("https://openrouter.ai")
    assert result == "https://openrouter.abklabs.api.corbits.dev"


def test_get_proxy_url_parallel():
    result = corbits_urls.get_proxy_url("https://api.parallel.ai")
    assert result == "https://parallelai.abklabs.api.corbits.dev"


def test_get_proxy_url_scrapecreators():
    result = corbits_urls.get_proxy_url("https://api.scrapecreators.com")
    assert result == "https://scrapecreators.abklabs.api.corbits.dev"


def test_get_proxy_url_brave():
    result = corbits_urls.get_proxy_url("https://api.search.brave.com")
    assert result == "https://brave.abklabs.api.corbits.dev"


def test_get_proxy_url_openrouter_preserves_path():
    result = corbits_urls.get_proxy_url("https://openrouter.ai/api/v1/chat/completions")
    assert result == "https://openrouter.abklabs.api.corbits.dev/api/v1/chat/completions"


def test_get_proxy_url_brave_preserves_path():
    result = corbits_urls.get_proxy_url("https://api.search.brave.com/res/v1/web/search")
    assert result == "https://brave.abklabs.api.corbits.dev/res/v1/web/search"


def test_get_proxy_url_unknown():
    with pytest.raises(ValueError, match="No Corbits proxy mapped"):
        corbits_urls.get_proxy_url("https://api.anthropic.com/v1/messages")


# ---------------------------------------------------------------------------
# get_proxy_base
# ---------------------------------------------------------------------------

def test_get_proxy_base_openai():
    result = corbits_urls.get_proxy_base("https://api.openai.com")
    assert result == "https://openai.api.corbits.dev"


def test_get_proxy_base_openrouter():
    result = corbits_urls.get_proxy_base("https://openrouter.ai")
    assert result == "https://openrouter.abklabs.api.corbits.dev"


def test_get_proxy_base_parallel():
    result = corbits_urls.get_proxy_base("https://api.parallel.ai")
    assert result == "https://parallelai.abklabs.api.corbits.dev"


def test_get_proxy_base_scrapecreators():
    result = corbits_urls.get_proxy_base("https://api.scrapecreators.com")
    assert result == "https://scrapecreators.abklabs.api.corbits.dev"


def test_get_proxy_base_brave():
    result = corbits_urls.get_proxy_base("https://api.search.brave.com")
    assert result == "https://brave.abklabs.api.corbits.dev"


def test_get_proxy_base_unknown():
    result = corbits_urls.get_proxy_base("https://api.anthropic.com")
    assert result is None


# ---------------------------------------------------------------------------
# is_proxied
# ---------------------------------------------------------------------------

def test_is_proxied_true():
    assert corbits_urls.is_proxied("https://api.openai.com/v1/chat") is True


def test_is_proxied_openrouter():
    assert corbits_urls.is_proxied("https://openrouter.ai/api/v1/chat") is True


def test_is_proxied_parallel():
    assert corbits_urls.is_proxied("https://api.parallel.ai/v1/completions") is True


def test_is_proxied_scrapecreators():
    assert corbits_urls.is_proxied("https://api.scrapecreators.com/scrape") is True


def test_is_proxied_brave():
    assert corbits_urls.is_proxied("https://api.search.brave.com/res/v1/web/search") is True


def test_is_proxied_false():
    assert corbits_urls.is_proxied("https://unknown.example.com/api") is False
