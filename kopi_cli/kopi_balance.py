"""KOPI Proxy token-quota balance + pricing — the data substrate for
showing "how much quota is left" across the CLI, web dashboard, and desktop.

Unlike Nous (USD micro-credits, see ``kopi_cli/nous_account.py``), the KOPI
Proxy is **token-quota based**: each client key carries a ``quota_limit``
measured in tokens, and requests draw it down until ``quota_remaining`` hits
zero (after which ``/v1/chat/completions`` returns HTTP 402). There is no
USD balance to reconcile — balance is simply "tokens left".

Two live endpoints back this module (both served under the configured base,
whether ``.../v1`` or the V2 ``.../v2`` engine):

- ``GET {base}/balance`` — the authoritative account row::

      {"quota_limit": 5000000, "quota_used": 394884, "quota_remaining": 4605116,
       "total_requests": 36, "is_unlimited": false, "is_active": true,
       "name": "auto-...", "key_prefix": "kopi-..."}

- ``GET {base}/pricing`` — per-model price table (also echoes the account
  quota) — the authoritative $/Mtok source that will feed the model picker::

      {"models": {"kopi-flash": {"input": 0.5, "output": 1.5, "tier": 3,
                                 "context": "128K", "desc": "DeepSeek V4 Pro..."}},
       "currency": "USD", "unit": "per 1M tokens", "account": {...}}

Everything here is **best-effort**: a missing/expired key, an unreachable
proxy, or a malformed body degrades to ``None`` / ``{}`` so callers render
"balance unavailable" instead of crashing. This is the only layer that talks
to the network; CLI/web/desktop consume the parsed dataclasses.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from kopi_cli.urllib_security import open_credentialed_url

# The proxy's own default; also the kopi-proxy provider profile default.
DEFAULT_KOPI_BASE_URL = "https://kopiaiagent.com/v1"

# Balance moves with every request, so keep it fresh; pricing is effectively
# static, so cache it long. force_fresh bypasses both.
_BALANCE_CACHE_TTL = 60  # seconds
_PRICING_CACHE_TTL = 1800  # seconds (30 minutes)

_balance_cache: tuple[Optional["KopiBalance"], float] | None = None  # (result, monotonic ts)
_pricing_cache: tuple[dict[str, "KopiModelPrice"], float] | None = None


# ─── Public types ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class KopiModelPrice:
    """Per-model price row from ``GET {base}/pricing`` (USD per 1M tokens)."""

    model: str
    input_per_mtok: float
    output_per_mtok: float
    tier: Optional[int]
    context: str
    description: str


@dataclass(frozen=True)
class KopiBalance:
    """Parsed token-quota snapshot from ``GET {base}/balance``."""

    quota_limit: int
    quota_used: int
    quota_remaining: int
    percentage_used: float  # 0..100, computed when the endpoint omits it
    total_requests: int
    is_unlimited: bool
    is_active: bool
    client_name: str
    key_prefix: str

    @property
    def is_low(self) -> bool:
        """True when a metered account has < 10% quota left."""
        return not self.is_unlimited and self.percentage_used >= 90.0

    @property
    def is_depleted(self) -> bool:
        """True when a metered account has run out of quota (next call 402s)."""
        return not self.is_unlimited and self.quota_remaining <= 0


# ─── Credential / base-URL resolution ───────────────────────────────────


def _resolve_kopi_credentials() -> tuple[str, str]:
    """Return ``(api_key, base_url)`` for the balance/pricing calls.

    base_url precedence: ``KOPI_PROXY_BASE_URL`` env > config ``model.base_url``
    > production default. api_key precedence: config ``model.api_key`` (which
    ``load_config`` already ``${VAR}``-expands) > ``KOPI_API_KEY`` env >
    ``KOPI_PROXY_API_KEY`` env. Both are best-effort — a blank key still yields
    a usable base_url so the caller can degrade gracefully.
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

    base = (
        os.getenv("KOPI_PROXY_BASE_URL", "").strip().rstrip("/")
        or cfg_base.rstrip("/")
        or DEFAULT_KOPI_BASE_URL
    )
    key = (
        cfg_key
        or os.getenv("KOPI_API_KEY", "").strip()
        or os.getenv("KOPI_PROXY_API_KEY", "").strip()
    )
    return (key, base)


# ─── HTTP ────────────────────────────────────────────────────────────────


def _get_json(url: str, api_key: str, *, timeout: int = 8) -> Optional[dict[str, Any]]:
    """GET ``url`` with a Bearer token, returning the parsed JSON dict or
    ``None`` on any failure (network, non-200, non-JSON, non-object).

    Uses ``open_credentialed_url`` (not bare ``urlopen``) so the request rides
    the certifi-pinned TLS context — python.org/Homebrew builds can't read the
    macOS keychain, so a plain ``urlopen`` here dies with
    CERTIFICATE_VERIFY_FAILED. A kopi User-Agent avoids Cloudflare's Browser
    Integrity Check (error 1010) rejecting the default Python-urllib signature.
    """
    headers = {"Accept": "application/json", "User-Agent": _user_agent()}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = open_credentialed_url(req, timeout=timeout)
        try:
            payload = json.loads(resp.read().decode())
        finally:
            try:
                resp.close()
            except Exception:
                pass
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _user_agent() -> str:
    try:
        from kopi_cli import __version__

        return f"kopi-cli/{__version__}"
    except Exception:
        return "kopi-cli"


