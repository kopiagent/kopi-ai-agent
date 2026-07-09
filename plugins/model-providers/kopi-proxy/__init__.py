"""KOPI Proxy provider profile — the default provider for KOPI AI AGENT.

Routes all kopi-* model names through the KOPI Proxy at kopiaiagent.com,
which handles upstream routing, failover, and circuit breaking.
"""

from providers import register_provider
from providers.base import ProviderProfile

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
    env_vars=("KOPI_PROXY_API_KEY",),
    base_url="https://kopiaiagent.com/v1",
    supports_health_check=False,
    supports_vision=True,
    supports_vision_tool_messages=True,
)

register_provider(kopi_proxy)
