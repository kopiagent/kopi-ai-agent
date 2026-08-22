"""KOPI provider profile — the default provider for KOPI AI AGENT.

Routes all ``kopi-*`` model names through the KOPI gateway (Kopi TokenMax) at
``bill.kopiagent.ai``, which handles upstream routing, per-key quota, and
billing.

The canonical name is ``kopi`` (the brand the customer sees in ``/model`` and
``kopi status``); ``kopi-proxy`` stays as an alias so instances whose
``config.yaml`` already pins ``provider: kopi-proxy`` keep resolving.

The endpoint is configurable: set ``KOPI_PROXY_BASE_URL`` to point at a
different deployment or API version (e.g. a staging gateway). Defaults to the
production ``/v1`` endpoint.
"""

import os

from providers import register_provider
from providers.base import ProviderProfile

# Production gateway (Kopi TokenMax, OpenAI-compatible). The previous default
# ``kopiaiagent.com`` is retired — it no longer serves inference, so leaving it
# here made every fresh install point at a dead host.
DEFAULT_KOPI_PROXY_BASE_URL = "https://bill.kopiagent.ai/v1"

_base_url = (
    os.getenv("KOPI_PROXY_BASE_URL", "").strip().rstrip("/")
    or DEFAULT_KOPI_PROXY_BASE_URL
)

kopi = ProviderProfile(
    name="kopi",
    aliases=(
        "kopi-proxy",
        "kopi_proxy",
        "KOPI Proxy",
        "kopiaiagent",
        "kopiagent",
    ),
    # NOT "Kopi Official" — that label belongs to the `nous` provider (the
    # Portal/OAuth path, plugins/image_gen/openrouter, web EnvPage). Two rows
    # sharing one label makes the picker ambiguous and breaks label-based
    # exclusion (tests/kopi_cli/test_model_picker_excluded_providers.py).
    display_name="KOPI Gateway",
    # Starts with display_name on purpose: the CLI picker renders a plugin
    # provider's row from `description` alone, so a description that does not
    # contain the label makes the row unfindable by label (and un-excludable).
    description="KOPI Gateway — official kopi-* models, OpenAI-compatible",
    # KOPI_PROXY_BASE_URL is listed so provider_catalog() surfaces it as the
    # base-URL override var (the *_BASE_URL suffix convention keeps it out of
    # the API-key var list). KOPI_API_KEY comes first because that is the name
    # the seeded config.yaml interpolates and the one the container mirrors
    # KOPI_PROXY_API_KEY into.
    env_vars=("KOPI_API_KEY", "KOPI_PROXY_API_KEY", "KOPI_PROXY_BASE_URL"),
    base_url=_base_url,
    supports_health_check=False,
    supports_vision=True,
    supports_vision_tool_messages=True,
    # Offline fallback for the /model picker when the live ``GET /v1/models``
    # probe can't run (no key yet, no network). The gateway is the source of
    # truth — this list only has to be close enough to pick from; it mirrors
    # the 11 customer-visible names the gateway served as of 2026-08-22.
    fallback_models=(
        "kopi-o",
        "kopi-siew-dai",
        "kopi-o-flash",
        "kopi-siew-dai-flash",
        "kopi-flash",
        "kopi-grok-4.5",
        "kopi-grok-4.3",
        "kopi-grok-4.20-0309-reasoning",
        "kopi-free-1-120B",
        "kopi-free-2-20B",
        "kopi-free-3-llama70B",
    ),
)

register_provider(kopi)

# Back-compat for anything importing the old module-level symbol.
kopi_proxy = kopi
