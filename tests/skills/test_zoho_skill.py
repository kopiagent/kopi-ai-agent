"""The Zoho skill's failure modes are all plumbing: wrong data-center hosts,
missing organization_id on Books calls, CRM's required fields param, token
re-mint storms, and secrets leaking to stdout. These tests pin each one
against a faked urllib — no network, no real Zoho app."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "finance"
    / "zoho"
    / "scripts"
    / "zoho_client.py"
)

SECRET = "zoho-secret-xyz"
REFRESH = "1000.refresh.token"


def load_module():
    spec = importlib.util.spec_from_file_location("zoho_skill", SCRIPT_PATH)
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


class FakeZoho:
    def __init__(self):
        self.calls = []  # (method, host, path, params)

    def __call__(self, request, timeout=0):
        url = urlparse(request.full_url)
        body = (request.data or b"").decode()
        params = {k: v[0] for k, v in parse_qs(url.query + "&" + body).items()}
        self.calls.append((request.get_method(), url.netloc, url.path, params, body))

        if url.path == "/oauth/v2/token":
            if params.get("grant_type") == "authorization_code":
                return _Resp({"refresh_token": REFRESH, "access_token": "at", "expires_in": 3600})
            return _Resp({"access_token": "at-123", "expires_in": 3600})
        if url.path == "/books/v3/organizations":
            return _Resp({"organizations": [
                {"organization_id": "890", "name": "Kopi Pte Ltd", "currency_code": "SGD", "is_default_org": True}
            ]})
        return _Resp({"path": url.path, "params": params})


@pytest.fixture
def zoho(monkeypatch, tmp_path):
    fake = FakeZoho()
    monkeypatch.setenv("ZOHO_CLIENT_ID", "1000.abc")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", SECRET)
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", REFRESH)
    monkeypatch.setenv("ZOHO_BOOKS_ORG_ID", "890")
    monkeypatch.delenv("ZOHO_DC", raising=False)
    mod = load_module()
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(mod, "_TOKEN_CACHE", str(tmp_path / "cache" / "tok.json"))
    monkeypatch.setattr(mod, "_ENV_FILE", str(tmp_path / "dotenv"))
    return mod, fake


def test_dc_selects_accounts_and_api_hosts(zoho, monkeypatch):
    mod, fake = zoho
    monkeypatch.setenv("ZOHO_DC", "eu")
    mod.main(["crm", "Leads"])
    hosts = [h for _, h, _, _, _ in fake.calls]
    assert "accounts.zoho.eu" in hosts        # token refresh
    assert "www.zohoapis.eu" in hosts         # API call


def test_books_injects_organization_id(zoho, capsys):
    mod, fake = zoho
    mod.main(["books", "invoices", "--param", "status=unpaid"])
    method, host, path, params, _ = fake.calls[-1]
    assert path == "/books/v3/invoices"
    assert params["organization_id"] == "890"
    assert params["status"] == "unpaid"


def test_crm_gets_default_fields(zoho):
    mod, fake = zoho
    mod.main(["crm", "Deals"])
    _, _, path, params, _ = fake.calls[-1]
    assert path == "/crm/v8/Deals"
    assert "Deal_Name" in params["fields"]


def test_crm_query_posts_coql(zoho):
    mod, fake = zoho
    mod.main(["crm-query", "select Deal_Name from Deals limit 5"])
    method, _, path, _, body = fake.calls[-1]
    assert (method, path) == ("POST", "/crm/v8/coql")
    assert json.loads(body)["select_query"].startswith("select Deal_Name")


def test_access_token_is_cached_across_calls(zoho):
    mod, fake = zoho
    mod.main(["crm", "Leads"])
    mod.main(["crm", "Contacts"])
    token_mints = [c for c in fake.calls if c[2] == "/oauth/v2/token"]
    assert len(token_mints) == 1


def test_exchange_writes_refresh_token_to_env_not_stdout(zoho, capsys):
    mod, fake = zoho
    mod.main(["exchange", "authcode-1"])
    captured = capsys.readouterr()
    assert REFRESH not in captured.out
    assert REFRESH not in captured.err
    env_text = Path(mod._ENV_FILE).read_text(encoding="utf-8")
    assert f"ZOHO_REFRESH_TOKEN={REFRESH}" in env_text


def test_secrets_never_in_query_output(zoho, capsys):
    mod, fake = zoho
    mod.main(["books", "invoices"])
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert REFRESH not in captured.out


def test_auth_url_uses_dc_and_readonly_scopes(zoho, capsys, monkeypatch):
    mod, _ = zoho
    monkeypatch.setenv("ZOHO_DC", "in")
    mod.main(["auth-url"])
    url = capsys.readouterr().out.strip()
    assert url.startswith("https://accounts.zoho.in/oauth/v2/auth?")
    assert "ZohoBooks.invoices.READ" in url
    assert "ZohoCRM.modules.READ" in url
    assert ".CREATE" not in url and ".ALL" not in url


def test_missing_env_is_actionable(zoho, monkeypatch, capsys):
    mod, _ = zoho
    monkeypatch.delenv("ZOHO_BOOKS_ORG_ID", raising=False)
    with pytest.raises(SystemExit) as exc:
        mod.main(["books", "invoices"])
    assert exc.value.code == 2
    assert "ZOHO_BOOKS_ORG_ID" in capsys.readouterr().err


def test_unknown_dc_rejected(zoho, monkeypatch, capsys):
    mod, _ = zoho
    monkeypatch.setenv("ZOHO_DC", "mars")
    with pytest.raises(SystemExit) as exc:
        mod.main(["crm", "Leads"])
    assert exc.value.code == 2
    assert "mars" in capsys.readouterr().err
