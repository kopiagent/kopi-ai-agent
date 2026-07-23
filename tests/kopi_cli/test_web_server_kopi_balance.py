"""Tests for the GET /api/kopi/balance dashboard route."""

import pytest

from kopi_cli import kopi_balance as kb
from kopi_cli import web_server

pytest.importorskip("starlette.testclient")
from starlette.testclient import TestClient


@pytest.fixture
def client():
    prev = getattr(web_server.app.state, "auth_required", None)
    web_server.app.state.auth_required = False
    c = TestClient(web_server.app)
    c.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    try:
        yield c
    finally:
        if prev is None:
            try:
                delattr(web_server.app.state, "auth_required")
            except AttributeError:
                pass
        else:
            web_server.app.state.auth_required = prev


def _balance(**over):
    base = dict(
        quota_limit=5_000_000, quota_used=394_884, quota_remaining=4_605_116,
        percentage_used=7.9, total_requests=37, is_unlimited=False,
        is_active=True, client_name="auto-43251c39", key_prefix="kopi-fa4b",
    )
    base.update(over)
    return kb.KopiBalance(**base)


def test_balance_route_returns_quota(client, monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *a, **k: _balance())
    r = client.get("/api/kopi/balance")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["quota_remaining"] == 4_605_116
    assert body["percentage_used"] == 7.9
    assert body["is_low"] is False and body["is_depleted"] is False
    assert body["remaining_display"] == "4.6M" and body["limit_display"] == "5M"
    assert "4.6M / 5M tokens left" in body["summary"]
    assert body["key_prefix"] == "kopi-fa4b"


def test_balance_route_unavailable(client, monkeypatch):
    monkeypatch.setattr(kb, "fetch_kopi_balance", lambda *a, **k: None)
    r = client.get("/api/kopi/balance")
    assert r.status_code == 200
    assert r.json() == {"available": False}


def test_balance_route_never_500s_on_error(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(kb, "fetch_kopi_balance", boom)
    r = client.get("/api/kopi/balance")
    assert r.status_code == 200
    assert r.json() == {"available": False}


def test_balance_route_depleted_flag(client, monkeypatch):
    monkeypatch.setattr(
        kb, "fetch_kopi_balance",
        lambda *a, **k: _balance(quota_used=5_000_000, quota_remaining=0, percentage_used=100.0),
    )
    body = client.get("/api/kopi/balance").json()
    assert body["is_depleted"] is True
