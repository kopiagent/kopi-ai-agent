---
name: xero
description: "Xero accounting via MCP: read orgs, contacts, invoices, accounts, reports, tax rates; create with care."
version: 1.0.0
author: KOPI AI AGENT
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [xero, accounting, finance, bookkeeping, invoices, reports, mcp]
    category: finance
    homepage: https://github.com/XeroAPI/xero-mcp-server
    related_skills: [quickbooks]
---

# Xero Accounting

Query and manage a Xero organisation through the **xero MCP server**. Use this
skill whenever the user asks about their Xero data — invoices, bills, contacts,
the chart of accounts, financial reports (P&L, balance sheet), tax rates, bank
transactions, or bookkeeping in general.

The tools come from the `@xeroapi/xero-mcp-server` MCP. This skill tells you when
and how to use them safely — it does not replace them.

## Prerequisite

The xero MCP must be installed and configured first:

```bash
kopi mcp install xero
```

That prompts for `XERO_CLIENT_ID` / `XERO_CLIENT_SECRET` (a Xero **Custom
Connection**) and stores them in `~/.kopi/.env`. If the xero tools are not
available in the current session, tell the user to run the command above and
restart the session — do not try to work around a missing MCP.

## Read-only via this MCP (IMPORTANT)

Treat Xero as **read-only through KOPI**. Use the read/list/report tools freely —
they work well. **Do NOT attempt transaction writes** (`create-invoice`,
`create-manual-journal`, `create-credit-note`, `delete-*`): on Custom Connections
that use Xero's newer *granular* scopes, this MCP requests the wrong OAuth scope
and every transaction write fails with a generic "unexpected error". Repeated
failed writes also trip KOPI's MCP circuit breaker and can briefly knock out
Xero *reads* too. So don't try them.

`create-contact` is the one write that does work (the contacts scope name is
unchanged), but avoid it unless the user explicitly asks — it still writes to a
real org.

If the user needs to bulk-create Xero data (invoices, journals) for testing,
that must be done outside this MCP (e.g. a direct Xero API script), not by the
agent through these tools.

## Safety (MANDATORY)

- **Read-first.** Read/list/report operations are always safe — prefer them.
- **Writes hit a REAL general ledger.** Any create/update/delete changes real
  accounting records. Given the granular-scope limitation above, do not attempt
  transaction writes through this MCP at all.
- **Never** print, summarise, or echo `XERO_CLIENT_ID` / `XERO_CLIENT_SECRET` or
  anything from `~/.kopi/.env`. Credentials are the user's to manage.

## Reading (the common case)

Typical read workflows and the tool family to reach for:

- **Organisation info** — org name, currency, country, tax basis, financial year.
- **Contacts** — list customers/suppliers; each has an `id` used elsewhere.
- **Invoices** — `ACCREC` (accounts receivable) and `ACCPAY` (accounts payable),
  with amounts and status (DRAFT / SUBMITTED / AUTHORISED / PAID).
- **Chart of accounts** — account codes + types (BANK, REVENUE, EXPENSE, EQUITY,
  CURRLIAB, …). Needed to build invoice/journal lines.
- **Reports** — Profit & Loss, Balance Sheet, Trial Balance, Aged Receivables/
  Payables. Great for "how's the business doing?" questions.
- **Tax rates** — tax types and effective rates, needed for invoice line items.

When answering a business question, pull the relevant report or list, then
summarise the numbers plainly (totals, notable lines) rather than dumping raw JSON.

## Writing

Transaction writes (invoices, bills, manual journals, credit notes) are **not
usable through this MCP** on granular-scope connections — see "Read-only via this
MCP" above. If a user asks to create such records, explain the limitation and
that it must be done via a direct Xero API integration, rather than attempting a
call that will fail and trip the circuit breaker.

## Tips

- Custom Connection binds to ONE organisation. Multi-org needs separate setup.
- Xero's **Demo Company** is free and safe for testing (fake data, resets ~monthly).
- Prefer specific report tools over scraping many invoices when the user wants
  aggregate figures — reports are pre-computed and cheaper.