# ─── Coercion helpers ──────────────────────────────────────────────────────


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent_used(used: int, limit: int, given: Any = None) -> float:
    """Prefer the server's ``percentage_used``; else compute used/limit."""
    if given is not None:
        pct = _as_float(given, default=-1.0)
        if pct >= 0:
            return round(pct, 1)
    if limit <= 0:
        return 0.0
    return round(used / limit * 100.0, 1)


# ─── Fetchers ──────────────────────────────────────────────────────────────


def _balance_from_payload(data: dict[str, Any]) -> KopiBalance:
    limit = _as_int(data.get("quota_limit"))
    used = _as_int(data.get("quota_used"))
    remaining = _as_int(data.get("quota_remaining"), default=max(limit - used, 0))
    return KopiBalance(
        quota_limit=limit,
        quota_used=used,
        quota_remaining=remaining,
        percentage_used=_percent_used(used, limit, data.get("percentage_used")),
        total_requests=_as_int(data.get("total_requests") or data.get("requests_total")),
        is_unlimited=bool(data.get("is_unlimited")),
        is_active=bool(data.get("is_active", True)),
        client_name=str(data.get("name") or data.get("client_name") or ""),
        key_prefix=str(data.get("key_prefix") or ""),
    )


def fetch_kopi_balance(*, force_fresh: bool = False) -> Optional[KopiBalance]:
    """Return the current token-quota snapshot, or ``None`` if unavailable.

    Cached for ``_BALANCE_CACHE_TTL`` seconds (both hits and ``None`` misses,
    so an unreachable proxy is not re-probed on every keystroke).
    """
    global _balance_cache
    now = time.monotonic()
    if not force_fresh and _balance_cache is not None:
        cached, cached_at = _balance_cache
        if now - cached_at < _BALANCE_CACHE_TTL:
            return cached

    key, base = _resolve_kopi_credentials()
    data = _get_json(f"{base}/balance", key)
    result = _balance_from_payload(data) if data else None
    _balance_cache = (result, now)
    return result


def fetch_kopi_pricing(*, force_fresh: bool = False) -> dict[str, KopiModelPrice]:
    """Return the per-model price table keyed by KOPI model name, or ``{}``.

    Returns ``{}`` on any failure so it slots straight into
    ``get_pricing_for_provider``'s empty-dict contract when it is wired up.
    Cached for ``_PRICING_CACHE_TTL`` seconds.
    """
    global _pricing_cache
    now = time.monotonic()
    if not force_fresh and _pricing_cache is not None:
        cached, cached_at = _pricing_cache
        if now - cached_at < _PRICING_CACHE_TTL:
            return cached

    key, base = _resolve_kopi_credentials()
    data = _get_json(f"{base}/pricing", key)
    models = data.get("models") if isinstance(data, dict) else None
    result: dict[str, KopiModelPrice] = {}
    if isinstance(models, dict):
        for name, row in models.items():
            if not isinstance(row, dict):
                continue
            tier_raw = row.get("tier")
            result[str(name)] = KopiModelPrice(
                model=str(name),
                input_per_mtok=_as_float(row.get("input")),
                output_per_mtok=_as_float(row.get("output")),
                tier=_as_int(tier_raw) if tier_raw is not None else None,
                context=str(row.get("context") or ""),
                description=str(row.get("desc") or row.get("description") or ""),
            )
    _pricing_cache = (result, now)
    return result


# ─── Display helpers (pure — shared by all three surfaces) ─────────────────


def format_token_count(n: int) -> str:
    """Compact human token count: 4605116 -> '4.6M', 5000000 -> '5M'."""
    n = _as_int(n)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(n) >= threshold:
            s = f"{n / threshold:.1f}"
            if s.endswith(".0"):
                s = s[:-2]
            return f"{s}{suffix}"
    return str(n)


def format_quota_summary(balance: KopiBalance) -> str:
    """One-line balance summary shared across surfaces.

    Unlimited: 'Unlimited quota · 36 requests'.
    Metered:   '4.6M / 5M tokens left · 7.9% used · 36 requests'.
    """
    reqs = f"{balance.total_requests} request" + ("" if balance.total_requests == 1 else "s")
    if balance.is_unlimited:
        return f"Unlimited quota · {reqs}"
    return (
        f"{format_token_count(balance.quota_remaining)} / "
        f"{format_token_count(balance.quota_limit)} tokens left · "
        f"{balance.percentage_used}% used · {reqs}"
    )


def reset_caches() -> None:
    """Drop the in-process balance/pricing caches (tests, key rotation)."""
    global _balance_cache, _pricing_cache
    _balance_cache = None
    _pricing_cache = None
