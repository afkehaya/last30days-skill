"""Lobster.cash CLI wrapper for x402 payment integration (stdlib only).

Also provides the shared ``sc_get()`` helper used by reddit.py, tiktok.py,
and instagram.py to fetch from ScrapeCreators via either the Lobster x402
proxy or plain ``requests``.
"""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode as _urlencode

from .http import DEBUG, HTTPError, log


def unwrap_envelope(data: dict, known_keys: Sequence[str]) -> dict:
    """Unwrap an x402 response envelope if needed.

    If ``data`` contains a ``"body"`` key but none of the ``known_keys``,
    attempt to extract the inner response from ``body``.

    Args:
        data: Parsed JSON response (may be an x402 envelope).
        known_keys: Keys whose presence indicates the response is already
            fully unwrapped (e.g. ``("web", "news")`` for Brave).

    Returns:
        The unwrapped response dict, or ``data`` unchanged.
    """
    if "body" not in data or any(k in data for k in known_keys):
        return data
    body = data["body"]
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return data


def is_installed() -> bool:
    """Check if the lobster CLI is available on PATH."""
    return shutil.which("lobster") is not None


def is_wallet_configured() -> bool:
    """Check if a lobster wallet is configured and returns valid data.

    Runs ``lobster wallet info`` and checks for valid JSON output.
    Returns False on any error.
    """
    try:
        result = subprocess.run(
            ["lobster", "wallet", "info"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"lobster wallet info failed: {result.stderr.strip()}")
            return False
        data = json.loads(result.stdout)
        return bool(data)
    except (json.JSONDecodeError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        log(f"lobster wallet check error: {e}")
        return False


def get_balance() -> Dict[str, Any]:
    """Run ``lobster balance`` and return parsed JSON.

    Returns:
        Parsed balance data, or empty dict on error.
    """
    try:
        result = subprocess.run(
            ["lobster", "balance"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"lobster balance failed: {result.stderr.strip()}")
            return {}
        return json.loads(result.stdout)
    except (json.JSONDecodeError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        log(f"lobster balance error: {e}")
        return {}


def x402_fetch(
    url: str,
    method: str = "GET",
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 120000,
) -> Dict[str, Any]:
    """Execute an x402-paid HTTP request via ``lobster x402 fetch``.

    Args:
        url: The URL to fetch (payment handled automatically by x402).
        method: HTTP method label for logging only. The lobster CLI infers
            the actual method from the presence of ``--json`` (POST) or its
            absence (GET); this parameter does not control CLI behavior.
        json_data: Optional JSON body for POST requests.
        headers: Optional dict of extra headers (key: value).
        timeout: Payment timeout in milliseconds.

    Returns:
        Parsed JSON response from the fetched resource.

    Raises:
        HTTPError: On subprocess failure or invalid response.
    """
    cmd: List[str] = ["lobster", "x402", "fetch", url]

    if json_data is not None:
        cmd.extend(["--json", json.dumps(json_data)])

    if headers:
        for key, value in headers.items():
            cmd.extend(["--header", f"{key}:{value}"])

    cmd.extend(["--timeout", str(timeout)])

    log(f"lobster x402 fetch {method} {url}")

    # Convert timeout from ms to seconds for subprocess, with a minimum of 30s
    subprocess_timeout = max(timeout // 1000, 30)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=subprocess_timeout,
        )
    except subprocess.TimeoutExpired:
        raise HTTPError(f"lobster x402 fetch timed out after {subprocess_timeout}s")
    except FileNotFoundError:
        raise HTTPError("lobster CLI not found. Run: npm install -g @crossmint/lobster-cli")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log(f"lobster x402 fetch failed: {stderr}")
        raise HTTPError(f"lobster x402 fetch failed: {stderr}")

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        log(f"lobster x402 fetch JSON decode error: {e}")
        raise HTTPError(f"Invalid JSON from lobster x402 fetch: {e}")

    # lobster x402 fetch returns an envelope: {agentId, url, status, contentType, body, paymentSucceeded}
    # The actual API response is inside the "body" field -- either as a JSON string or already parsed.
    if "body" in envelope:
        log(f"lobster x402 response: status={envelope.get('status')} paid={envelope.get('paymentSucceeded')}")
        body = envelope["body"]
        if isinstance(body, dict) or isinstance(body, list):
            return body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                # body might not be JSON (e.g. plain text response)
                return envelope
    return envelope


def sc_get(
    url: str,
    params: dict,
    headers: dict,
    config: dict = None,
    timeout: int = 30,
    *,
    known_keys: Sequence[str] = (),
    empty_fallback: Optional[Dict[str, Any]] = None,
    log_prefix: str = "sc_get",
) -> dict:
    """Fetch from ScrapeCreators, routing through Lobster x402 proxy when available.

    This is the shared helper used by reddit.py, tiktok.py, and instagram.py
    so that envelope-unwrapping logic is not duplicated.

    Args:
        url: ScrapeCreators API URL.
        params: Query parameters dict.
        headers: HTTP headers (used only on the direct-requests path).
        config: Runtime config dict; if ``config['LOBSTER_AVAILABLE']`` is
            truthy the request is routed through the Lobster x402 proxy.
        timeout: Timeout in **seconds** (converted to ms for lobster CLI).
        known_keys: Sequence of response-level keys that indicate the x402
            envelope was already fully unwrapped (e.g. ``("posts", "data")``
            for Reddit).  When *none* of these keys are present but ``"body"``
            is, the function performs an extra unwrap attempt.
        empty_fallback: Value to return when the x402 response is unusable.
            Defaults to ``{}``.
        log_prefix: Label used in log messages (e.g. ``"Reddit"``).

    Returns:
        Parsed JSON response dict.
    """
    from . import corbits_urls  # local import to avoid circular at module level

    if empty_fallback is None:
        empty_fallback = {}

    if config and config.get('LOBSTER_AVAILABLE'):
        full_url = f"{url}?{_urlencode(params)}" if params else url
        proxy_url = corbits_urls.get_proxy_url(full_url)
        data = x402_fetch(proxy_url, method="GET", timeout=timeout * 1000)
        if not isinstance(data, dict):
            log(f"[{log_prefix}] Lobster x402 returned non-dict: {type(data).__name__}")
            return empty_fallback
        unwrapped = unwrap_envelope(data, known_keys)
        if unwrapped is not data:
            log(f"[{log_prefix}] Unwrapped x402 envelope (keys: {list(unwrapped.keys())[:5]})")
        return unwrapped
    else:
        try:
            import requests as _requests
        except ImportError:
            _requests = None
        if _requests is None:
            raise ImportError("requests library required for non-Lobster ScrapeCreators calls")
        resp = _requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


def get_setup_instructions() -> str:
    """Return user-friendly install and setup instructions for Lobster.cash."""
    return (
        "Lobster.cash Setup Instructions\n"
        "================================\n"
        "\n"
        "1. Install the Lobster CLI:\n"
        "   npm install -g @crossmint/lobster-cli\n"
        "\n"
        "2. Create a wallet:\n"
        "   lobster wallet create\n"
        "\n"
        "3. Fund your wallet with USDC on Solana to enable x402 payments.\n"
        "   Run `lobster wallet info` to see your wallet address.\n"
        "\n"
        "4. Verify setup:\n"
        "   lobster balance\n"
        "\n"
        "Wallet data is stored at: ~/.openclaw/lobster-cash/wallets.json\n"
        "Learn more: https://lobster.cash\n"
    )
