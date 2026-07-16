# Langfuse Observability Plugin

This plugin ships bundled with Kopi but is **opt-in** — it only loads when
you explicitly enable it.

## Enable

Pick one:

```bash
# Interactive: walks you through credentials + SDK install + enable
kopi tools  # → Langfuse Observability

# Manual
pip install langfuse
kopi plugins enable observability/langfuse
```

## Required credentials

Set these in `~/.kopi/.env` (or via `kopi tools`):

```bash
KOPI_LANGFUSE_PUBLIC_KEY=pk-lf-...
KOPI_LANGFUSE_SECRET_KEY=sk-lf-...
KOPI_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Without the SDK or credentials the hooks no-op silently — the plugin fails
open.

## Verify

```bash
kopi plugins list                 # observability/langfuse should show "enabled"
kopi chat -q "hello"              # then check Langfuse for a "Kopi turn" trace
```

## Optional tuning

```bash
KOPI_LANGFUSE_ENV=production       # environment tag
KOPI_LANGFUSE_RELEASE=v1.0.0       # release tag
KOPI_LANGFUSE_SAMPLE_RATE=0.5      # sample 50% of traces
KOPI_LANGFUSE_MAX_CHARS=12000      # max chars per field (default: 12000)
KOPI_LANGFUSE_DEBUG=true           # verbose plugin logging
```

## Disable

```bash
kopi plugins disable observability/langfuse
```
