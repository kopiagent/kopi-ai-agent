"""Tests for inventory._apply_pricing — the pricing/tier enrichment that

feeds the desktop GUI model picker (and onboarding) so it can show $/Mtok
columns + Free/Pro badges and gate paid models on free Nous accounts, the
same way the `kopi model` CLI picker does.
"""

import kopi_cli.inventory as inv
import kopi_cli.models as models_mod


def _patch_pricing(monkeypatch, *, free_tier, pricing, unavailable=None):
    monkeypatch.setattr(models_mod, "get_pricing_for_provider", lambda slug, **kw: pricing.get(slug, {}))
    monkeypatch.setattr(models_mod, "check_nous_free_tier", lambda *, force_fresh=False: free_tier)
    monkeypatch.setattr(
        models_mod, "partition_nous_models_by_tier",
        lambda ids, pr, free_tier: (
            [m for m in ids if m not in (unavailable or [])],
            list(unavailable or []),
        ),
    )


def test_apply_pricing_formats_per_model_prices(monkeypatch):
    """Each model gets formatted input/output/cache + a free flag."""
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={
            "openrouter": {
                "a/paid": {"prompt": "0.000003", "completion": "0.000015", "input_cache_read": "0.0000003"},
                "b/free": {"prompt": "0", "completion": "0"},
            }
        },
    )
    rows = [{"slug": "openrouter", "models": ["a/paid", "b/free"]}]
    inv._apply_pricing(rows)

    pricing = rows[0]["pricing"]
    assert pricing["a/paid"] == {"input": "$3.00", "output": "$15.00", "cache": "$0.30", "free": False}
    assert pricing["b/free"]["free"] is True
    assert pricing["b/free"]["input"] == "free"


def test_apply_pricing_nous_free_tier_gates_paid_models(monkeypatch):
    """A free-tier Nous account marks paid models unavailable and sets the flag."""
    _patch_pricing(
        monkeypatch,
        free_tier=True,
        pricing={
            "nous": {
                "free/model": {"prompt": "0", "completion": "0"},
                "paid/model": {"prompt": "0.000005", "completion": "0.00001"},
            }
        },
        unavailable=["paid/model"],
    )
    rows = [{"slug": "nous", "models": ["free/model", "paid/model"]}]
    inv._apply_pricing(rows)

    assert rows[0]["free_tier"] is True
    assert rows[0]["unavailable_models"] == ["paid/model"]
    assert rows[0]["pricing"]["free/model"]["free"] is True


def test_apply_pricing_nous_paid_tier_no_gating(monkeypatch):
    """A paid Nous account gates nothing."""
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={"nous": {"x/model": {"prompt": "0.000001", "completion": "0.000002"}}},
    )
    rows = [{"slug": "nous", "models": ["x/model"]}]
    inv._apply_pricing(rows)

    assert rows[0]["free_tier"] is False
    assert rows[0]["unavailable_models"] == []


def test_apply_pricing_skips_providers_without_pricing(monkeypatch):
    """A provider with no live pricing simply gets no pricing key."""
    _patch_pricing(monkeypatch, free_tier=False, pricing={})
    rows = [{"slug": "anthropic", "models": ["claude-x"]}]
    inv._apply_pricing(rows)

    assert "pricing" not in rows[0]


def test_apply_pricing_failure_is_swallowed(monkeypatch):
    """A pricing fetch that raises must not break the whole payload."""
    def boom(slug, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(models_mod, "get_pricing_for_provider", boom)
    rows = [{"slug": "openrouter", "models": ["a/b"]}]
    inv._apply_pricing(rows)  # must not raise

    assert "pricing" not in rows[0]


def test_apply_pricing_emits_sale_fields_when_original_cheaper(monkeypatch):
    """Gateway pricing.original → was_* + discount_percent for Desktop."""
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={
            "nous": {
                "a/sale": {
                    "prompt": "0.0000016",
                    "completion": "0.000008",
                    "original": {
                        "prompt": "0.000002",
                        "completion": "0.00001",
                    },
                },
                "b/normal": {
                    "prompt": "0.000003",
                    "completion": "0.000015",
                },
            }
        },
    )
    rows = [{"slug": "nous", "models": ["a/sale", "b/normal"]}]
    inv._apply_pricing(rows)

    sale = rows[0]["pricing"]["a/sale"]
    assert sale["input"] == "$1.60"
    assert sale["output"] == "$8.00"
    assert sale["discount_percent"] == 20
    assert sale["was_input"] == "$2.00"
    assert sale["was_output"] == "$10.00"

    normal = rows[0]["pricing"]["b/normal"]
    assert "discount_percent" not in normal
    assert "was_input" not in normal
    assert "was_output" not in normal


