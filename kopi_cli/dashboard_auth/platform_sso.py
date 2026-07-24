"""Platform SSO: verify handoff tokens minted by the KOPI website.

The website console's "Open Agent console" button signs a short-lived
HMAC token with the shared ``KOPI_DASHBOARD_BASIC_AUTH_SECRET`` (injected
into every instance via k8s Secret) and redirects the browser to
``{instance}/sso?token=...``. This module verifies that token; the
``/sso`` route then mints a normal dashboard session so the customer
lands signed-in — no second login.

Token format (must stay in lockstep with the website's
``saas-starter-kit/lib/instance-sso.ts``)::

    v1:{customerId}:{exp}:{nonce}:{sig}
    sig = hex(HMAC_SHA256(secret, "v1:{customerId}:{exp}:{nonce}"))

* ``exp``   — unix seconds; the website signs 60s ahead.
* ``nonce`` — random hex; replayed nonces are rejected until their token
  expires (in-memory per-process cache — one dashboard process per
  container, so that is airtight enough for a 60s window).
* ``customerId`` must equal this container's ``INSTANCE`` env when set,
  so a token minted for one customer can never open another's dashboard.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Literal, Optional, Tuple

VerifyFailure = Literal[
    "malformed", "expired", "bad-signature", "wrong-instance", "replayed"
]

# nonce -> exp; pruned on every call. Process-local (one dashboard per
# container) which matches the 60s replay window this protects.
_seen_nonces: dict[str, int] = {}


def _prune(now: int) -> None:
    expired = [n for n, exp in _seen_nonces.items() if exp < now]
    for n in expired:
        _seen_nonces.pop(n, None)


def verify_platform_sso_token(
    token: str,
    secret: str,
    *,
    instance: Optional[str] = None,
    now: Optional[int] = None,
) -> Tuple[bool, Optional[VerifyFailure], str]:
    """Return ``(ok, failure_reason, customer_id)``.

    Marks the nonce as used on success — call once per request.
    """
    ts = int(now if now is not None else time.time())
    parts = token.split(":")
    if len(parts) != 5 or parts[0] != "v1":
        return False, "malformed", ""
    _, customer_id, exp_str, nonce, sig = parts
    if not customer_id or not exp_str.isdigit() or not nonce or not sig:
        return False, "malformed", ""
    expected = hmac.new(
        secret.encode("utf-8"),
        f"v1:{customer_id}:{exp_str}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False, "bad-signature", ""
    exp = int(exp_str)
    if ts > exp:
        return False, "expired", ""
    if instance and customer_id != instance:
        return False, "wrong-instance", ""
    _prune(ts)
    if nonce in _seen_nonces:
        return False, "replayed", ""
    _seen_nonces[nonce] = exp
    return True, None, customer_id


def reset_replay_cache() -> None:
    """Test hook."""
    _seen_nonces.clear()
