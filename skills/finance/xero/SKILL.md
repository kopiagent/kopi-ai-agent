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

## Safety (MANDATORY)

- **Read-first.** Default to read/list/report operations. They are always safe.
- **Writes hit a REAL general ledger.** `create-invoice`, `create-contact`,
  `create-credit-note`, `create-manual-journal`, `delete-*`, etc. change real
  accounting records. Before ANY write, restate exactly what you will create/
  change and get explicit user confirmation. Never write speculatively.
- Whether writes even work depends on the OAuth **scopes** granted to the Custom
  Connection. If a write fails with a scope/permission error, that is by design —
  do not try to escalate; tell the user to re-grant scopes only if they intend to.
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

## Writing (only on explicit request + confirmation)

To create an invoice you usually need three lookups first:
1. `contactId` — from the contacts list.
2. `accountCode` — from the chart of accounts.
3. `taxType` — from the tax rates list.

Build the line items, **show the user the full invoice you're about to create**,
confirm, then create it. Xero returns a deep link to the new record — surface
that link to the user so they can review it in Xero.

Manual journals must balance (debits = credits) and need at least two lines.

## Tips

- Custom Connection binds to ONE organisation. Multi-org needs separate setup.
- Xero's **Demo Company** is free and safe for testing (fake data, resets ~monthly).
- Prefer specific report tools over scraping many invoices when the user wants
  aggregate figures — reports are pre-computed and cheaper.
