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
    """Check if a lobster wallet is configured with an active agent.

    Tries v3.x ``lobster agents list`` first, falls back to v1.x
    ``lobster wallet info`` for backwards compatibility.
    Returns False on any error.
    """
    # v3.x: check for an active agent
    try:
        result = subprocess.run(
            ["lobster", "agents", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and "(active)" in result.stdout:
            return True
        # If the command exists but no active agent, that's a valid "not configured"
        if result.returncode == 0:
            log("lobster agents list: no active agent found")
            return False
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        log(f"lobster agents list error: {e}")
        return False

    # v1.x fallback: lobster wallet info
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
    """Run ``lobster crypto balance`` (v3.x) or ``lobster balance`` (v1.x).

    v3.x outputs human-readable text, so we parse it into a dict.

    Returns:
        Parsed balance data, or empty dict on error.
    """
    import re

    # Known token names in lobster crypto balance output
    _KNOWN_TOKENS = {"usdc", "sol", "usdt", "bonk", "pyusd"}

    # v3.x: lobster crypto balance
    try:
        result = subprocess.run(
            ["lobster", "crypto", "balance"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            # v3.x output is human-readable text like:
            #   usdc: 5
            #   sol: 0
            balances = {}
            for match in re.finditer(r'^\s*(\w+):\s*([\d.]+)\s*$', result.stdout, re.MULTILINE):
                token, amount = match.group(1).lower(), match.group(2)
                if token not in _KNOWN_TOKENS:
                    continue
                try:
                    balances[token] = float(amount)
                except ValueError:
                    continue
            # Also extract wallet address if present
            wallet_match = re.search(r'Smart Wallet:\s*(\S+)', result.stdout, re.IGNORECASE)
            if wallet_match:
                balances['wallet'] = wallet_match.group(1)
            return balances
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        log(f"lobster crypto balance error: {e}")

    # v1.x fallback: lobster balance (returns JSON)
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
    # v3.x command; falls back to v1.x if "unknown command" error
    cmd: List[str] = ["lobster", "crypto", "x402", "fetch", url]

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

    # v1.x fallback: if v3.x command not recognized, try old path
    if result.returncode != 0 and "unknown command" in result.stderr.lower():
        log("v3.x crypto x402 not found, falling back to v1.x lobster x402 fetch")
        cmd_v1: List[str] = ["lobster", "x402", "fetch", url]
        if json_data is not None:
            cmd_v1.extend(["--json", json.dumps(json_data)])
        if headers:
            for key, value in headers.items():
                cmd_v1.extend(["--header", f"{key}:{value}"])
        cmd_v1.extend(["--timeout", str(timeout)])
        try:
            result = subprocess.run(
                cmd_v1,
                capture_output=True,
                text=True,
                timeout=subprocess_timeout,
            )
        except subprocess.TimeoutExpired:
            raise HTTPError(f"lobster x402 fetch timed out after {subprocess_timeout}s")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log(f"lobster x402 fetch failed: {stderr}")
        raise HTTPError(f"lobster x402 fetch failed: {stderr}")

    # v3.x outputs a text preamble before the JSON body:
    #   x402 FETCH https://...
    #   Status: 200
    #   Content-Type: application/json
    #   Payment: USDC via settlement account
    #
    #   {"actual":"json",...}
    #
    # v1.x outputs pure JSON (an envelope with {agentId, url, status, body}).
    stdout = result.stdout
    if stdout.lstrip().startswith("x402"):
        # v3.x: strip preamble, JSON starts after blank line
        parts = stdout.split("\n\n", 1)
        if len(parts) == 2:
            stdout = parts[1].strip()
            log(f"lobster v3.x: stripped preamble, body starts with: {stdout[:60]!r}")
        else:
            log(f"lobster v3.x: preamble detected but no blank line separator")

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        log(f"lobster x402 fetch JSON decode error: {e}")
        raise HTTPError(f"Invalid JSON from lobster x402 fetch: {e}")

    # v1.x returns an envelope: {agentId, url, status, contentType, body, paymentSucceeded}
    # v3.x returns the API response directly (no envelope).
    # Detect envelope by checking for v1.x-specific keys.
    if isinstance(parsed, dict) and "body" in parsed and "paymentSucceeded" in parsed:
        log(f"lobster v1.x envelope: status={parsed.get('status')} paid={parsed.get('paymentSucceeded')}")
        body = parsed["body"]
        if isinstance(body, dict) or isinstance(body, list):
            return body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return parsed
        return parsed

    # v3.x: parsed IS the API response
    return parsed


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
        "Lobster is the recommended way to use last30days — no API keys needed.\n"
        "\n"
        "1. Install the Lobster CLI:\n"
        "   npm install -g @crossmint/lobster-cli\n"
        "\n"
        "2. Set up and register an agent:\n"
        "   lobster setup\n"
        "   lobster agents register --name last30days-agent\n"
        "\n"
        "3. Fund your wallet with USDC on Solana to enable x402 payments.\n"
        "   Run `lobster crypto balance` to see your wallet address and balance.\n"
        "   A typical research run costs $0.10-0.50 — even $5 will last many runs.\n"
        "\n"
        "4. Verify setup:\n"
        "   lobster status\n"
        "\n"
        "Once funded, re-run /last30days and it will auto-detect your wallet.\n"
        "\n"
        "Learn more: https://lobster.cash\n"
    )
