"""Tests for kopi_cli/kopi_balance.py — the KOPI Proxy token-quota data source.

Payload fixtures are the real bodies returned by the production proxy
(https://kopiaiagent.com/v1/{balance,pricing}) captured 2026-07-23.
"""

from __future__ import annotations

import pytest

from kopi_cli import kopi_balance as kb

# Real /v1/balance body.
BALANCE_PAYLOAD = {
    "client_id": 100094,
    "name": "auto-43251c39",
    "key_prefix": "kopi-fa4b3b60537",
    "is_active": True,
    "quota_limit": 5_000_000,
    "quota_used": 394_884,
    "quota_remaining": 4_605_116,
    "total_requests": 36,
    "is_unlimited": False,
}

# Real /v1/pricing body (trimmed to a representative subset of models).
PRICING_PAYLOAD = {
    "account": {
        "client": "auto-43251c39",
        "key_prefix": "kopi-fa4b3b60537",
        "quota_limit": 5_000_000,
        "quota_remaining": 4_605_116,
        "quota_used": 394_884,
        "unit": "tokens",
    },
    "currency": "USD",
    "unit": "per 1M tokens",
    "models": {
        "kopi-flash": {"context": "128K", "desc": "DeepSeek V4 Pro - ultra fast", "input": 0.5, "output": 1.5, "tier": 3},
        "kopi-opus": {"context": "1M", "desc": "Claude Opus 4.6 - deep analysis", "input": 7.0, "output": 35.0, "tier": 1},
    },
}


@pytest.fixture(autouse=True)
def _clean_caches_and_env(monkeypatch):
    """Isolate every test: fresh caches + deterministic credentials, no config/network."""
    kb.reset_caches()
    monkeypatch.setenv("KOPI_PROXY_BASE_URL", "https://proxy.test/v1")
    monkeypatch.setenv("KOPI_API_KEY", "kopi-test-key")
    # Never let credential resolution touch the real config on disk.
    monkeypatch.setattr(kb, "_resolve_kopi_credentials", lambda: ("kopi-test-key", "https://proxy.test/v1"))
    yield
    kb.reset_caches()


def _stub_get(monkeypatch, mapping):
    """Route _get_json by URL suffix; unknown URLs return None."""
    def fake(url, api_key, *, timeout=8):
        for suffix, body in mapping.items():
            if url.endswith(suffix):
                return body
        return None
    monkeypatch.setattr(kb, "_get_json", fake)


# --- balance parsing --------------------------------------------------------


def test_fetch_balance_parses_real_payload(monkeypatch):
    _stub_get(monkeypatch, {"/balance": BALANCE_PAYLOAD})
    bal = kb.fetch_kopi_balance()
    assert bal is not None
    assert bal.quota_limit == 5_000_000
    assert bal.quota_used == 394_884
    assert bal.quota_remaining == 4_605_116
    assert bal.total_requests == 36
    assert bal.is_unlimited is False
    assert bal.client_name == "auto-43251c39"
    assert bal.key_prefix == "kopi-fa4b3b60537"


def test_percentage_computed_when_absent(monkeypatch):
    # /v1/balance omits percentage_used -> derive from used/limit (7.9%).
    _stub_get(monkeypatch, {"/balance": BALANCE_PAYLOAD})
    assert kb.fetch_kopi_balance().percentage_used == 7.9


def test_percentage_prefers_server_value(monkeypatch):
    _stub_get(monkeypatch, {"/balance": {**BALANCE_PAYLOAD, "percentage_used": 12.5}})
    assert kb.fetch_kopi_balance().percentage_used == 12.5


def test_remaining_defaulted_when_missing(monkeypatch):
    payload = {"quota_limit": 100, "quota_used": 30}
    _stub_get(monkeypatch, {"/balance": payload})
    assert kb.fetch_kopi_balance().quota_remaining == 70


def test_low_and_depleted_flags(monkeypatch):
    _stub_get(monkeypatch, {"/balance": {"quota_limit": 100, "quota_used": 95, "quota_remaining": 5}})
    bal = kb.fetch_kopi_balance()
    assert bal.is_low is True and bal.is_depleted is False

    kb.reset_caches()
    _stub_get(monkeypatch, {"/balance": {"quota_limit": 100, "quota_used": 100, "quota_remaining": 0}})
    bal = kb.fetch_kopi_balance()
    assert bal.is_depleted is True


def test_unlimited_never_low_or_depleted(monkeypatch):
    _stub_get(monkeypatch, {"/balance": {"quota_limit": 0, "quota_used": 0, "quota_remaining": 0, "is_unlimited": True}})
    bal = kb.fetch_kopi_balance()
    assert bal.is_unlimited is True
    assert bal.is_low is False and bal.is_depleted is False


# --- best-effort degradation ------------------------------------------------


def test_balance_none_on_network_failure(monkeypatch):
    _stub_get(monkeypatch, {})  # every URL -> None
    assert kb.fetch_kopi_balance() is None


def test_balance_none_on_non_dict_body(monkeypatch):
    monkeypatch.setattr(kb, "_get_json", lambda *a, **k: None)
    assert kb.fetch_kopi_balance() is None


# --- pricing parsing --------------------------------------------------------


def test_fetch_pricing_parses_models(monkeypatch):
    _stub_get(monkeypatch, {"/pricing": PRICING_PAYLOAD})
    pricing = kb.fetch_kopi_pricing()
    assert set(pricing) == {"kopi-flash", "kopi-opus"}
    flash = pricing["kopi-flash"]
    assert flash.input_per_mtok == 0.5
    assert flash.output_per_mtok == 1.5
    assert flash.tier == 3
    assert flash.context == "128K"
    assert "DeepSeek" in flash.description


