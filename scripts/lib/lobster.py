"""Lobster.cash CLI wrapper for x402 payment integration (stdlib only)."""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from .http import DEBUG, HTTPError, log


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
        )
        if result.returncode != 0:
            log(f"lobster wallet info failed: {result.stderr.strip()}")
            return False
        data = json.loads(result.stdout)
        return bool(data)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
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
        )
        if result.returncode != 0:
            log(f"lobster balance failed: {result.stderr.strip()}")
            return {}
        return json.loads(result.stdout)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
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
        method: HTTP method (GET or POST).
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

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
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
        "3. Fund your wallet with USDC on Base to enable x402 payments.\n"
        "   Run `lobster wallet info` to see your wallet address.\n"
        "\n"
        "4. Verify setup:\n"
        "   lobster balance\n"
        "\n"
        "Wallet data is stored at: ~/.openclaw/lobster-cash/wallets.json\n"
        "Learn more: https://lobster.cash\n"
    )
