"""KOPI Proxy provider profile — the default provider for KOPI AI AGENT.

Routes all kopi-* model names through the KOPI Proxy at kopiaiagent.com,
which handles upstream routing, failover, and circuit breaking.

The endpoint is configurable: set ``KOPI_PROXY_BASE_URL`` to point at a
different deployment or API version (e.g. ``https://kopiaiagent.com/v3``).
Defaults to the production ``/v1`` endpoint.
"""

import os

from providers import register_provider
from providers.base import ProviderProfile

DEFAULT_KOPI_PROXY_BASE_URL = "https://kopiaiagent.com/v1"

_base_url = (
    os.getenv("KOPI_PROXY_BASE_URL", "").strip().rstrip("/")
    or DEFAULT_KOPI_PROXY_BASE_URL
)

kopi_proxy = ProviderProfile(
    name="kopi-proxy",
    aliases=(
        "kopi",
        "kopi-o",
        "kopi-o-pro",
        "kopi-flash",
        "KOPI Proxy",
        "kopiaiagent",
    ),
    # KOPI_PROXY_BASE_URL is listed so provider_catalog() surfaces it as the
    # base-URL override var (the *_BASE_URL suffix convention keeps it out of
    # the API-key var list).
    env_vars=("KOPI_PROXY_API_KEY", "KOPI_PROXY_BASE_URL"),
    base_url=_base_url,
    supports_health_check=False,
    supports_vision=True,
    supports_vision_tool_messages=True,
)

register_provider(kopi_proxy)
