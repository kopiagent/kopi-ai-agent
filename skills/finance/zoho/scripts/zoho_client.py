#!/usr/bin/env python3
"""Zoho Books + CRM via Zoho's official REST APIs (OAuth2, stdlib only).

One Zoho app grants both surfaces: a single refresh token minted with
Books + CRM scopes drives `books` and `crm` subcommands alike. No
third-party MCP is involved (none is official; see the capability plan
§3.4) — this script talks to zohoapis.* directly.

Zoho is DATA-CENTER PARTITIONED: an account lives in exactly one DC and
both the accounts server and the API host differ per DC (accounts.zoho.eu
/ www.zohoapis.eu, …). A mismatched DC yields `invalid_client` even with
correct credentials — set ZOHO_DC to where the account was signed up.

Usage:
    python3 zoho_client.py auth-url [--redirect URI] [--scopes S1,S2]
    python3 zoho_client.py exchange <code> [--redirect URI]
    python3 zoho_client.py orgs                       # Books organizations
    python3 zoho_client.py books <resource> [--param k=v ...]
    python3 zoho_client.py crm <Module> [--fields a,b] [--param k=v ...]
    python3 zoho_client.py crm-query "<COQL select …>"
    python3 zoho_client.py get <path> [--param k=v ...]   # raw escape hatch

Environment (from ~/.kopi/.env):
    ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET   server-based app, api-console.zoho.com
    ZOHO_REFRESH_TOKEN                    minted once via auth-url + exchange
    ZOHO_DC                               com | eu | in | com.au | jp | com.cn | sa | ca
    ZOHO_BOOKS_ORG_ID                     Books organization id (from `orgs`)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_DCS = ("com", "eu", "in", "com.au", "jp", "com.cn", "sa", "ca")

# Read-only by default — same stance as the xero/quickbooks skills: listing
# and reports are what a chat assistant needs; writes touch a real ledger /
# real pipeline and must be an explicit human decision (pass --scopes).
_DEFAULT_SCOPES = ",".join(
    [
        "ZohoBooks.settings.READ",
        "ZohoBooks.contacts.READ",
        "ZohoBooks.invoices.READ",
        "ZohoBooks.bills.READ",
        "ZohoBooks.expenses.READ",
        "ZohoBooks.banking.READ",
        "ZohoCRM.modules.READ",
        "ZohoCRM.settings.READ",
        "ZohoCRM.org.READ",
        "ZohoCRM.coql.READ",
    ]
)

_TOKEN_CACHE = os.path.expanduser("~/.kopi/cache/zoho_access_token.json")
_ENV_FILE = os.path.expanduser("~/.kopi/.env")


def _dc() -> str:
    dc = os.environ.get("ZOHO_DC", "").strip() or "com"
    if dc not in _DCS:
        print(f"unknown ZOHO_DC {dc!r}; expected one of {_DCS}", file=sys.stderr)
        sys.exit(2)
    return dc


def _accounts_base() -> str:
    return f"https://accounts.zoho.{_dc()}"


def _api_base() -> str:
    return f"https://www.zohoapis.{_dc()}"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"missing {name} — set it in ~/.kopi/.env (see the skill's Setup section).",
            file=sys.stderr,
        )
        sys.exit(2)
    return value


def _ssl_context():
    """Default SSL context, falling back to certifi's CA bundle.

    uv-managed/standalone Pythons often ship with NO system CA store, so
    ``create_default_context()`` alone fails every HTTPS call with
    CERTIFICATE_VERIFY_FAILED. certifi is a core dependency of the agent;
    plain ``python3`` without it keeps the system default behavior.
    """
    import ssl

    context = ssl.create_default_context()
    if context.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi

            context.load_verify_locations(cafile=certifi.where())
        except ImportError:
            pass
    return context


def _http(method: str, url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            message = json.loads(body).get("message", body)
        except (json.JSONDecodeError, AttributeError):
            message = body
        print(f"Zoho API {exc.code}: {message[:400]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        print(f"non-JSON response: {body[:200]}", file=sys.stderr)
        sys.exit(1)


def _access_token() -> str:
    """Refresh-grant an access token, cached on disk until near expiry
    (Zoho rate-limits token minting per 10-minute window)."""
    try:
        cached = json.load(open(_TOKEN_CACHE, encoding="utf-8"))
        if cached.get("dc") == _dc() and cached.get("expires_at", 0) > time.time() + 60:
            return cached["access_token"]
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": _env("ZOHO_REFRESH_TOKEN"),
            "client_id": _env("ZOHO_CLIENT_ID"),
            "client_secret": _env("ZOHO_CLIENT_SECRET"),
        }
    ).encode()
    tok = _http("POST", f"{_accounts_base()}/oauth/v2/token", data=data)
    if "access_token" not in tok:
        print(f"token refresh failed: {json.dumps(tok)[:300]}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(_TOKEN_CACHE), exist_ok=True)
    fd = os.open(_TOKEN_CACHE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(
            {
                "access_token": tok["access_token"],
                "expires_at": time.time() + int(tok.get("expires_in", 3600)),
                "dc": _dc(),
            },
            f,
        )
    return tok["access_token"]


def _api(method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
    url = f"{_api_base()}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Zoho-oauthtoken {_access_token()}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    return _http(method, url, data=data, headers=headers)


def _out(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _kv_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep:
            print(f"--param expects k=v, got {pair!r}", file=sys.stderr)
            sys.exit(2)
        params[key] = value
    return params


# ─── Commands ────────────────────────────────────────────────────────────────


def cmd_auth_url(args: argparse.Namespace) -> None:
    query = urllib.parse.urlencode(
        {
            "scope": args.scopes,
            "client_id": _env("ZOHO_CLIENT_ID"),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "redirect_uri": args.redirect,
        }
    )
    print(f"{_accounts_base()}/oauth/v2/auth?{query}")


def cmd_exchange(args: argparse.Namespace) -> None:
    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": args.code,
            "client_id": _env("ZOHO_CLIENT_ID"),
            "client_secret": _env("ZOHO_CLIENT_SECRET"),
            "redirect_uri": args.redirect,
        }
    ).encode()
    tok = _http("POST", f"{_accounts_base()}/oauth/v2/token", data=data)
    refresh = tok.get("refresh_token")
    if not refresh:
        # Zoho returns 200 with an error field for bad codes/DC mismatches.
        print(f"exchange failed: {json.dumps(tok)[:300]}", file=sys.stderr)
        sys.exit(1)
    # The refresh token is a long-lived secret: write it straight to .env,
    # never to stdout.
    with open(_ENV_FILE, "a", encoding="utf-8") as f:
        f.write(f"ZOHO_REFRESH_TOKEN={refresh}\n")
    print(json.dumps({"status": "ok", "written": "ZOHO_REFRESH_TOKEN -> ~/.kopi/.env"}))


def cmd_orgs(_args: argparse.Namespace) -> None:
    result = _api("GET", "/books/v3/organizations")
    orgs = [
        {k: o.get(k) for k in ("organization_id", "name", "currency_code", "is_default_org")}
        for o in result.get("organizations", [])
    ]
    _out({"organizations": orgs, "hint": "set ZOHO_BOOKS_ORG_ID in ~/.kopi/.env"})


def cmd_books(args: argparse.Namespace) -> None:
    params = _kv_params(args.param)
    params["organization_id"] = _env("ZOHO_BOOKS_ORG_ID")
    _out(_api("GET", f"/books/v3/{args.resource.strip('/')}", params=params))


def cmd_crm(args: argparse.Namespace) -> None:
    params = _kv_params(args.param)
    if args.fields:
        params["fields"] = args.fields
    elif "fields" not in params:
        # CRM v8 record listing REQUIRES a fields param; give a usable default.
        defaults = {
            "Leads": "Last_Name,First_Name,Company,Email,Lead_Status",
            "Contacts": "Last_Name,First_Name,Email,Account_Name",
            "Accounts": "Account_Name,Industry,Annual_Revenue",
            "Deals": "Deal_Name,Stage,Amount,Closing_Date,Account_Name",
        }
        params["fields"] = defaults.get(args.module, "id,Created_Time")
    _out(_api("GET", f"/crm/v8/{args.module.strip('/')}", params=params))


def cmd_crm_query(args: argparse.Namespace) -> None:
    _out(_api("POST", "/crm/v8/coql", body={"select_query": args.query}))


def cmd_get(args: argparse.Namespace) -> None:
    params = _kv_params(args.param)
    path = "/" + args.path.lstrip("/")
    if path.startswith("/books/") and "organization_id" not in params:
        params["organization_id"] = _env("ZOHO_BOOKS_ORG_ID")
    _out(_api("GET", path, params=params or None))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth-url")
    p.add_argument("--redirect", default="http://localhost:8123/callback")
    p.add_argument("--scopes", default=_DEFAULT_SCOPES)
    p.set_defaults(fn=cmd_auth_url)

    p = sub.add_parser("exchange")
    p.add_argument("code")
    p.add_argument("--redirect", default="http://localhost:8123/callback")
    p.set_defaults(fn=cmd_exchange)

    sub.add_parser("orgs").set_defaults(fn=cmd_orgs)

    p = sub.add_parser("books")
    p.add_argument("resource", help="invoices | contacts | bills | expenses | banktransactions | …")
    p.add_argument("--param", action="append", default=[])
    p.set_defaults(fn=cmd_books)

    p = sub.add_parser("crm")
    p.add_argument("module", help="Leads | Contacts | Accounts | Deals | …")
    p.add_argument("--fields", default=None)
    p.add_argument("--param", action="append", default=[])
    p.set_defaults(fn=cmd_crm)

    p = sub.add_parser("crm-query")
    p.add_argument("query", help="COQL — a where clause is MANDATORY, e.g. select Deal_Name from Deals where Stage = 'Qualification' limit 20")
    p.set_defaults(fn=cmd_crm_query)

    p = sub.add_parser("get")
    p.add_argument("path", help="raw API path, e.g. /crm/v8/org or /books/v3/reports/…")
    p.add_argument("--param", action="append", default=[])
    p.set_defaults(fn=cmd_get)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
