"""The Instagram skill's whole value is the container protocol done right:
create → poll until FINISHED → publish, with the prepared-but-unpublished
mode for a human final step, and the access token never surfacing in
output. All Graph traffic is faked at the urllib layer — no network."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "social-media"
    / "instagram"
    / "scripts"
    / "instagram_publish.py"
)

TOKEN = "TEST-TOKEN-abc123"
USER = "17840000"


def load_module():
    spec = importlib.util.spec_from_file_location("instagram_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Resp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGraph:
    """Routes urllib requests to canned Graph API responses."""

    def __init__(self, statuses=("FINISHED",)):
        self.calls = []  # (method, path, params)
        self._statuses = list(statuses)
        self._containers = 0

    def __call__(self, request, timeout=0, context=None):
        from urllib.parse import parse_qs, urlparse

        url = urlparse(request.full_url)
        body = (request.data or b"").decode()
        params = {k: v[0] for k, v in parse_qs(url.query + "&" + body).items()}
        path = url.path.split("/", 2)[2]  # strip /vXX.X/
        method = request.get_method()
        self.calls.append((method, path, params))

        if method == "POST" and path == f"{USER}/media":
            self._containers += 1
            return _Resp({"id": f"C{self._containers}"})
        if method == "POST" and path == f"{USER}/media_publish":
            return _Resp({"id": "M1"})
        if method == "GET" and params.get("fields") == "status_code,status":
            code = self._statuses.pop(0) if self._statuses else "FINISHED"
            return _Resp({"status_code": code, "status": f"Status: {code}"})
        if method == "GET" and path == "M1":
            return _Resp({"permalink": "https://www.instagram.com/p/xyz/", "media_type": "IMAGE"})
        if method == "GET" and path == USER:
            return _Resp({"username": "kopi_demo"})
        return _Resp({})


@pytest.fixture
def graph(monkeypatch):
    fake = FakeGraph()
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("INSTAGRAM_USER_ID", USER)
    mod = load_module()
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return mod, fake


def test_publish_image_full_flow(graph, capsys):
    mod, fake = graph
    mod.main(["publish-image", "https://x.test/a.jpg", "--caption", "hello"])
    out = json.loads(capsys.readouterr().out)
    assert out["media_id"] == "M1"
    assert out["permalink"].startswith("https://www.instagram.com/")
    methods_paths = [(m, p) for m, p, _ in fake.calls]
    assert ("POST", f"{USER}/media") in methods_paths
    assert ("POST", f"{USER}/media_publish") in methods_paths
    create = next(p for m, pa, p in fake.calls if pa == f"{USER}/media")
    assert create["image_url"] == "https://x.test/a.jpg"
    assert create["caption"] == "hello"


def test_reel_uses_reels_media_type(graph):
    mod, fake = graph
    mod.main(["publish-reel", "https://x.test/v.mp4", "--caption", "c"])
    create = next(p for m, pa, p in fake.calls if pa == f"{USER}/media")
    assert create["media_type"] == "REELS"
    assert create["video_url"] == "https://x.test/v.mp4"


def test_no_publish_stops_at_container(graph, capsys):
    mod, fake = graph
    mod.main(["publish-image", "https://x.test/a.jpg", "--no-publish"])
    out = json.loads(capsys.readouterr().out)
    assert out["container_id"] == "C1"
    assert "publish-container C1" in out["next_step"]
    assert all(path != f"{USER}/media_publish" for _, path, _ in fake.calls)


def test_polls_until_finished(graph):
    mod, fake = graph
    fake._statuses = ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]
    mod.main(["publish-reel", "https://x.test/v.mp4"])
    status_polls = [p for m, pa, p in fake.calls if p.get("fields") == "status_code,status"]
    assert len(status_polls) == 3


def test_container_error_exits_nonzero(graph, capsys):
    mod, fake = graph
    fake._statuses = ["ERROR"]
    with pytest.raises(SystemExit) as exc:
        mod.main(["publish-image", "https://x.test/a.jpg"])
    assert exc.value.code == 1
    assert "failed" in capsys.readouterr().err


def test_carousel_builds_children_then_parent(graph):
    mod, fake = graph
    mod.main(["publish-carousel", "https://x.test/1.jpg", "https://x.test/2.jpg"])
    creates = [p for m, pa, p in fake.calls if pa == f"{USER}/media"]
    assert [c.get("is_carousel_item") for c in creates[:2]] == ["true", "true"]
    assert creates[2]["media_type"] == "CAROUSEL"
    assert creates[2]["children"] == "C1,C2"


def test_carousel_rejects_single_image(graph, capsys):
    mod, _ = graph
    with pytest.raises(SystemExit) as exc:
        mod.main(["publish-carousel", "https://x.test/1.jpg"])
    assert exc.value.code == 2


def test_token_never_appears_in_output(graph, capsys):
    mod, fake = graph
    mod.main(["publish-image", "https://x.test/a.jpg"])
    captured = capsys.readouterr()
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err
    # ...but it IS sent to the API.
    create = next(p for m, pa, p in fake.calls if pa == f"{USER}/media")
    assert create["access_token"] == TOKEN


def test_missing_env_is_actionable(monkeypatch, capsys):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("INSTAGRAM_USER_ID", USER)
    mod = load_module()
    with pytest.raises(SystemExit) as exc:
        mod.main(["whoami"])
    assert exc.value.code == 2
    assert "INSTAGRAM_ACCESS_TOKEN" in capsys.readouterr().err