def test_pricing_empty_on_failure(monkeypatch):
    _stub_get(monkeypatch, {})
    assert kb.fetch_kopi_pricing() == {}


def test_pricing_skips_malformed_rows(monkeypatch):
    _stub_get(monkeypatch, {"/pricing": {"models": {"kopi-x": "not-a-dict", "kopi-flash": PRICING_PAYLOAD["models"]["kopi-flash"]}}})
    pricing = kb.fetch_kopi_pricing()
    assert set(pricing) == {"kopi-flash"}


# --- caching ----------------------------------------------------------------


def test_balance_cached_between_calls(monkeypatch):
    calls = {"n": 0}

    def fake(url, api_key, *, timeout=8):
        calls["n"] += 1
        return BALANCE_PAYLOAD

    monkeypatch.setattr(kb, "_get_json", fake)
    kb.fetch_kopi_balance()
    kb.fetch_kopi_balance()
    assert calls["n"] == 1  # second call served from cache


def test_force_fresh_bypasses_cache(monkeypatch):
    calls = {"n": 0}

    def fake(url, api_key, *, timeout=8):
        calls["n"] += 1
        return BALANCE_PAYLOAD

    monkeypatch.setattr(kb, "_get_json", fake)
    kb.fetch_kopi_balance()
    kb.fetch_kopi_balance(force_fresh=True)
    assert calls["n"] == 2


def test_failed_fetch_is_cached_too(monkeypatch):
    """An unreachable proxy must not be re-probed on every keystroke."""
    calls = {"n": 0}

    def fake(url, api_key, *, timeout=8):
        calls["n"] += 1
        return None

    monkeypatch.setattr(kb, "_get_json", fake)
    assert kb.fetch_kopi_balance() is None
    assert kb.fetch_kopi_balance() is None
    assert calls["n"] == 1


# --- display helpers --------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "expected"),
    [(4_605_116, "4.6M"), (5_000_000, "5M"), (900, "900"), (2_500, "2.5K"), (1_200_000_000, "1.2B"), (0, "0")],
)
def test_format_token_count(n, expected):
    assert kb.format_token_count(n) == expected


def test_format_quota_summary_metered(monkeypatch):
    _stub_get(monkeypatch, {"/balance": BALANCE_PAYLOAD})
    line = kb.format_quota_summary(kb.fetch_kopi_balance())
    assert line == "4.6M / 5M tokens left · 7.9% used · 36 requests"


def test_format_quota_summary_unlimited():
    bal = kb.KopiBalance(0, 0, 0, 0.0, 1, True, True, "acct", "kopi-x")
    assert kb.format_quota_summary(bal) == "Unlimited quota · 1 request"


# --- credential resolution (exercise the real resolver, not the stub) -------


def test_credential_env_precedence(monkeypatch):
    monkeypatch.undo()  # drop the autouse resolver stub + env
    kb.reset_caches()
    monkeypatch.setenv("KOPI_PROXY_BASE_URL", "https://override.test/v2")
    monkeypatch.setenv("KOPI_API_KEY", "env-key")
    # Force config resolution to no-op so only env is consulted.
    import kopi_cli.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "load_config", lambda: {}, raising=True)
    key, base = kb._resolve_kopi_credentials()
    assert base == "https://override.test/v2"
    assert key == "env-key"


# --- pricing conversion + proxy detection ----------------------------------


@pytest.mark.parametrize(
    ("per_mtok", "expected_back"),
    [(0.5, 0.5), (15.0, 15.0), (0.74, 0.74), (0.0, 0.0)],
)
def test_per_mtok_to_per_token_roundtrips(per_mtok, expected_back):
    s = kb.per_mtok_to_per_token(per_mtok)
    assert float(s) * 1_000_000 == pytest.approx(expected_back)


def test_per_mtok_zero_is_free_marker():
    # "0" flows through _format_price_per_mtok as "free".
    assert kb.per_mtok_to_per_token(0) == "0"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://kopiaiagent.com/v1", True),
        ("https://kopiaiagent.com/v2", True),
        ("https://api.kopiaiagent.com/v1", True),
        ("kopiaiagent.com/v2", True),
        ("https://api.openai.com/v1", False),
        ("", False),
    ],
)
def test_is_kopi_proxy_base(url, expected):
    assert kb.is_kopi_proxy_base(url) is expected


def test_is_kopi_proxy_base_self_hosted(monkeypatch):
    # A self-hosted proxy matches when it equals the resolved KOPI base host.
    monkeypatch.setattr(kb, "_resolve_kopi_credentials", lambda: ("k", "https://kopi.acme.internal/v1"))
    assert kb.is_kopi_proxy_base("https://kopi.acme.internal/v1") is True
    assert kb.is_kopi_proxy_base("https://other.internal/v1") is False


# --- usage bar -------------------------------------------------------------


@pytest.mark.parametrize(
    ("pct", "filled", "empty"),
    [(0.0, 0, 20), (50.0, 10, 10), (100.0, 20, 0), (7.9, 2, 18)],
)
def test_format_quota_bar(pct, filled, empty):
    bar = kb.format_quota_bar(pct)
    assert bar.count("▓") == filled
    assert bar.count("░") == empty
    assert bar.endswith(f"{pct:.1f}%")


def test_format_quota_bar_clamps_out_of_range():
    assert kb.format_quota_bar(150).count("▓") == 20
    assert kb.format_quota_bar(-5).count("▓") == 0
