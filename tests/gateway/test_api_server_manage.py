"""HTTP-level tests for the /v1/manage/* instance-management endpoints.

Builds an aiohttp app from the adapter's real ``_http_route_table()`` so route
registration, bearer auth and handler behavior are all exercised end to end.
"""

import time
from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import gateway.pairing as pairing_mod
from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter

KEY = "sk-manage-test"


def _make_adapter() -> APIServerAdapter:
    return APIServerAdapter(PlatformConfig(enabled=True, extra={"key": KEY}))


def _app_from_route_table(adapter: APIServerAdapter) -> web.Application:
    app = web.Application()
    for method, path, handler in adapter._http_route_table():
        app.router.add_route(method, path, handler)
    return app


@pytest.fixture
def manage_env(tmp_path, monkeypatch):
    """Isolate pairing + config storage under a temp KOPI_HOME."""
    monkeypatch.setenv("KOPI_HOME", str(tmp_path))
    pairing_dir = tmp_path / "pairing"
    pairing_dir.mkdir(parents=True, exist_ok=True)
    pairing_mod._STORES.clear()
    with patch("gateway.pairing.PAIRING_DIR", pairing_dir):
        yield tmp_path
    pairing_mod._STORES.clear()


def _seed_pending(platform, user_id, user_name="u"):
    store = pairing_mod.get_pairing_store()
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


def _auth(key=KEY):
    return {"Authorization": f"Bearer {key}"}


class TestPairingEndpoints:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/v1/manage/pairing", headers=_auth("wrong"))
            assert resp.status == 401

    @pytest.mark.asyncio
    async def test_list_empty(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/v1/manage/pairing", headers=_auth())
            assert resp.status == 200
            data = await resp.json()
        assert data["object"] == "kopi.pairing.list"
        assert data["pending"] == []
        assert data["approved"] == []

    @pytest.mark.asyncio
    async def test_approve_notfound_is_200(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/pairing/approve",
                headers=_auth(),
                json={"platform": "telegram", "user_id": "999"},
            )
            assert resp.status == 200
            data = await resp.json()
        assert data == {"object": "kopi.pairing.approve", "result": "notfound"}

    @pytest.mark.asyncio
    async def test_approve_then_list_shows_approved(self, manage_env):
        _seed_pending("telegram", "111", "Kun")
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/pairing/approve",
                headers=_auth(),
                json={"platform": "telegram", "user_id": "111"},
            )
            assert (await resp.json())["result"] == "ok"

            resp = await cli.get("/v1/manage/pairing?platform=telegram", headers=_auth())
            data = await resp.json()
        assert data["pending"] == []
        assert [r["user_id"] for r in data["approved"]] == ["111"]
        row = data["approved"][0]
        # last_active / chat_type present (null when no gateway session yet).
        assert "last_active" in row and "chat_type" in row

    @pytest.mark.asyncio
    async def test_approve_bad_platform_400(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/pairing/approve",
                headers=_auth(),
                json={"platform": "not-a-real-platform", "user_id": "1"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_approve_empty_user_id_400(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/pairing/approve",
                headers=_auth(),
                json={"platform": "telegram", "user_id": ""},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_revoke_ok_and_notfound(self, manage_env):
        _seed_pending("telegram", "222")
        pairing_mod.get_pairing_store().approve_user("telegram", "222")
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/pairing/revoke",
                headers=_auth(),
                json={"platform": "telegram", "user_id": "222"},
            )
            assert (await resp.json())["result"] == "ok"

            resp = await cli.post(
                "/v1/manage/pairing/revoke",
                headers=_auth(),
                json={"platform": "telegram", "user_id": "222"},
            )
            assert (await resp.json())["result"] == "notfound"


class TestSkillsEndpoints:
    @pytest.mark.asyncio
    async def test_get_shape(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/v1/manage/skills", headers=_auth())
            assert resp.status == 200
            data = await resp.json()
        assert data["object"] == "kopi.skills.config"
        assert isinstance(data["available"], list)
        assert isinstance(data["disabled"], list)
        assert isinstance(data["platform_disabled"], dict)

    @pytest.mark.asyncio
    async def test_post_uses_merge_existing_and_reports_no_restart(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        captured = {}

        from kopi_cli import config as cfg_mod

        def _spy_save(cfg, *args, **kwargs):
            captured["merge_existing"] = kwargs.get("merge_existing")
            captured["skills"] = dict(cfg.get("skills", {}))
            return None

        async with TestClient(TestServer(app)) as cli:
            with patch.object(cfg_mod, "save_config", _spy_save):
                resp = await cli.post(
                    "/v1/manage/skills",
                    headers=_auth(),
                    json={"disabled": ["blockchain"], "platform_disabled": {"telegram": ["gaming"]}},
                )
                assert resp.status == 200
                data = await resp.json()

        assert data == {"object": "kopi.skills.config", "result": "ok", "restart_required": False}
        assert captured["merge_existing"] is True
        assert captured["skills"]["disabled"] == ["blockchain"]
        assert captured["skills"]["platform_disabled"] == {"telegram": ["gaming"]}

    @pytest.mark.asyncio
    async def test_post_rejects_bad_shape_400(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/v1/manage/skills", headers=_auth(), json={"disabled": "notalist"}
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_post_empty_body_400(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post("/v1/manage/skills", headers=_auth(), json={})
            assert resp.status == 400


class TestCapabilities:
    @pytest.mark.asyncio
    async def test_advertises_manage_api(self, manage_env):
        app = _app_from_route_table(_make_adapter())
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/v1/capabilities", headers=_auth())
            data = await resp.json()
        assert data["features"]["manage_api"] is True
        assert "manage_pairing" in data["endpoints"]
        assert "manage_skills_set" in data["endpoints"]
