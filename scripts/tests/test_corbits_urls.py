"""Tests for Corbits proxy URL mapping."""
import importlib
import os
from unittest.mock import patch

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
    assert result == "https://openrouter.api.corbits.dev"


def test_get_proxy_url_parallel():
    result = corbits_urls.get_proxy_url("https://api.parallel.ai")
    assert result == "https://parallel.api.corbits.dev"


def test_get_proxy_url_scrapecreators():
    result = corbits_urls.get_proxy_url("https://api.scrapecreators.com")
    assert result == "https://scrapecreators.api.corbits.dev"


def test_get_proxy_url_brave():
    result = corbits_urls.get_proxy_url("https://api.search.brave.com")
    assert result == "https://brave.api.corbits.dev"


def test_get_proxy_url_openrouter_preserves_path():
    result = corbits_urls.get_proxy_url("https://openrouter.ai/api/v1/chat/completions")
    assert result == "https://openrouter.api.corbits.dev/api/v1/chat/completions"


def test_get_proxy_url_brave_preserves_path():
    result = corbits_urls.get_proxy_url("https://api.search.brave.com/res/v1/web/search")
    assert result == "https://brave.api.corbits.dev/res/v1/web/search"


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
    assert result == "https://openrouter.api.corbits.dev"


def test_get_proxy_base_parallel():
    result = corbits_urls.get_proxy_base("https://api.parallel.ai")
    assert result == "https://parallel.api.corbits.dev"


def test_get_proxy_base_scrapecreators():
    result = corbits_urls.get_proxy_base("https://api.scrapecreators.com")
    assert result == "https://scrapecreators.api.corbits.dev"


def test_get_proxy_base_brave():
    result = corbits_urls.get_proxy_base("https://api.search.brave.com")
    assert result == "https://brave.api.corbits.dev"


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


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------

def test_env_var_override_openai():
    """Setting CORBITS_PROXY_OPENAI overrides the default proxy URL."""
    custom_url = "https://custom-openai.example.com"
    with patch.dict(os.environ, {"CORBITS_PROXY_OPENAI": custom_url}):
        importlib.reload(corbits_urls)
        result = corbits_urls.get_proxy_url("https://api.openai.com/v1/responses")
        assert result == f"{custom_url}/v1/responses"
    # Reload to restore defaults
    importlib.reload(corbits_urls)


def test_env_var_unset_falls_back_to_default():
    """Unsetting env var falls back to the default proxy URL."""
    # Ensure env var is not set
    env = os.environ.copy()
    env.pop("CORBITS_PROXY_OPENAI", None)
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(corbits_urls)
        result = corbits_urls.get_proxy_url("https://api.openai.com/v1/responses")
        assert result == "https://openai.api.corbits.dev/v1/responses"
    # Reload to restore defaults
    importlib.reload(corbits_urls)
