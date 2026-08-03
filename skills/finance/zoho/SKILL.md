---
name: zoho
description: "Zoho Books (accounting) and Zoho CRM via the official REST APIs: organizations, invoices, bills, expenses, leads, deals, COQL queries."
version: 1.0.0
author: KOPI AI AGENT
license: MIT
platforms: [linux, macos, windows]
metadata:
  kopi:
    tags: [zoho, zoho-books, zoho-crm, accounting, finance, crm, invoices, leads, deals]
    category: finance
    homepage: https://www.zoho.com/books/api/v3/
    related_skills: [xero, quickbooks]
---

# Zoho Books + CRM

Query Zoho **Books** (accounting: invoices, bills, expenses, banking) and
Zoho **CRM** (leads, contacts, accounts, deals) through Zoho's official
REST APIs. One Zoho app and one refresh token cover both — there is no
official Zoho MCP, and third-party ones don't meet the catalog's trust
bar, so this skill ships a stdlib-only client script instead.

Use this skill when the user asks about their Zoho data — outstanding
invoices, expenses, a customer's balance, pipeline/deals, lead status —
including questions arriving via Telegram/WhatsApp.

## The data-center trap (read this first)

Zoho accounts live in exactly ONE data center; both the login server and
the API host differ per DC (`accounts.zoho.eu` / `www.zohoapis.eu`, …).
The wrong DC produces `invalid_client` **even with correct credentials**.
Set `ZOHO_DC` to where the account was registered:
`com` (US) | `eu` | `in` | `com.au` | `jp` | `com.cn` | `sa` | `ca`.

## Setup (one-time)

1. [api-console.zoho.com](https://api-console.zoho.com) (on the account's
   DC!) → **Add Client → Server-based Applications**.
   Redirect URI: `http://localhost:8123/callback`.
2. Put the client credentials in `~/.kopi/.env`:

```bash
ZOHO_CLIENT_ID=1000.XXXX
ZOHO_CLIENT_SECRET=...
ZOHO_DC=com                # the account's data center
```

3. Mint the refresh token (authorize in a browser once):

```bash
python3 {skill_dir}/scripts/zoho_client.py auth-url    # prints the URL to open
# authorize → browser lands on localhost:8123 → grab ?code=... quickly
python3 {skill_dir}/scripts/zoho_client.py exchange <code>
```

`exchange` writes `ZOHO_REFRESH_TOKEN` straight into `~/.kopi/.env`
(never prints it). Zoho auth codes expire in ~2 minutes — exchange
immediately. The default scopes are **read-only** for both products;
writes require explicitly re-minting with `--scopes`.

4. For Books, pick the organization:

```bash
python3 {skill_dir}/scripts/zoho_client.py orgs
# → set ZOHO_BOOKS_ORG_ID=... in ~/.kopi/.env
```

## Querying

```bash
# Books
python3 {skill_dir}/scripts/zoho_client.py books invoices --param status=unpaid
python3 {skill_dir}/scripts/zoho_client.py books contacts
python3 {skill_dir}/scripts/zoho_client.py books expenses --param date_start=2026-07-01

# CRM (record lists need fields; sensible defaults ship for the big four modules)
python3 {skill_dir}/scripts/zoho_client.py crm Leads
python3 {skill_dir}/scripts/zoho_client.py crm Deals --fields Deal_Name,Stage,Amount

# CRM COQL for anything analytical
# 注意:Zoho COQL 强制要求 where 子句;全表就用 "where id is not null"
python3 {skill_dir}/scripts/zoho_client.py crm-query \
  "select Deal_Name, Amount from Deals where Stage = 'Negotiation' limit 20"

# Raw escape hatch (reports, org info, anything not wrapped)
python3 {skill_dir}/scripts/zoho_client.py get /crm/v8/org
python3 {skill_dir}/scripts/zoho_client.py get /books/v3/reports/profitandloss
```

Access tokens are refresh-granted automatically and cached (~1 h, file
mode 0600) — Zoho rate-limits token minting, so don't clear the cache in
a loop.

## Safety (MANDATORY)

- **Read-first.** The default scopes are read-only; keep them that way
  unless the user explicitly needs writes, then re-mint with `--scopes`
  and treat every write as touching a real ledger / real pipeline.
- **Never** print or echo `ZOHO_CLIENT_SECRET` / `ZOHO_REFRESH_TOKEN` or
  any part of `~/.kopi/.env`. The `exchange` command writes the refresh
  token to `.env` itself precisely so it never transits chat.
- Books amounts are org-currency; say which organization the numbers
  come from when multiple orgs exist.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `invalid_client` | wrong `ZOHO_DC` for this account (the #1 issue), or client id/secret typo |
| `invalid_code` on exchange | auth code expired (~2 min) — re-run auth-url |
| `INVALID_TOKEN` / 401 on API calls | refresh token revoked, or minted on a different DC |
| CRM list returns `REQUIRED_PARAM_MISSING` | module needs `--fields` (defaults only cover Leads/Contacts/Accounts/Deals) |
| COQL returns `missing clause` | COQL requires a `where` clause — add `where id is not null` for full scans |
| Books call complains about organization | `ZOHO_BOOKS_ORG_ID` unset — run `orgs` |
| `You have made too many requests` on token | token-mint rate limit — reuse the cache, don't delete it |
