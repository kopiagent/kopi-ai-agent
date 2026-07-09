<p align="center">
  <img src="assets/banner.png" alt="KOPI AI AGENT" width="100%">
</p>

# KOPI AI AGENT ☕

<p align="center">
  <a href="https://kopiaiagent.com"><b>kopiaiagent.com</b></a> | <a href="https://github.com/LINYIQ66/kopi-ai-agent">GitHub</a>
</p>

<p align="center">
  <a href="https://kopiaiagent.com/docs/"><img src="https://img.shields.io/badge/Docs-kopiaiagent.com-8B4513?style=for-the-badge" alt="Documentation"></a>
  <a href="https://github.com/LINYIQ66/kopi-ai-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

**The self-improving AI agent built by [Kopi Ai Agent Pte Ltd (Singapore)](https://kopiaiagent.com).** It creates skills from experience, improves them during use, persists knowledge across sessions, and builds a deepening model of who you are. Run it on a $5 VPS, a GPU cluster, or in the cloud. Talk to it from Telegram while it works on a cloud VM — no laptop tethering.

Use any model you want — **KOPI Proxy**, OpenRouter, OpenAI, or your own endpoint. Switch with `kopi model` — no code changes, no lock-in. New installs get **5 million tokens** auto-provisioned.

<table>
<tr><td><b>Works out of the box</b></td><td>Install with one command. Auto-provisioned API key with 5M token quota. Pick a model and start chatting immediately — no API key collection.</td></tr>
<tr><td><b>KOPI Proxy — built-in model provider</b></td><td>Pre-configured with KOPI Proxy (kopi-o, kopi-o-flash, kopi-flash). No separate API signups needed. Full model catalog at <a href="https://kopiaiagent.com/models">kopiaiagent.com/models</a>.</td></tr>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>MCP v1 + v2 support</b></td><td>Connect MCP stdio servers (filesystem, time, github) and SSE servers via KOPI MCP Gateway. Extended capabilities from day one.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Singularity, Modal, and Daytona. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://kopiaiagent.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs KOPI AI AGENT without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux one-liner above works there too. Found a bug? Please [file issues](https://github.com/LINYIQ66/kopi-ai-agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://kopiaiagent.com/install.ps1)
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, and **auto-provisions a KOPI Proxy API key with 5M tokens** — no manual signup needed.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
kopi              # start chatting!
```

Your first conversation is on us — 5M tokens included.

---

## Getting Started

```bash
kopi              # Interactive CLI — start a conversation
kopi model        # Choose your LLM provider and model
kopi tools        # Configure which tools are enabled
kopi config set   # Set individual config values
kopi gateway      # Start the messaging gateway (Telegram, Discord, etc.)
kopi setup        # Run the full setup wizard
kopi update       # Update to the latest version
kopi doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://kopiaiagent.com/docs/)**

---

## Built-in KOPI Proxy

KOPI AI AGENT comes pre-configured with **KOPI Proxy** as the default model provider:

| Model | Backend | Max Tokens |
|-------|---------|-----------|
| `kopi-o` | MiMo 2.5 Pro | 128K input / 4K output |
| `kopi-o-flash` | MiMo 2.5 | 128K input / 4K output |
| `kopi-flash` | DeepSeek v4 Pro | 128K input / 4K output |

No API keys to collect — just install and start chatting. Need more tokens? Manage your quota at [kopiaiagent.com/account](https://kopiaiagent.com/account).

---

## MCP Integration

KOPI AI AGENT supports MCP (Model Context Protocol) out of the box:

- **MCP v1 (stdio):** filesystem, time, github servers auto-configured on install
- **MCP v2 (SSE):** KOPI MCP Gateway at `wss://kopiaiagent.com/agg-mcp/sse`
- Add your own MCP servers via `kopi mcp add`

The KOPI MCP Gateway exposes KOPI-specific tools — AI agent orchestration, reasoning engines, and KOPI team coordination — through the standard MCP protocol.

---

## CLI vs Messaging Quick Reference

| Action | CLI | Messaging platforms |
|--------|-----|-------------------|
| Start chatting | `kopi` | Run `kopi gateway setup` + `kopi gateway start` |
| Start fresh conversation | `/new` or `/reset` | `/new` or `/reset` |
| Change model | `/model [provider:model]` | `/model [provider:model]` |
| Set a personality | `/personality [name]` | `/personality [name]` |
| Retry or undo | `/retry`, `/undo` | `/retry`, `/undo` |
| Context management | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]` |
| Browse skills | `/skills` or `/<skill-name>` | `/<skill-name>` |
| Interrupt | `Ctrl+C` or send a new message | `/stop` or send a new message |

For the full command lists, see the [CLI guide](https://kopiaiagent.com/docs/user-guide/cli) and the [Messaging Gateway guide](https://kopiaiagent.com/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[kopiaiagent.com/docs](https://kopiaiagent.com/docs/)**:

| Section | What's Covered |
|---------|---------------|
| [Quickstart](https://kopiaiagent.com/docs/getting-started/quickstart) | Install → setup → first conversation in 2 minutes |
| [CLI Usage](https://kopiaiagent.com/docs/user-guide/cli) | Commands, keybindings, personalities, sessions |
| [Configuration](https://kopiaiagent.com/docs/user-guide/configuration) | Config file, providers, models, all options |
| [Messaging Gateway](https://kopiaiagent.com/docs/user-guide/messaging) | Telegram, Discord, Slack, WhatsApp, Signal |
| [Security](https://kopiaiagent.com/docs/user-guide/security) | Command approval, DM pairing, container isolation |
| [Tools & Toolsets](https://kopiaiagent.com/docs/user-guide/features/tools) | 40+ tools, toolset system, terminal backends |
| [Skills System](https://kopiaiagent.com/docs/user-guide/features/skills) | Procedural memory, Skills Hub, creating skills |
| [Memory](https://kopiaiagent.com/docs/user-guide/features/memory) | Persistent memory, user profiles, best practices |
| [MCP Integration](https://kopiaiagent.com/docs/user-guide/features/mcp) | Connect any MCP server for extended capabilities |
| [Cron Scheduling](https://kopiaiagent.com/docs/user-guide/features/cron) | Scheduled tasks with platform delivery |
| [Architecture](https://kopiaiagent.com/docs/developer-guide/architecture) | Project structure, agent loop, key classes |
| [Contributing](https://kopiaiagent.com/docs/developer-guide/contributing) | Development setup, PR process, code style |

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://kopiaiagent.com/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors:

```bash
curl -fsSL https://kopiaiagent.com/install.sh | bash
cd "${KOPI_HOME:-$HOME/.kopi}/kopi-ai-agent"
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

Manual clone fallback:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv ~/.kopi/venvs/kopi-dev --python 3.11
source ~/.kopi/venvs/kopi-dev/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Community

- 🐛 [Issues](https://github.com/LINYIQ66/kopi-ai-agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [KOPI Claw](https://github.com/AaronWong1999/kopiclaw) — Community WeChat bridge: Run KOPI AI AGENT on WeChat.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Kopi Ai Agent Pte Ltd (Singapore)](https://kopiaiagent.com).
