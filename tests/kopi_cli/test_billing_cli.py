"""Tests for the /billing CLI handler (cli.py::_show_billing).

Focus on the non-interactive (no live prompt_toolkit app) path — the same
discipline as the /credits non-interactive test: it must render text, never
invoke the modal (which would read the slash-worker's JSON-RPC stdin and hang).
Plus role/kill-switch gating and logged-out handling.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import agent.billing_view as bv
from agent.billing_view import BillingState, CardInfo, MonthlyCap
from cli import KopiCLI


@pytest.fixture
def cli():
    obj = KopiCLI.__new__(KopiCLI)  # bypass __init__ (no full app needed)
    obj._app = None  # non-interactive: forces the text path
    return obj


def _boom_modal(*a, **kw):
    raise AssertionError("modal must NOT be called in non-interactive mode")








# ── Card visibility + the add-card path (inline w/ NAS card-resolver) ──


def _scripted(*responses):
    it = iter(responses)

    def _modal(self, **kw):
        return next(it)

    return _modal


# ── Gateway mode (kopi_ virtual key, no portal login) ────────────────────────


def _logged_out(monkeypatch):
    """Stub build_billing_state → a logged-out state (drives the gateway branch)."""
    from types import SimpleNamespace

    monkeypatch.setattr(bv, "build_billing_state", lambda *a, **kw: SimpleNamespace(logged_in=False, error=None))


def test_gateway_topup_creates_checkout_and_opens_url(cli, monkeypatch, capsys):
    _logged_out(monkeypatch)
    import kopi_cli.kopi_topup as ktm

    monkeypatch.setattr(ktm, "gateway_topup_available", lambda: True)
    seen = {}

    def _checkout(amount, **kw):
        seen["amount"] = amount
        return "https://checkout.stripe.com/c/pay/xyz"

    monkeypatch.setattr(ktm, "create_topup_checkout", _checkout)
    import webbrowser

    opened = {}
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.setdefault("url", url))

    cli._show_billing("/topup 100")
    out = capsys.readouterr().out

    assert seen["amount"] == "100"
    assert "https://checkout.stripe.com/c/pay/xyz" in out
    assert opened["url"] == "https://checkout.stripe.com/c/pay/xyz"
    # Never falls through to the portal-login hint.
    assert "Not logged into Nous Portal" not in out


def test_gateway_topup_bare_command_prints_usage_and_makes_no_call(cli, monkeypatch, capsys):
    _logged_out(monkeypatch)
    import kopi_cli.kopi_topup as ktm

    monkeypatch.setattr(ktm, "gateway_topup_available", lambda: True)

    def _boom(*a, **kw):
        raise AssertionError("create_topup_checkout must not run without an amount")

    monkeypatch.setattr(ktm, "create_topup_checkout", _boom)

    cli._show_billing("/topup")
    out = capsys.readouterr().out
    assert "/topup <amount>" in out


def test_gateway_topup_error_surfaces_message(cli, monkeypatch, capsys):
    _logged_out(monkeypatch)
    import kopi_cli.kopi_topup as ktm

    monkeypatch.setattr(ktm, "gateway_topup_available", lambda: True)

    def _raise(*a, **kw):
        raise ktm.TopupError("Gateway rejected the top-up (HTTP 401).", code="http_401")

    monkeypatch.setattr(ktm, "create_topup_checkout", _raise)

    cli._show_billing("/topup 50")
    out = capsys.readouterr().out
    assert "Could not start the top-up" in out
    assert "HTTP 401" in out


def test_not_gateway_falls_through_to_portal_hint(cli, monkeypatch, capsys):
    _logged_out(monkeypatch)
    import kopi_cli.kopi_topup as ktm

    monkeypatch.setattr(ktm, "gateway_topup_available", lambda: False)

    cli._show_billing("/topup 100")
    out = capsys.readouterr().out
    assert "Not logged into Nous Portal" in out


def test_topup_overview_splits_onetime_from_automatic_copy(cli, monkeypatch, capsys):
    # (c): the interactive /topup overview states the one-time-vs-automatic
    # distinction up front in each first sentence, and keeps "credits" out of the
    # dollars-only surface. Auto-reload OFF → the automatic line omits amounts.
    cli._app = object()  # interactive → reaches the split-copy explainer
    state = BillingState(
        logged_in=True, role="OWNER", balance_usd=Decimal("50"),
        cli_billing_enabled=True, charge_presets=(Decimal("25"),),
        card=CardInfo(brand="Visa", last4="4242"),
        portal_url="https://portal/billing",
    )
    monkeypatch.setattr(bv, "build_billing_state", lambda *a, **kw: state)
    # Overview prints the explainer, then the action modal → back out with "cancel".
    monkeypatch.setattr(KopiCLI, "_prompt_text_input_modal", _scripted("cancel"), raising=False)
    cli._show_billing("/topup")
    out = capsys.readouterr().out

    assert "Add funds now — a single charge, added to your balance today." in out
    assert "Refill when low — charges your card automatically when your balance falls below" in out
    # Dollars-only surface: no "credits" word leaks into /topup.
    assert "credits" not in out.lower()


def test_topup_automatic_copy_generic_when_amounts_missing(cli, monkeypatch, capsys):
    # (5): auto-reload "enabled" but amounts absent (partial response) → generic
    # copy, never "charges — automatically … below —.".
    from agent.billing_view import AutoReload

    cli._app = object()
    state = BillingState(
        logged_in=True, role="OWNER", balance_usd=Decimal("50"),
        cli_billing_enabled=True, charge_presets=(Decimal("25"),),
        card=CardInfo(brand="Visa", last4="4242"),
        auto_reload=AutoReload(enabled=True, threshold_usd=None, reload_to_usd=None),
        portal_url="https://portal/billing",
    )
    monkeypatch.setattr(bv, "build_billing_state", lambda *a, **kw: state)
    monkeypatch.setattr(KopiCLI, "_prompt_text_input_modal", _scripted("cancel"), raising=False)
    cli._show_billing("/topup")
    out = capsys.readouterr().out

    assert (
        "Refill when low — charges your card automatically when your balance "
        "falls below the amount you set."
    ) in out
    assert "charges — automatically" not in out








def test_buy_flow_no_card_back_abandons(cli, monkeypatch, capsys):
    cli._app = object()
    nocard = BillingState(
        logged_in=True, role="OWNER", cli_billing_enabled=True,
        charge_presets=(Decimal("25"),), card=None,
        portal_url="https://portal/billing",
    )
    calls = {"n": 0}

    def _no_fetch(*a, **kw):
        calls["n"] += 1
        return nocard

    monkeypatch.setattr(bv, "build_billing_state", _no_fetch)
    monkeypatch.setattr(KopiCLI, "_prompt_text_input_modal", _scripted("cancel"), raising=False)

    cli._billing_buy_flow(nocard)
    out = capsys.readouterr().out

    assert "Add a card first" in out
    assert "Cancelled. No funds added." in out
    assert calls["n"] == 0  # backed out before any re-check
