"""Tests for the /balance messaging-gateway handler (gateway._handle_balance_command).

/balance is gateway-known (registers on Telegram/Discord; Slack via /kopi balance).
"""

from __future__ import annotations

import asyncio
import inspect
import types

import pytest

from kopi_cli import kopi_balance as kb
import gateway.slash_commands as gsc


def _handler():
    cls = next(c for _n, c in inspect.getmembers(gsc, inspect.isclass) if hasattr(c, "_handle_balance_command"))
    return cls._handle_balance_command.__get__(types.SimpleNamespace())


def _balance(**over):
    base = dict(
        quota_limit=5_000_000, quota_used=394_884, quota_remaining=4_605_116,
        percentage_used=7.9, total_requests=42, is_unlimited=False,
        is_active=True, client_name="auto-x", key_prefix="kopi-fa4b",
    )
    base.update(over)
    return kb.KopiBalance(**base)


def test_balance_registered_on_gateway_and_telegram():
    from kopi_cli.commands import is_gateway_known_command, telegram_bot_commands, _SLACK_VIA_KOPI_ONLY
    assert is_gateway_known_command("balance") is True
    assert "balance" in {n for n, _ in telegram_bot_commands()}
    # Slack: routed via /kopi balance to stay under the 50-slash cap.
    assert "balance" in _SLACK_VIA_KOPI_ONLY


def test_handler_renders_quota(monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *a, **k: _balance())
    out = asyncio.new_event_loop().run_until_complete(_handler()(None))
    assert "KOPI balance" in out
    assert "4.6M / 5M tokens left" in out
    assert "auto-x" in out and "kopi-fa4b" in out


def test_handler_unavailable(monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *a, **k: None)
    out = asyncio.new_event_loop().run_until_complete(_handler()(None))
    assert "unreachable" in out.lower() or "unavailable" in out.lower()


def test_handler_depleted_warns_402(monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance",
                        lambda *a, **k: _balance(quota_used=5_000_000, quota_remaining=0, percentage_used=100.0))
    out = asyncio.new_event_loop().run_until_complete(_handler()(None))
    assert "402" in out and "exhausted" in out.lower()


def test_handler_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("net")
    monkeypatch.setattr(kb, "fetch_kopi_balance", boom)
    out = asyncio.new_event_loop().run_until_complete(_handler()(None))
    assert "unreachable" in out.lower() or "unavailable" in out.lower()
