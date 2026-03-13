"""Tests for Lobster.cash CLI integration."""
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from lib import lobster
from lib.http import HTTPError


# ---------------------------------------------------------------------------
# is_installed
# ---------------------------------------------------------------------------

@patch("shutil.which", return_value="/usr/local/bin/lobster")
def test_is_installed_true(mock_which):
    assert lobster.is_installed() is True
    mock_which.assert_called_once_with("lobster")


@patch("shutil.which", return_value=None)
def test_is_installed_false(mock_which):
    assert lobster.is_installed() is False
    mock_which.assert_called_once_with("lobster")


# ---------------------------------------------------------------------------
# is_wallet_configured
# ---------------------------------------------------------------------------

@patch("subprocess.run")
def test_is_wallet_configured_true(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"address": "0xabc123", "balance": "1.00"}),
        stderr="",
    )
    assert lobster.is_wallet_configured() is True
    mock_run.assert_called_once_with(
        ["lobster", "wallet", "info"],
        capture_output=True,
        text=True,
    )


@patch("subprocess.run", side_effect=FileNotFoundError("lobster not found"))
def test_is_wallet_configured_false_not_installed(mock_run):
    assert lobster.is_wallet_configured() is False


@patch("subprocess.run")
def test_is_wallet_configured_false_no_wallet(mock_run):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="No wallet configured",
    )
    assert lobster.is_wallet_configured() is False


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

@patch("subprocess.run")
def test_get_balance(mock_run):
    balance_data = {"usdc": "5.25", "network": "base"}
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(balance_data),
        stderr="",
    )
    result = lobster.get_balance()
    assert result == balance_data
    mock_run.assert_called_once_with(
        ["lobster", "balance"],
        capture_output=True,
        text=True,
    )


@patch("subprocess.run")
def test_get_balance_error(mock_run):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="connection error",
    )
    result = lobster.get_balance()
    assert result == {}


# ---------------------------------------------------------------------------
# x402_fetch
# ---------------------------------------------------------------------------

@patch("subprocess.run")
def test_x402_fetch_get(mock_run):
    response_data = {"choices": [{"text": "hello"}]}
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(response_data),
        stderr="",
    )
    result = lobster.x402_fetch("https://openai.api.corbits.dev/v1/responses")
    assert result == response_data

    cmd = mock_run.call_args[0][0]
    assert cmd[0:4] == ["lobster", "x402", "fetch", "https://openai.api.corbits.dev/v1/responses"]
    assert "--json" not in cmd
    assert "--timeout" in cmd


@patch("subprocess.run")
def test_x402_fetch_post(mock_run):
    body = {"model": "gpt-4", "prompt": "hi"}
    response_data = {"id": "resp_1"}
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(response_data),
        stderr="",
    )
    result = lobster.x402_fetch(
        "https://openai.api.corbits.dev/v1/responses",
        method="POST",
        json_data=body,
    )
    assert result == response_data

    cmd = mock_run.call_args[0][0]
    json_flag_idx = cmd.index("--json")
    assert json.loads(cmd[json_flag_idx + 1]) == body


@patch("subprocess.run")
def test_x402_fetch_with_headers(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"ok": True}),
        stderr="",
    )
    lobster.x402_fetch(
        "https://example.com/api",
        headers={"Authorization": "Bearer tok", "X-Custom": "val"},
    )

    cmd = mock_run.call_args[0][0]
    header_indices = [i for i, v in enumerate(cmd) if v == "--header"]
    assert len(header_indices) == 2
    header_values = [cmd[i + 1] for i in header_indices]
    assert "Authorization:Bearer tok" in header_values
    assert "X-Custom:val" in header_values


@patch("subprocess.run")
def test_x402_fetch_error(mock_run):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="payment failed",
    )
    with pytest.raises(HTTPError, match="lobster x402 fetch failed"):
        lobster.x402_fetch("https://example.com/api")


# ---------------------------------------------------------------------------
# get_setup_instructions
# ---------------------------------------------------------------------------

def test_get_setup_instructions():
    instructions = lobster.get_setup_instructions()
    assert isinstance(instructions, str)
    assert len(instructions) > 0
    assert "lobster" in instructions.lower()
    assert "npm install" in instructions
