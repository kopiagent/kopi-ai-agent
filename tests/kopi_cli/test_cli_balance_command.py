"""Tests for the /balance CLI command (cli_billing_mixin._show_kopi_balance)."""

from __future__ import annotations

import sys
import types

import pytest

from kopi_cli import kopi_balance as kb
from kopi_cli.cli_billing_mixin import CLIBillingMixin


@pytest.fixture
def captured(monkeypatch):
    """Fake the cli.py display helpers so the mixin renders into a list."""
    lines: list[str] = []
    fake_cli = types.ModuleType("cli")
    fake_cli._cprint = lambda s="": lines.append(s)
    fake_cli._b = lambda s: s
    fake_cli._d = lambda s: s
    monkeypatch.setitem(sys.modules, "cli", fake_cli)
    return lines


def _obj():
    return type("X", (CLIBillingMixin,), {})()


def _balance(**over):
    base = dict(
        quota_limit=5_000_000, quota_used=394_884, quota_remaining=4_605_116,
        percentage_used=7.9, total_requests=37, is_unlimited=False,
        is_active=True, client_name="auto-43251c39", key_prefix="kopi-fa4b",
    )
    base.update(over)
    return kb.KopiBalance(**base)


def test_balance_renders_quota_and_identity(captured, monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *, force_fresh=False: _balance())
    _obj()._show_kopi_balance()
    blob = "\n".join(captured)
    assert "KOPI balance" in blob
    assert "4.6M / 5M tokens left" in blob
    assert "7.9%" in blob  # summary + bar
    assert "auto-43251c39" in blob and "kopi-fa4b" in blob
    assert "!" not in blob  # not low/depleted


def test_balance_unavailable_is_graceful(captured, monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *, force_fresh=False: None)
    _obj()._show_kopi_balance()
    blob = "\n".join(captured)
    assert "KOPI balance" in blob
    assert "unreachable" in blob.lower()


def test_balance_never_raises_on_fetch_error(captured, monkeypatch):
    def boom(*, force_fresh=False):
        raise RuntimeError("network")

    monkeypatch.setattr(kb, "fetch_kopi_balance", boom)
    _obj()._show_kopi_balance()  # must not raise
    assert "unreachable" in "\n".join(captured).lower()


def test_balance_depleted_warns_402(captured, monkeypatch):
    monkeypatch.setattr(
        kb, "fetch_kopi_balance",
        lambda *, force_fresh=False: _balance(quota_used=5_000_000, quota_remaining=0, percentage_used=100.0),
    )
    _obj()._show_kopi_balance()
    blob = "\n".join(captured)
    assert "402" in blob and "exhausted" in blob.lower()


def test_balance_low_warns(captured, monkeypatch):
    monkeypatch.setattr(
        kb, "fetch_kopi_balance",
        lambda *, force_fresh=False: _balance(quota_used=4_600_000, quota_remaining=400_000, percentage_used=92.0),
    )
    _obj()._show_kopi_balance()
    assert "low quota" in "\n".join(captured).lower()


def test_balance_unlimited_hides_bar(captured, monkeypatch):
    monkeypatch.setattr(
        kb, "fetch_kopi_balance",
        lambda *, force_fresh=False: _balance(is_unlimited=True),
    )
    _obj()._show_kopi_balance()
    blob = "\n".join(captured)
    assert "Unlimited quota" in blob
    assert "▓" not in blob and "░" not in blob  # no bar for unlimited
