"""Gateway-mode top-up — create a Stripe checkout via the kopi proxy.

Two worlds fund a balance in this CLI:

- **Portal OAuth** (`nous_billing.py`): the rich ``/api/billing/*`` surface —
  saved-card charges, auto-reload, limits — behind a Nous device-flow token.
- **Gateway virtual key** (this module): deployments that authenticate to the
  kopi proxy with a ``kopi_``-prefixed key (``KOPI_API_KEY``) instead of a
  portal login. The proxy exposes a single one-shot funding route,
  ``POST /kopi/topup/checkout`` → a Stripe hosted-checkout URL. There is no
  saved card / auto-reload here; the user pays on Stripe's page in a browser.

Which world ``/topup`` uses is decided by :func:`gateway_topup_available`: a
configured virtual key means gateway mode. See
``docs/pending-product-decisions.md`` §1a for why the portal path is currently
a dead end (``kopiaiagent.com`` offline) and the live gateway is
``bill.kopiagent.ai``.

Endpoint shape: the top-up route lives at the proxy **host root**
(``{host}/kopi/topup/checkout``), whereas the inference base is ``{host}/v1``.
We resolve the same ``(key, base)`` precedence the balance client uses and then
strip the ``/v1`` (or ``/kp/v1``) suffix to recover the host.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from kopi_cli.urllib_security import open_credentialed_url

# The live production gateway (Let's Encrypt, 2026-08-05). The legacy
# kopiaiagent.com default is offline; this is the only host that answers today.
# Configuration (KOPI_PROXY_BASE_URL / config model.base_url) overrides it.
DEFAULT_TOPUP_HOST = "https://bill.kopiagent.ai"

TOPUP_CHECKOUT_PATH = "/kopi/topup/checkout"


class TopupError(Exception):
    """A gateway top-up call did not produce a usable checkout URL.

    ``code`` is a stable, machine-routable slug (``not_configured``,
    ``http_401`` …); ``message`` is human-facing. Kept deliberately simpler than
    ``nous_billing.BillingError`` — the gateway flow has no scope/step-up model.
    """

    def __init__(self, message: str, *, code: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _user_agent() -> str:
    try:
        from kopi_cli import __version__

        return f"kopi-cli/{__version__}"
    except Exception:
        return "kopi-cli"


def _strip_inference_suffix(base: str) -> str:
    """Recover the proxy host root from an inference base URL.

    ``https://host/v1`` and ``https://host/kp/v1`` (the legacy-key path) both
    map to ``https://host``. A base that is already a bare host is unchanged.
    """
    host = base.rstrip("/")
    for suffix in ("/kp/v1", "/v1"):
        if host.endswith(suffix):
            return host[: -len(suffix)]
    return host


def resolve_topup_endpoint() -> tuple[str, str]:
    """Return ``(api_key, checkout_url)`` for the gateway top-up call.

    Mirrors :func:`kopi_cli.kopi_balance._resolve_kopi_credentials` precedence so
    ``/balance`` and ``/topup`` never disagree on which gateway they talk to:
    base_url = ``KOPI_PROXY_BASE_URL`` env > config ``model.base_url`` > the
    production default; api_key = config ``model.api_key`` (already
    ``${VAR}``-expanded by ``load_config``) > ``KOPI_API_KEY`` > ``KOPI_PROXY_API_KEY``.

    A blank key still yields a usable URL so the caller can decide how to
    degrade rather than crashing here.
    """
    cfg_base = ""
    cfg_key = ""
    try:
        from kopi_cli.config import load_config

        cfg = load_config()
        model_cfg = cfg.get("model") if isinstance(cfg, dict) else None
        if isinstance(model_cfg, dict):
            cfg_base = str(model_cfg.get("base_url") or "").strip()
            cfg_key = str(model_cfg.get("api_key") or "").strip()
    except Exception:
        pass

    # Expand a literal ``${KOPI_API_KEY}`` that slipped through unexpanded.
    if "${" in cfg_key:
        cfg_key = os.path.expandvars(cfg_key)
        if "${" in cfg_key:  # unresolved — treat as absent
            cfg_key = ""

    configured_base = (
        os.getenv("KOPI_PROXY_BASE_URL", "").strip()
        or cfg_base
    ).strip()
    host = _strip_inference_suffix(configured_base) if configured_base else DEFAULT_TOPUP_HOST

    key = (
        cfg_key
        or os.getenv("KOPI_API_KEY", "").strip()
        or os.getenv("KOPI_PROXY_API_KEY", "").strip()
    )
    return (key, f"{host}{TOPUP_CHECKOUT_PATH}")


def gateway_topup_available() -> bool:
    """True when a kopi virtual key is configured (i.e. gateway mode).

    This is the discriminator ``/topup`` uses to choose the gateway checkout
    over the portal overlay. Presence of the KEY — not a reachable network —
    defines the mode, so it is cheap and offline-safe.
    """
    key, _ = resolve_topup_endpoint()
    return bool(key)


def _extract_checkout_url(payload: Any) -> Optional[str]:
    """Pull the Stripe checkout URL out of the response body.

    The gateway is the source of truth for the field name; accept the plausible
    spellings rather than pinning one the server might rename.
    """
    if not isinstance(payload, dict):
        return None
    for field in ("checkout_url", "url", "payment_url", "checkoutUrl"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def create_topup_checkout(amount_usd: Any, *, timeout: float = 15.0) -> str:
    """POST ``/kopi/topup/checkout`` and return the Stripe checkout URL.

    ``amount_usd`` is sent as the server expects it (``{"amount_usd": N}``); the
    server validates min/max. Raises :class:`TopupError` on a missing key,
    transport failure, non-2xx status, or a response without a URL — the caller
    renders ``.message`` and never opens a browser on failure.
    """
    key, url = resolve_topup_endpoint()
    if not key:
        raise TopupError(
            "No kopi API key configured — set model.api_key or KOPI_API_KEY.",
            code="not_configured",
        )

    body = json.dumps({"amount_usd": amount_usd}).encode()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": _user_agent(),
        "Authorization": f"Bearer {key}",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        resp = open_credentialed_url(req, timeout=timeout)
        try:
            raw = resp.read().decode()
        finally:
            try:
                resp.close()
            except Exception:
                pass
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:200]
        except Exception:
            pass
        raise TopupError(
            f"Gateway rejected the top-up (HTTP {exc.code}). {detail}".strip(),
            code=f"http_{exc.code}",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — any transport failure is non-charging
        raise TopupError(f"Could not reach the gateway: {exc}", code="unreachable") from exc

    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise TopupError("Gateway returned a non-JSON response.", code="bad_response") from exc

    checkout_url = _extract_checkout_url(payload)
    if not checkout_url:
        raise TopupError("Gateway response did not include a checkout URL.", code="bad_response")
    return checkout_url
