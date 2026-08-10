"""Unit coverage for the gateway-mode top-up client (kopi_cli/kopi_topup.py).

The HTTP boundary is ``open_credentialed_url``; every test stubs it so nothing
touches the network. Credential/base resolution is driven purely through env +
a stubbed ``load_config`` so the precedence rules are pinned.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from kopi_cli import kopi_topup as kt


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("KOPI_PROXY_BASE_URL", "KOPI_API_KEY", "KOPI_PROXY_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # Default: config resolves to an empty dict so only env drives resolution.
    # resolve_topup_endpoint imports load_config lazily from kopi_cli.config.
    import kopi_cli.config as cfg

    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: {}, raising=False)


class _FakeResp:
    def __init__(self, body: str):
        self._body = body.encode()

    def read(self):
        return self._body

    def close(self):
        pass


def _stub_http(monkeypatch, *, body=None, exc=None):
    def fake(req, timeout=None):
        if exc is not None:
            raise exc
        fake.captured = req
        return _FakeResp(body)

    fake.captured = None
    monkeypatch.setattr(kt, "open_credentialed_url", fake)
    return fake


# ── endpoint / credential resolution ────────────────────────────────────────


def test_default_host_when_nothing_configured():
    key, url = kt.resolve_topup_endpoint()
    assert key == ""
    assert url == "https://bill.kopiagent.ai/kopi/topup/checkout"


def test_env_base_v1_suffix_is_stripped_to_host(monkeypatch):
    monkeypatch.setenv("KOPI_PROXY_BASE_URL", "https://proxy.test/v1")
    _, url = kt.resolve_topup_endpoint()
    # The top-up route lives at the host root, not under /v1.
    assert url == "https://proxy.test/kopi/topup/checkout"


def test_env_base_legacy_kp_v1_suffix_is_stripped(monkeypatch):
    monkeypatch.setenv("KOPI_PROXY_BASE_URL", "https://proxy.test/kp/v1")
    _, url = kt.resolve_topup_endpoint()
    assert url == "https://proxy.test/kopi/topup/checkout"


def test_config_base_used_when_no_env(monkeypatch):
    import kopi_cli.config as cfg

    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: {"model": {"base_url": "https://cfg.example/v1"}})
    _, url = kt.resolve_topup_endpoint()
    assert url == "https://cfg.example/kopi/topup/checkout"


def test_env_base_beats_config_base(monkeypatch):
    import kopi_cli.config as cfg

    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: {"model": {"base_url": "https://cfg.example/v1"}})
    monkeypatch.setenv("KOPI_PROXY_BASE_URL", "https://env.example/v1")
    _, url = kt.resolve_topup_endpoint()
    assert url == "https://env.example/kopi/topup/checkout"


def test_key_precedence_config_over_env(monkeypatch):
    import kopi_cli.config as cfg

    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: {"model": {"api_key": "kopi_cfg"}})
    monkeypatch.setenv("KOPI_API_KEY", "kopi_env")
    key, _ = kt.resolve_topup_endpoint()
    assert key == "kopi_cfg"


def test_key_env_kopi_api_key_then_proxy(monkeypatch):
    monkeypatch.setenv("KOPI_PROXY_API_KEY", "kopi_proxy")
    key, _ = kt.resolve_topup_endpoint()
    assert key == "kopi_proxy"
    monkeypatch.setenv("KOPI_API_KEY", "kopi_primary")
    key, _ = kt.resolve_topup_endpoint()
    assert key == "kopi_primary"


def test_gateway_available_reflects_key_presence(monkeypatch):
    assert kt.gateway_topup_available() is False
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    assert kt.gateway_topup_available() is True


# ── create_topup_checkout ────────────────────────────────────────────────────


def test_checkout_success_returns_url_and_sends_bearer_and_amount(monkeypatch):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    fake = _stub_http(monkeypatch, body=json.dumps({"checkout_url": "https://checkout.stripe.com/c/pay/abc"}))

    url = kt.create_topup_checkout(100)

    assert url == "https://checkout.stripe.com/c/pay/abc"
    req = fake.captured
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer kopi_live"
    assert json.loads(req.data.decode()) == {"amount_usd": 100}
    assert req.full_url == "https://bill.kopiagent.ai/kopi/topup/checkout"


@pytest.mark.parametrize("field", ["checkout_url", "url", "payment_url", "checkoutUrl"])
def test_checkout_accepts_plausible_url_field_names(monkeypatch, field):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    _stub_http(monkeypatch, body=json.dumps({field: "https://pay.example/x"}))
    assert kt.create_topup_checkout("50") == "https://pay.example/x"


def test_checkout_without_key_raises_not_configured_and_makes_no_call(monkeypatch):
    called = {"hit": False}

    def fake(req, timeout=None):
        called["hit"] = True
        raise AssertionError("must not be called without a key")

    monkeypatch.setattr(kt, "open_credentialed_url", fake)

    with pytest.raises(kt.TopupError) as ei:
        kt.create_topup_checkout(100)
    assert ei.value.code == "not_configured"
    assert called["hit"] is False


def test_checkout_http_error_maps_to_status_code(monkeypatch):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))
    _stub_http(monkeypatch, exc=err)

    with pytest.raises(kt.TopupError) as ei:
        kt.create_topup_checkout(100)
    assert ei.value.code == "http_401"


def test_checkout_transport_failure_is_unreachable(monkeypatch):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    _stub_http(monkeypatch, exc=OSError("connection refused"))

    with pytest.raises(kt.TopupError) as ei:
        kt.create_topup_checkout(100)
    assert ei.value.code == "unreachable"


def test_checkout_non_json_body_is_bad_response(monkeypatch):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    _stub_http(monkeypatch, body="<html>gateway error</html>")

    with pytest.raises(kt.TopupError) as ei:
        kt.create_topup_checkout(100)
    assert ei.value.code == "bad_response"


def test_checkout_json_without_url_is_bad_response(monkeypatch):
    monkeypatch.setenv("KOPI_API_KEY", "kopi_live")
    _stub_http(monkeypatch, body=json.dumps({"ok": True, "session_id": "cs_live_x"}))

    with pytest.raises(kt.TopupError) as ei:
        kt.create_topup_checkout(100)
    assert ei.value.code == "bad_response"
