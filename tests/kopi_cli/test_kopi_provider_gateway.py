"""The fork's own provider ("kopi") must resolve in BOTH provider systems.

Background: this fork ships exactly one user-facing provider, declared as a
plugin profile (``plugins/model-providers/kopi-proxy/``). The plugin registry
is what ``kopi status`` and the ``/model`` picker LIST read; a different module
(``kopi_cli/providers.py``) is what a provider SWITCH resolves against, and it
cannot see the plugin registry. Before this was wired up, the single provider
we offer was listed in the picker and then rejected on selection with
``Unknown provider 'kopi-proxy'`` (reported from a live customer instance,
2026-08-22 — see docs/kopi-gateway-provider-default.md).

These tests pin both halves plus the seeded default endpoint, so a drift in
either registry fails here rather than in a customer's Telegram session.
"""

from pathlib import Path

import dataclasses

import pytest

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GATEWAY_BASE_URL = "https://bill.kopiagent.ai/v1"

# Every spelling that existing configs / operators may have written.
KOPI_ALIASES = ["kopi", "kopi-proxy", "kopi_proxy", "kopiaiagent", "KOPI Proxy"]


# -- Plugin profile (the LIST side) -------------------------------------------

def test_plugin_profile_is_registered_as_kopi_with_proxy_alias():
    from providers import get_provider_profile

    profile = get_provider_profile("kopi")
    assert profile is not None
    assert profile.name == "kopi"
    assert profile.display_name == "KOPI Gateway"
    # Old canonical id must keep resolving: instances provisioned before the
    # rename still carry ``provider: kopi-proxy`` in config.yaml.
    assert get_provider_profile("kopi-proxy") is profile
    assert profile.base_url == GATEWAY_BASE_URL
    assert "KOPI_API_KEY" in profile.env_vars


def test_plugin_profile_carries_offline_model_list():
    """The picker must show models even before a key exists (no live /models)."""
    from providers import get_provider_profile

    models = get_provider_profile("kopi").fallback_models
    assert models, "fallback_models is what /model shows when the live probe can't run"
    assert all(m.startswith("kopi-") for m in models), models


# -- kopi_cli/providers.py (the SWITCH side) ----------------------------------

@pytest.mark.parametrize("name", KOPI_ALIASES)
def test_resolve_provider_full_accepts_every_kopi_spelling(name):
    from kopi_cli.providers import resolve_provider_full

    pdef = resolve_provider_full(name, None, None)
    assert pdef is not None, f"{name!r} must resolve — this is the /model switch path"
    assert pdef.id == "kopi"
    assert pdef.base_url == GATEWAY_BASE_URL
    # The base-URL override var must survive alias resolution, otherwise an
    # instance whose KOPI_PROXY_BASE_URL points at another deployment silently
    # falls back to the production gateway.
    assert pdef.base_url_env_var == "KOPI_PROXY_BASE_URL"
    assert "KOPI_API_KEY" in pdef.api_key_env_vars


def test_alias_entries_do_not_count_as_distinct_providers():
    """Guard for the sibling-collapse check in resolve_provider_full().

    A plugin registers one auth-registry entry per alias, all sharing one id.
    Those must NOT be treated as several providers colliding on one canonical
    name (that path returns an auth-registry def and drops the overlay's
    base_url_env_var). Genuinely distinct siblings must still stay distinct.
    """
    from kopi_cli.providers import resolve_provider_full

    assert resolve_provider_full("kopi-proxy", None, None).source == "kopi"

    cn = resolve_provider_full("kimi-coding-cn", None, None)
    intl = resolve_provider_full("kimi-coding", None, None)
    assert cn is not None and intl is not None
    assert cn.base_url != intl.base_url, "distinct endpoints must not collapse"


@pytest.mark.parametrize("name", ["kopi", "kopi-proxy", "kopiaiagent"])
def test_auth_resolve_provider_maps_aliases_to_kopi(name):
    from kopi_cli.auth import resolve_provider

    assert resolve_provider(name) == "kopi"


# -- Labels + picker ----------------------------------------------------------

def test_provider_label_is_branded_for_both_ids():
    from kopi_cli.models import provider_label

    assert provider_label("kopi") == "KOPI Gateway"
    assert provider_label("kopi-proxy") == "KOPI Gateway"


def test_provider_lock_allows_the_canonical_slug():
    """The lock trims CANONICAL_PROVIDERS to our provider; 'kopi' must be in it.

    (tests/conftest.py sets KOPI_ALL_PROVIDERS=1, so the lock itself is off in
    the suite — assert on the slug set it would keep.)
    """
    from kopi_cli.models import CANONICAL_PROVIDERS, _KOPI_LOCKED_SLUGS

    assert "kopi" in _KOPI_LOCKED_SLUGS
    assert any(p.slug == "kopi" for p in CANONICAL_PROVIDERS)


def test_provider_model_ids_falls_back_to_the_offline_list(monkeypatch):
    from kopi_cli.models import provider_model_ids

    for var in ("KOPI_API_KEY", "KOPI_PROXY_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    ids = provider_model_ids("kopi")
    assert ids, "/model must still list models with no key configured"
    assert "kopi-o" in ids


# -- The reported regression: switching to our own provider ------------------

@pytest.mark.parametrize("requested", ["kopi", "kopi-proxy"])
def test_switch_model_to_kopi_succeeds(monkeypatch, requested):
    """`/model --provider kopi[-proxy]` used to fail with 'Unknown provider'."""
    from kopi_cli.model_switch import switch_model

    monkeypatch.setenv("KOPI_API_KEY", "kopi_testkey")

    result = switch_model(
        "kopi-o",
        current_provider="custom",
        current_model="kopi-o",
        explicit_provider=requested,
    )
    assert result.success, result.error_message
    assert result.target_provider == "kopi"
    assert result.base_url == GATEWAY_BASE_URL
    assert result.api_key == "kopi_testkey"
    assert dataclasses.asdict(result)["api_mode"] == "chat_completions"


# -- Seeded default (what a fresh instance gets) ------------------------------

def test_seeded_config_defaults_to_the_kopi_gateway():
    """install.sh / docker stage2-hook seed config.yaml from this template."""
    cfg = yaml.safe_load((PROJECT_ROOT / "cli-config.yaml.example").read_text())
    model = cfg["model"]

    assert model["provider"] == "kopi"
    assert model["base_url"] == GATEWAY_BASE_URL
    assert model["api_key"] == "${KOPI_API_KEY}"
    # The retired endpoint must not come back as a default.
    assert "kopiaiagent.com" not in model["base_url"]


def test_picker_row_is_findable_by_label():
    """The CLI picker renders a plugin provider's row from ``description`` only.

    A description that doesn't contain the display label makes our row
    impossible to match by label — which is also how
    ``model_catalog.excluded_providers`` exclusion is verified.
    """
    from providers import get_provider_profile

    profile = get_provider_profile("kopi")
    assert profile.description.startswith(profile.display_name), (
        profile.display_name,
        profile.description,
    )