def test_apply_pricing_omits_sale_for_free_models_even_with_original(monkeypatch):
    """Free models must not get was_*/discount_percent even if original leaked."""
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={
            "nous": {
                "a/free": {
                    "prompt": "0",
                    "completion": "0",
                    "original": {
                        "prompt": "0.000002",
                        "completion": "0.00001",
                    },
                },
            }
        },
    )
    rows = [{"slug": "nous", "models": ["a/free"]}]
    inv._apply_pricing(rows)
    free = rows[0]["pricing"]["a/free"]
    assert free["free"] is True
    assert "discount_percent" not in free
    assert "was_input" not in free
    assert "was_output" not in free


def test_apply_pricing_omits_sale_when_original_not_cheaper(monkeypatch):
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={
            "nous": {
                "a/eq": {
                    "prompt": "0.000002",
                    "completion": "0.00001",
                    "original": {
                        "prompt": "0.000002",
                        "completion": "0.00001",
                    },
                },
            }
        },
    )
    rows = [{"slug": "nous", "models": ["a/eq"]}]
    inv._apply_pricing(rows)
    assert "discount_percent" not in rows[0]["pricing"]["a/eq"]


def test_apply_pricing_sale_chrome_nous_only(monkeypatch):
    """OpenRouter (and other non-nous slugs) must never emit sale fields."""
    _patch_pricing(
        monkeypatch,
        free_tier=False,
        pricing={
            "openrouter": {
                "a/sale": {
                    "prompt": "0.0000016",
                    "completion": "0.000008",
                    "original": {
                        "prompt": "0.000002",
                        "completion": "0.00001",
                    },
                },
            }
        },
    )
    rows = [{"slug": "openrouter", "models": ["a/sale"]}]
    inv._apply_pricing(rows)
    entry = rows[0]["pricing"]["a/sale"]
    assert entry["input"] == "$1.60"
    assert "discount_percent" not in entry
    assert "was_input" not in entry
    assert "was_output" not in entry


# --- KOPI Proxy custom row -------------------------------------------------
#
# The KOPI Proxy runs as a bare ``custom`` provider (config provider: custom,
# base_url: https://kopiaiagent.com/v2), so get_pricing_for_provider("custom")
# returns nothing. _apply_pricing must back-fill from the proxy's /pricing
# table for the current custom row when its base_url is the KOPI proxy.


def _patch_kopi_pricing(monkeypatch, models):
    """Stub kopi_balance.fetch_kopi_pricing with {model: KopiModelPrice}."""
    from kopi_cli import kopi_balance

    monkeypatch.setattr(models_mod, "get_pricing_for_provider", lambda slug, **kw: {})
    monkeypatch.setattr(kopi_balance, "fetch_kopi_pricing", lambda *, force_fresh=False: models)


def test_apply_pricing_kopi_custom_row_gets_proxy_pricing(monkeypatch):
    from kopi_cli.kopi_balance import KopiModelPrice

    _patch_kopi_pricing(
        monkeypatch,
        {
            "kopi-flash": KopiModelPrice("kopi-flash", 0.5, 1.5, 3, "128K", "DeepSeek"),
            "kopi-gpt5": KopiModelPrice("kopi-gpt5", 5.0, 15.0, 1, "1.05M", "GPT-5.5"),
        },
    )
    rows = [{"slug": "custom", "is_current": True, "models": ["kopi-flash", "kopi-gpt5", "kopi-unknown"]}]
    inv._apply_pricing(rows, current_base_url="https://kopiaiagent.com/v2")

    pricing = rows[0]["pricing"]
    # $/1M-token prices round-trip through the shared per-token formatter.
    assert pricing["kopi-flash"] == {"input": "$0.50", "output": "$1.50", "cache": None, "free": False}
    assert pricing["kopi-gpt5"]["input"] == "$5.00" and pricing["kopi-gpt5"]["output"] == "$15.00"
    # A model absent from /pricing simply gets no entry.
    assert "kopi-unknown" not in pricing


def test_apply_pricing_kopi_skipped_for_non_proxy_base(monkeypatch):
    from kopi_cli.kopi_balance import KopiModelPrice

    _patch_kopi_pricing(monkeypatch, {"kopi-flash": KopiModelPrice("kopi-flash", 0.5, 1.5, 3, "128K", "x")})
    rows = [{"slug": "custom", "is_current": True, "models": ["kopi-flash"]}]
    # A non-KOPI custom endpoint must NOT get KOPI proxy prices.
    inv._apply_pricing(rows, current_base_url="https://api.openai.com/v1")
    assert "pricing" not in rows[0]


def test_apply_pricing_kopi_skipped_for_non_current_row(monkeypatch):
    from kopi_cli.kopi_balance import KopiModelPrice

    _patch_kopi_pricing(monkeypatch, {"kopi-flash": KopiModelPrice("kopi-flash", 0.5, 1.5, 3, "128K", "x")})
    rows = [{"slug": "custom", "is_current": False, "models": ["kopi-flash"]}]
    inv._apply_pricing(rows, current_base_url="https://kopiaiagent.com/v2")
    assert "pricing" not in rows[0]
