"""Tests for the instance-management additions to gateway/pairing.py.

Covers:
  - PairingStore.approve_user() (operator/console approval by user_id)
  - get_pairing_store() process-wide singleton
  - the concurrency regression the singleton exists to prevent: two
    read-modify-write cycles on the same pending.json must not lose either.
"""

import threading
import time
from unittest.mock import patch

import pytest

import gateway.pairing as pairing_mod
from gateway.pairing import PairingStore, get_pairing_store


def _make_store(tmp_path):
    with patch("gateway.pairing.PAIRING_DIR", tmp_path):
        return PairingStore()


def _seed_pending(store, platform, user_id, user_name="u"):
    """Write a well-formed pending entry directly (bypasses rate limits)."""
    path = store._pending_path(platform)
    pending = store._load_json(path)
    pending[f"entry-{user_id}"] = {
        "hash": "deadbeef" * 8,
        "salt": "00" * 16,
        "user_id": user_id,
        "user_name": user_name,
        "created_at": time.time(),
    }
    store._save_json(path, pending)


class TestApproveUser:
    def test_hit_moves_pending_to_approved(self, tmp_path):
        store = _make_store(tmp_path)
        _seed_pending(store, "telegram", "111", "Kun")

        with patch("gateway.pairing._sync_allowlist_add") as sync_add:
            result = store.approve_user("telegram", "111")

        assert result == "ok"
        assert store.is_approved("telegram", "111") is True
        # pending entry consumed
        assert store._load_json(store._pending_path("telegram")) == {}
        sync_add.assert_called_once()

    def test_already_when_approved_and_not_pending(self, tmp_path):
        store = _make_store(tmp_path)
        _seed_pending(store, "telegram", "222")
        assert store.approve_user("telegram", "222") == "ok"

        approved_before = store.list_approved("telegram")
        # Second call: no pending entry, but already approved -> idempotent.
        assert store.approve_user("telegram", "222") == "already"
        assert store.list_approved("telegram") == approved_before

    def test_notfound_when_absent(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.approve_user("telegram", "999") == "notfound"
        assert store.list_approved("telegram") == []
        assert store._load_json(store._pending_path("telegram")) == {}

    def test_does_not_trigger_lockout(self, tmp_path):
        store = _make_store(tmp_path)
        # Many misses in a row must NOT lock the platform (unlike approve_code,
        # which records failed attempts to defend against code brute-forcing).
        for _ in range(pairing_mod.MAX_FAILED_ATTEMPTS + 3):
            assert store.approve_user("telegram", "no-such-user") == "notfound"
        assert store._is_locked_out("telegram") is False


class TestSingleton:
    def setup_method(self):
        pairing_mod._STORES.clear()

    def teardown_method(self):
        pairing_mod._STORES.clear()

    def test_same_profile_returns_same_object(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KOPI_HOME", str(tmp_path))
        with patch("gateway.pairing.PAIRING_DIR", tmp_path):
            a = get_pairing_store()
            b = get_pairing_store()
        assert a is b

    def test_distinct_profiles_distinct_objects(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KOPI_HOME", str(tmp_path))
        with patch("gateway.pairing.PAIRING_DIR", tmp_path):
            default = get_pairing_store()
            p1 = get_pairing_store("p1")
            p1_again = get_pairing_store("p1")
            p2 = get_pairing_store("p2")
        assert p1 is p1_again
        assert default is not p1
        assert p1 is not p2


class TestConcurrencyRegression:
    """The lost-update race the singleton lock exists to prevent.

    _secure_write is atomic (tmp + fsync + rename) so the file never corrupts,
    but "read whole file -> mutate -> write whole file" from two callers that
    do NOT share a lock silently loses one side's mutation. Going through
    get_pairing_store() gives both callers one RLock, so every mutation lands.
    """

    def setup_method(self):
        pairing_mod._STORES.clear()

    def teardown_method(self):
        pairing_mod._STORES.clear()

    def test_approve_while_new_pending_arrives_does_not_lose_either(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KOPI_HOME", str(tmp_path))
        N = 25
        approve_ids = [f"A{i}" for i in range(N)]
        gen_ids = [f"B{i}" for i in range(N)]

        with patch("gateway.pairing.PAIRING_DIR", tmp_path), \
             patch("gateway.pairing.RATE_LIMIT_SECONDS", 0), \
             patch("gateway.pairing.MAX_PENDING_PER_PLATFORM", 10_000):
            store = get_pairing_store()
            for uid in approve_ids:
                _seed_pending(store, "telegram", uid)

            start = threading.Barrier(2 * N)
            errors = []

            def _approve(uid):
                try:
                    start.wait()
                    assert store.approve_user("telegram", uid) == "ok"
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

            def _generate(uid):
                try:
                    start.wait()
                    assert store.generate_code("telegram", uid, uid) is not None
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

            threads = [threading.Thread(target=_approve, args=(u,)) for u in approve_ids]
            threads += [threading.Thread(target=_generate, args=(u,)) for u in gen_ids]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, errors
        # Every approved A landed and left pending.
        approved = {r["user_id"] for r in store.list_approved("telegram")}
        for uid in approve_ids:
            assert uid in approved, f"lost approval for {uid}"
        # Every generated B is still pending — none clobbered by a racing approve.
        pending_ids = {r["user_id"] for r in store.list_pending("telegram")}
        for uid in gen_ids:
            assert uid in pending_ids, f"lost pending for {uid}"
        # No approved A left lingering in pending.
        for uid in approve_ids:
            assert uid not in pending_ids, f"approved user {uid} still pending"
