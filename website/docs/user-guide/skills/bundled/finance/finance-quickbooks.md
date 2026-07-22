---
title: "Quickbooks — QuickBooks Online via MCP: read customers, invoices, bills, accounts, reports; write only when enabled"
sidebar_label: "Quickbooks"
description: "QuickBooks Online via MCP: read customers, invoices, bills, accounts, reports; write only when enabled"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Quickbooks

QuickBooks Online via MCP: read customers, invoices, bills, accounts, reports; write only when enabled.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/finance/quickbooks` |
| Version | `1.0.0` |
| Author | KOPI AI AGENT |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `quickbooks`, `qbo`, `accounting`, `finance`, `bookkeeping`, `invoices`, `reports`, `mcp` |
| Related skills | [`xero`](/docs/user-guide/skills/bundled/finance/finance-xero) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Kopi loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# QuickBooks Online Accounting

Query and manage a QuickBooks Online (QBO) company through the **quickbooks MCP
server** (Intuit's official server). Use this skill whenever the user asks about
their QuickBooks data — customers, vendors, invoices, bills, payments, the chart
of accounts, journal entries, or financial reports.

The tools come from the QBO MCP (144 tools across ~29 entity types + 11 reports).
This skill tells you when and how to use them safely.

## Prerequisite

The quickbooks MCP must be installed and configured first:

```bash
kopi mcp install quickbooks
```

This clones + builds Intuit's server and prompts for `QUICKBOOKS_CLIENT_ID`,
`QUICKBOOKS_CLIENT_SECRET`, `QUICKBOOKS_REFRESH_TOKEN`, and `QUICKBOOKS_REALM_ID`
(stored in `~/.kopi/.env`). Getting the refresh token needs a one-time Intuit
browser OAuth handshake done outside the agent. If the quickbooks tools are not
available, tell the user to install the MCP and restart — do not improvise.

## Calling the tools (IMPORTANT — avoids tripping the circuit breaker)

Every QBO tool wraps its inputs in a required `params` object. Pass arguments as
`{ "params": { ... } }`, NOT at the top level. Examples:

- Company info: `get_company_info` → `{ "params": {} }`
- Get a customer: `get_customer` → `{ "params": { "id": "1" } }`
- A report: `get_profit_and_loss` → `{ "params": { ... } }`

If you call a tool with the wrong shape (missing `params`), the server returns an
`Invalid arguments` (-32602) error. KOPI's MCP circuit breaker counts consecutive
errors and, after 3, marks the whole server "unreachable" for ~60s — so a burst of
mis-shaped calls locks you out. Therefore:

- **Get the shape right the first time** — always wrap in `params`.
- **Probe with ONE call before fanning out.** Don't fire many tool calls in
  parallel until you've confirmed one succeeds; parallel mis-calls trip the
  breaker instantly.
- If you do hit "server unreachable", stop calling and wait ~60s for the cooldown;
  do not hammer it.

## Safety (MANDATORY)

- **Read-first.** Default to read/query/report operations — always safe.
- **Write access is OFF by default.** The MCP is installed with
  `QUICKBOOKS_DISABLE_WRITE=1`. Create/update/delete tools will refuse unless the
  user explicitly enabled writes. Do NOT ask them to disable the guard casually —
  this touches a REAL general ledger.
- If writes ARE enabled: before any create/update/delete, restate exactly what
  will change and get explicit confirmation. Never write speculatively.
- **Never** print or echo `QUICKBOOKS_*` credentials or `~/.kopi/.env` contents.

## Reading (the common case)

- **Entities** — Customer, Vendor, Employee, Invoice, Bill, Payment, Account,
  Item, Journal Entry, and more. List or fetch by id.
- **Reports** — Balance Sheet, Profit & Loss, Cash Flow, Trial Balance, General
  Ledger, Customer Sales, Aged Receivables/Payables. Use these for "how's the
  business doing?" questions instead of summing raw transactions.
- Summarise figures plainly (totals, notable lines); don't dump raw JSON.

## Writing (only if enabled + explicit confirmation)

When creating an invoice you typically resolve a Customer (by id), the Item/
Account, and tax details first, then build the line items, show the user the full
document, confirm, and create. Reference numbers/ids returned by the API should
be surfaced so the user can verify in QuickBooks.

## Tips

- `QUICKBOOKS_REALM_ID` binds to ONE company. A different company needs its own
  realm id + refresh token.
- Sandbox companies are safe for testing; production touches real books.
- The MCP also honours `QUICKBOOKS_DISABLE_UPDATE` / `QUICKBOOKS_DISABLE_DELETE`
  for finer-grained write control.
