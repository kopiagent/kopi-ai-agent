<div align="center">

<img src="assets/kopi-ai-agent-logo.jpg" width="200" alt="KOPI AI AGENT">

# ☕ KOPI AI AGENT

### The self-improving AI agent that learns from experience

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-8B4513?style=for-the-badge)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-kopiaiagent.com-2563EB?style=for-the-badge)](https://kopiaiagent.com/docs/)
[![中文](https://img.shields.io/badge/Lang-中文-red?style=for-the-badge)](README.zh-CN.md)
[![Español](https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge)](README.es.md)

[🌐 Website](https://kopiaiagent.com) · [📚 Docs](https://kopiaiagent.com/docs/) · [⚡ Quick Start](#-quick-start) · [🎮 Features](#-features)

---

*Built by [Kopi Ai Agent Pte Ltd](https://kopiaiagent.com) (Singapore). Run it on a $5 VPS, a GPU cluster, or in the cloud.*

</div>

---

It creates skills from experience, improves them during use, persists knowledge across sessions, and builds a deepening model of who you are. Talk to it from Telegram while it works on a cloud VM — no laptop tethering.

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
<tr><td><b>📈 Stock Intelligence</b></td><td>Built-in real-time market data (US & HK), 30+ technical indicators, AI-powered analysis. No API keys — just install and analyze.</td></tr>
<tr><td><b>🎬 Media Generation</b></td><td>Text-to-image (Krea 2, FAL, SDXL), video generation with voiceover & subtitles. All through unified MCP tools.</td></tr>
<tr><td><b>🧑‍💼 Digital Human</b></td><td>Alpaca-powered AI avatars with lip-sync, voice cloning, and multi-language TTS. For live streaming and customer service.</td></tr>
<tr><td><b>📰 Content Engine</b></td><td>Daily briefings, content repurposing (podcast→social), RSS monitoring, multi-language auto-publishing.</td></tr>
<tr><td><b>💼 Business Suite</b></td><td>SME advertising (TikTok ads + coupon engine), digital commerce (Stripe + USDC), customer onboarding portal.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://kopiaiagent.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs KOPI AI AGENT without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux one-liner above works there too. Found a bug? Please [file issues](https://github.com/kopiagent/kopi-ai-agent/issues).

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
kopi config get   # Print individual config values
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

## 🧠 KOPI Memory Provider

<img src="assets/kopi-memory-logo.jpg" width="180" align="right" alt="KOPI Memory">

KOPI AI AGENT ships with a dedicated **KOPI Memory** provider backed by [kopi-agent-memory](https://github.com/LINYIQ66/kopi-agent-memory) — a production-grade multi-layer memory system with:

- **Hot Tier (Redis)** — Session state, <1ms latency
- **Warm Tier (PostgreSQL + pgvector)** — Semantic search, HNSW indexing, ~5ms queries
- **Cold Tier (S3/MinIO)** — Unlimited archive with gzip compression
- **Multi-Agent Shared Memory** — Cross-agent KV store with TTL

**Enable it:**

```yaml
# config.yaml
memory:
  provider: kopi
```

**Environment variables:**

```bash
export KOPI_MEMORY_API_URL=http://localhost:8900
export KOPI_MEMORY_API_KEY="your-jwt-key"
export KOPI_MEMORY_USER_ID="kopi"
```

**Deploy the backend:**

```bash
git clone https://github.com/LINYIQ66/kopi-agent-memory.git
cd kopi-agent-memory
docker compose up -d
```

The provider exposes three tools to the agent:
- `memory_search` — Semantic search across past conversations
- `memory_save` — Store important facts and preferences
- `memory_forget` — Remove specific memories

---

## 📈 KOPI Stock Intelligence

KOPI AI AGENT includes a built-in **Stock Intelligence** engine — real-time market data, technical analysis, and AI-powered trading insights. No API keys to manage, no data sources to configure.

```bash
kopi tools          # enable Stock Intelligence tools
```

| Feature | Description |
|---------|-------------|
| **Real-time Quotes** | US & HK stocks, live price, volume, order book |
| **Technical Analysis** | MA/MACD/RSI/BOLL/KDJ — 30+ indicators, auto-computed |
| **K-Line Charts** | Historical candlestick data, multiple timeframes |
| **AI Market Insights** | LLM-powered sentiment analysis, trend detection |
| **Portfolio Tracking** | Watchlists, position tracking, P&L alerts |

**Use it from any platform:**

```
You: 分析一下苹果股票
KOPI: 📊 AAPL (Apple Inc.)
  当前价格: $234.40 (+1.2%)
  RSI: 58.3 (中性)
  MACD: 金叉形成中...
  综合评级: ⚡ 偏多
```

> 🔒 All market data is sourced through KOPI's proprietary data pipeline. No third-party API keys or credentials required — just install and start analyzing.

---

## 🎬 KOPI Media MCP (Video & Image Generation)

KOPI AI AGENT ships with integrated **Media Generation** capabilities — text-to-image, image editing, and video generation, all accessible through MCP tools.

### 🖼️ Image Generation

```bash
kopi tools          # enable Image Generation
```

| Backend | Models | Capabilities |
|---------|--------|-------------|
| **Krea 2** | Large, Medium, Turbo | Text-to-image, style transfer, reference-guided |
| **FAL** | SDXL, Flux, Upscaler | High-res generation, image-to-image, upscaling |
| **OpenRouter** | Multi-model | Reference-grounded image generation |

```
You: 生成一张赛博朋克风格的新加坡城市夜景
KOPI: ✨ Image generated and saved to assets/cyberpunk-sg.jpg
```

### 🎥 Video Generation

```bash
kopi tools          # enable Video Generation
```

- **Text-to-Video** — Describe a scene, get a video clip
- **Image-to-Video** — Animate a static image with motion
- **Multi-scene Scripts** — Batch generation from screenplay-style prompts
- **Voiceover + Subtitles** — Auto-narration with TTS + subtitle burn-in

```
You: 做一个30秒的产品宣传片，主题是AI咖啡机器人
KOPI: 🎬 Generating video...
  Scene 1: 航拍工厂全景 (5s)
  Scene 2: 机器人特写制作咖啡 (10s)
  Scene 3: 客户体验画面 (10s)
  Scene 4: 品牌logo + slogan (5s)
  ✅ Video saved to output/promo-30s.mp4
```

> 🔒 All media generation runs through KOPI's managed gateway. No separate API signups — billing is unified under your KOPI subscription.

---

## 🧑‍💼 KOPI Digital Human (Alpaca)

KOPI AI AGENT supports **AI Digital Human** avatars — lifelike virtual presenters powered by the Alpaca engine, for customer service, live streaming, and interactive demos.

```bash
kopi tools          # enable Digital Human
```

| Feature | Description |
|---------|-------------|
| **Real-time Avatar** | 3D rendered digital human with lip-sync |
| **Voice Cloning** | Custom voice from 30s of sample audio |
| **Multi-language** | Speak 30+ languages with natural TTS |
| **Knowledge Base** | Connect to your docs — the avatar answers questions |
| **Live Streaming** | Broadcast to TikTok, YouTube, WeChat channels |

> 🔒 Powered by KOPI's proprietary Alpaca engine. No external dependencies — activate via `kopi tools` and start creating.

---

## 📰 KOPI Content & Media Ecosystem

KOPI AI AGENT powers a full **content lifecycle** — from daily briefings to podcast repurposing to automated publishing.

### Daily Briefings

```bash
kopi tools          # enable Content & Briefings
```

| Feature | Description |
|---------|-------------|
| **Daily Digest** | Automated morning market briefings (SG/US/HK) delivered to Telegram |
| **Awesome Daily** | Curated tech & AI news digest, published as interactive HTML pages |
| **RSS Monitoring** | Blog & feed watcher with change detection and smart summarization |
| **Multi-language** | Auto-generate content in English, Chinese, Malay, Tamil |

```
You: 今天的财经新闻简报
KOPI: 📰 KOPI Daily — 2026-07-09
  📈 SG: STI +0.8%, DBS创年内新高
  🇺🇸 US: 纳指收涨1.2%, AI板块领涨
  🇭🇰 HK: 恒指微跌0.3%, 南向资金净流入
  🔗 Full report: sub.readinghero.xyz/awesome-daily/2026-07-09
```

### Content Repurposing Engine

Transform one piece of content into multi-platform output:

```
You: 把这篇播客转成小红书文案+推文+LinkedIn长文
KOPI: ✨ Content repurposed:
  📕 小红书: 3篇图文已生成
  🐦 Twitter: 5条thread
  💼 LinkedIn: 1篇长文已排版
```

### PDF & Document Tools

- **PDF Conversion** — Extract, merge, split, and convert PDF documents
- **OCR** — Scan and digitize printed documents with high accuracy
- **Document Generation** — Create .docx reports, invoices, proposals from templates

> 🔒 All content pipelines run through KOPI's managed infrastructure. No external API dependencies.

---

## 💼 KOPI Business Suite (SaaS)

KOPI AI AGENT includes ready-to-deploy **business tools** for SMEs in Southeast Asia.

### 🛍️ KOPI Shop — Digital Commerce

```bash
kopi tools          # enable KOPI Shop
```

| Feature | Description |
|---------|-------------|
| **Digital Products** | Sell premium prompts, AI agents, and digital assets |
| **Stripe + USDC** | Fiat payments via Stripe, crypto via Base network |
| **Instant Delivery** | Automated fulfillment on payment confirmation |
| **Multi-tenant** | Per-vendor storefronts with revenue analytics |

### 📊 SME Advertising Manager

Built-in **advertising management** for F&B and retail businesses:

| Feature | Description |
|---------|-------------|
| **Boss Survey** | Onboarding questionnaire for business profiling |
| **TikTok Ads** | Campaign creation, budget management, performance tracking |
| **Coupon Engine** | QR code generation, redemption tracking, expiry control |
| **KPI Dashboard** | Real-time ROAS, CTR, conversion metrics |

```
You: 查看这周的TikTok广告数据
KOPI: 📊 SME Ad Report — Week of Jul 7
  💰 总花费: SGD $480
  👀 曝光: 142K (+18% vs last week)
  🎯 CTR: 3.2% (行业平均 1.8%)
  ✅ 核销: 37张优惠券已使用
  💵 ROAS: 4.2x
```

### 🏪 KOPI Portal — Customer Onboarding

- **Self-service signup** — New customers onboard via web portal
- **API key provisioning** — Automatic key generation and quota allocation
- **Billing management** — Usage tracking, invoice generation, payment history

> 🔒 All business services are production-deployed on KOPI's managed cloud. Activate via `kopi tools` — no separate infrastructure needed.

---

## Community

- 🐛 [Issues](https://github.com/kopiagent/kopi-ai-agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [KOPI Claw](https://github.com/AaronWong1999/kopiclaw) — Community WeChat bridge: Run KOPI AI AGENT on WeChat.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Kopi Ai Agent Pte Ltd (Singapore)](https://kopiaiagent.com).
