"""Platform SSO token verification (website → dashboard handoff).

Protocol must stay in lockstep with saas-starter-kit/lib/instance-sso.ts:
    v1:{customerId}:{exp}:{nonce}:{sig}
    sig = hex(HMAC_SHA256(secret, payload-without-sig))
"""

import hashlib
import hmac

import pytest

from kopi_cli.dashboard_auth.platform_sso import (
    reset_replay_cache,
    verify_platform_sso_token,
)

SECRET = "shared-dashboard-session-secret"
NOW = 1_800_000_000


def _mint(customer_id: str, exp: int, nonce: str = "abcd1234", secret: str = SECRET) -> str:
    payload = f"v1:{customer_id}:{exp}:{nonce}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


@pytest.fixture(autouse=True)
def _fresh_cache():
    reset_replay_cache()
    yield
    reset_replay_cache()


def test_valid_token_accepted():
    token = _mint("team-1", NOW + 60)
    ok, reason, cid = verify_platform_sso_token(token, SECRET, now=NOW)
    assert (ok, reason, cid) == (True, None, "team-1")


def test_expired_token_rejected():
    token = _mint("team-1", NOW - 1)
    ok, reason, _ = verify_platform_sso_token(token, SECRET, now=NOW)
    assert (ok, reason) == (False, "expired")


def test_tampered_payload_rejected():
    token = _mint("team-1", NOW + 60).replace(":team-1:", ":team-2:")
    ok, reason, _ = verify_platform_sso_token(token, SECRET, now=NOW)
    assert (ok, reason) == (False, "bad-signature")


def test_wrong_secret_rejected():
    token = _mint("team-1", NOW + 60, secret="other")
    ok, reason, _ = verify_platform_sso_token(token, SECRET, now=NOW)
    assert (ok, reason) == (False, "bad-signature")


def test_malformed_token_rejected():
    for bad in ("", "garbage", "v2:a:1:b:c", "v1:a:not-int:b:c"):
        ok, reason, _ = verify_platform_sso_token(bad, SECRET, now=NOW)
        assert (ok, reason) == (False, "malformed"), bad


def test_instance_binding_enforced():
    token = _mint("team-1", NOW + 60)
    ok, reason, _ = verify_platform_sso_token(
        token, SECRET, instance="team-2", now=NOW
    )
    assert (ok, reason) == (False, "wrong-instance")


def test_replay_rejected_within_window():
    token = _mint("team-1", NOW + 60)
    ok1, _, _ = verify_platform_sso_token(token, SECRET, now=NOW)
    ok2, reason, _ = verify_platform_sso_token(token, SECRET, now=NOW)
    assert ok1 is True
    assert (ok2, reason) == (False, "replayed")


def test_replay_cache_prunes_expired_nonces():
    token = _mint("team-1", NOW + 60, nonce="prune-me")
    assert verify_platform_sso_token(token, SECRET, now=NOW)[0]
    # After expiry the nonce is pruned; a *new* (still-valid) token with the
    # same nonce would verify — the exp check is what protects that window.
    later = NOW + 120
    token2 = _mint("team-1", later + 60, nonce="prune-me")
    assert verify_platform_sso_token(token2, SECRET, now=later)[0]
