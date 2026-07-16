---
name: kopi-agent
description: "Configure, extend, or contribute to Kopi Agent."
version: 2.3.0
author: Kopi Agent + Teknium
license: MIT
platforms: [linux, macos, windows]
metadata:
  kopi:
    tags: [kopi, setup, configuration, multi-agent, spawning, cli, gateway, development]
    homepage: https://github.com/NousResearch/kopi-agent
    related_skills: [claude-code, codex, opencode]
---

# Kopi Agent

Kopi Agent is an open-source AI agent framework by Nous Research that runs in your terminal, a native desktop app, messaging platforms, and IDEs. It's in the same category as Claude Code (Anthropic), Codex (OpenAI), and OpenClaw — autonomous coding and task-execution agents that use tool calling to interact with your system. Kopi works with any LLM provider (OpenRouter, Anthropic, OpenAI, Google, DeepSeek, xAI, local models, and 20+ others) and runs on Linux, macOS, Windows, and WSL.

What makes Kopi different:

- **Self-improving through skills** — Kopi learns from experience by saving reusable procedures as skills. When it solves a complex problem, discovers a workflow, or gets corrected, it can persist that knowledge as a skill document that loads into future sessions. Skills accumulate over time, making the agent better at your specific tasks and environment.
- **Persistent memory across sessions** — remembers who you are, your preferences, environment details, and lessons learned. Pluggable memory backends (built-in, Honcho, Mem0, and more) let you choose how memory works.
- **Multi-platform gateway** — the same agent runs on Telegram, Discord, Slack, WhatsApp, iMessage, Signal, Matrix, Teams, Email, and a dozen more platforms with full tool access, not just chat.
- **Many surfaces** — the same agent core drives the CLI, the Ink TUI, a native Electron desktop app, a web dashboard, and an ACP server for IDEs (VS Code / Zed / JetBrains).
- **Provider-agnostic** — swap models and providers mid-workflow without changing anything else. Credential pools rotate across multiple API keys automatically.
- **Profiles** — run multiple independent Kopi instances with isolated configs, sessions, skills, and memory.
- **Extensible** — plugins, MCP servers, custom tools, webhook triggers, cron scheduling, and the full Python ecosystem.

People use Kopi for software development, research, system administration, data analysis, content creation, home automation, and anything else that benefits from an AI agent with persistent context and full system access.

**This skill helps you work with Kopi Agent effectively** — setting it up, configuring features, spawning additional agent instances, troubleshooting issues, finding the right commands and settings, and understanding how the system works when you need to extend or contribute to it.

**Docs:** https://kopi-agent.nousresearch.com/docs/

## Scope & Verification

This skill is a concise operating guide, not the complete source of truth for every Kopi feature. If a Kopi feature, command, or setting is not mentioned here, do not treat that absence as evidence that it does not exist. Check the live repository and official docs before giving a negative answer.

Good verification targets:

- CLI commands: `kopi --help`, `kopi <command> --help`, and `kopi_cli/main.py`
- User documentation: https://kopi-agent.nousresearch.com/docs/
- Source tree: https://github.com/NousResearch/kopi-agent

## Quick Start

```bash
# Install (shell installer — sets up uv, Python, the venv, and the launcher)
curl -fsSL https://kopi-agent.nousresearch.com/install.sh | bash

# Or via PyPI (ships the TUI bundle + shell launcher)
pip install kopi-agent       # or: uv pip install kopi-agent

# Interactive chat (default surface; set display.interface: tui to launch the Ink TUI instead)
kopi

# Single query
kopi chat -q "What is the capital of France?"

# Setup wizard  /  pick model+provider  /  health check
kopi setup
kopi model
kopi doctor

# Other surfaces
kopi desktop                 # launch the native desktop app (alias: kopi gui)
kopi dashboard               # web admin panel + embedded chat
kopi proxy                   # OpenAI-compatible local proxy backed by your OAuth provider
```

---

## CLI Reference

### Global Flags

```
kopi [flags] [command]

  --version, -V             Show version
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --pass-session-id         Include session ID in system prompt
```

No subcommand defaults to `chat`.

### Chat

```
kopi chat [flags]
  -q, --query TEXT          Single query, non-interactive
  -m, --model MODEL         Model (e.g. anthropic/claude-sonnet-4)
  -t, --toolsets LIST       Comma-separated toolsets
  --provider PROVIDER       Force provider (openrouter, anthropic, nous, etc.)
  -v, --verbose             Verbose output
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --source TAG              Session source tag (default: cli)
```

### Configuration

```
kopi setup [section]      Interactive wizard (model|terminal|gateway|tools|agent)
kopi model                Interactive model/provider picker
kopi config               View current config
kopi config edit          Open config.yaml in $EDITOR
kopi config set KEY VAL   Set a config value
kopi config path          Print config.yaml path
kopi config env-path      Print .env path
kopi config check         Check for missing/outdated config
kopi config migrate       Update config with new options
kopi doctor [--fix]       Check dependencies and config
kopi status [--all]       Show component status
```

Credentials (OAuth + API keys, with pooling) are managed under `kopi auth` — see the Credentials & Pools section below.

### Tools & Skills

```
kopi tools                Interactive tool enable/disable (curses UI)
kopi tools list           Show all tools and status
kopi tools enable NAME    Enable a toolset
kopi tools disable NAME   Disable a toolset

kopi skills list          List installed skills
kopi skills search QUERY  Search the skills hub
kopi skills install ID    Install a skill (ID can be a hub identifier OR a direct https://…/SKILL.md URL; pass --name to override when frontmatter has no name)
kopi skills inspect ID    Preview without installing
kopi skills config        Enable/disable skills per platform
kopi skills check         Check for updates
kopi skills update        Update outdated skills
kopi skills uninstall N   Remove a hub skill
kopi skills publish PATH  Publish to registry
kopi skills browse        Browse all available skills
kopi skills tap add REPO  Add a GitHub repo as skill source
```

### MCP Servers

```
kopi mcp serve            Run Kopi as an MCP server
kopi mcp add NAME         Add an MCP server (--url or --command)
kopi mcp remove NAME      Remove an MCP server
kopi mcp list             List configured servers
kopi mcp test NAME        Test connection
kopi mcp configure NAME   Toggle tool selection
```

How the built-in MCP client connects servers (stdio/HTTP), auto-discovers
their tools, and exposes them as first-class tools, plus catalog install
(`kopi mcp install <name>`): `skill_view(name="kopi-agent", file_path="references/native-mcp.md")`.

### Gateway (Messaging Platforms)

```
kopi gateway run          Start gateway foreground
kopi gateway install      Install as background service
kopi gateway start/stop   Control the service
kopi gateway restart      Restart the service
kopi gateway status       Check status
kopi gateway setup        Configure platforms
```

Supported platforms (20+): Telegram, Discord, Slack, WhatsApp (Baileys bridge + official Business Cloud API), iMessage (Photon — `kopi photon setup`, the BlueBubbles successor with no Mac relay), Signal, Email, SMS, Matrix, Mattermost, Microsoft Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin (WeChat), Raft (agent network), API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`, so new ones drop in without touching core.

Platform docs: https://kopi-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
kopi sessions list        List recent sessions
kopi sessions browse      Interactive picker
kopi sessions export OUT  Export to JSONL
kopi sessions rename ID T Rename a session
kopi sessions delete ID   Delete a session
kopi sessions prune       Clean up old sessions (--older-than N days)
kopi sessions stats       Session store statistics
```

### Cron Jobs

```
kopi cron list            List jobs (--all for disabled)
kopi cron create SCHED    Create: '30m', 'every 2h', '0 9 * * *'
kopi cron edit ID         Edit schedule, prompt, delivery
kopi cron pause/resume ID Control job state
kopi cron run ID          Trigger on next tick
kopi cron remove ID       Delete a job
kopi cron status          Scheduler status
```

### Webhooks

```
kopi webhook subscribe N  Create route at /webhooks/<name>
kopi webhook list         List subscriptions
kopi webhook remove NAME  Remove a subscription
kopi webhook test NAME    Send a test POST
```

Full setup, route config, payload templating, and event-driven agent-run
patterns: `skill_view(name="kopi-agent", file_path="references/webhooks.md")`.

### Profiles

```
kopi profile list         List all profiles
kopi profile create NAME  Create (--clone, --clone-all, --clone-from)
kopi profile use NAME     Set sticky default
kopi profile delete NAME  Delete a profile
kopi profile show NAME    Show details
kopi profile alias NAME   Manage wrapper scripts
kopi profile rename A B   Rename a profile
kopi profile export NAME  Export to tar.gz
kopi profile import FILE  Import from archive
```

### Credentials & Pools

```
kopi auth                 Interactive credential manager
kopi auth add [PROVIDER]  Add OAuth or API-key credential
                            (e.g. nous, openai-codex, qwen-oauth, anthropic)
kopi auth list [PROVIDER] List pooled credentials
kopi auth remove P INDEX  Remove by provider + index
kopi auth reset PROVIDER  Clear exhaustion status
```

Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
kopi insights [--days N]  Usage analytics
kopi update               Update to latest version
kopi desktop / gui        Launch the native desktop app
kopi dashboard            Web admin panel + embedded chat
kopi proxy                OpenAI-compatible local proxy backed by an OAuth provider
kopi portal               Quick setup / sign in via Nous Portal
kopi kanban <verb>        Multi-agent work-queue board (init/create/list/show/assign/…)
kopi pairing list/approve/revoke  DM authorization
kopi plugins list/install/remove  Plugin management
kopi secrets bitwarden …  External secret store (Bitwarden Secrets Manager)
kopi memory setup/status/off  Memory provider config
kopi send                 Send a one-off message through a gateway platform
kopi completion bash|zsh  Shell completions
kopi acp                  ACP server (IDE integration)
kopi claw migrate         Migrate from OpenClaw
kopi uninstall            Uninstall Kopi
```

For the full, authoritative command list run `kopi --help` (and `kopi <command> --help`). Plugin- and provider-supplied subcommands (e.g. `kopi photon setup` for iMessage) only appear once their plugin is installed/active.

---

## Slash Commands (In-Session)

Type these during an interactive chat session. New commands land fairly
often; if something below looks stale, run `/help` in-session for the
authoritative list or see the [live slash commands reference](https://kopi-agent.nousresearch.com/docs/reference/slash-commands).
The registry of record is `kopi_cli/commands.py` — every consumer
(autocomplete, Telegram menu, Slack mapping, `/help`) derives from it.

### Session Control
```
/new (/reset)        Fresh session
/clear               Clear screen + new session (CLI)
/retry               Resend last message
/undo                Remove last exchange
/title [name]        Name the session
/compress            Manually compress context
/stop                Kill background processes
/rollback [N]        Restore filesystem checkpoint
/snapshot [sub]      Create or restore state snapshots of Kopi config/state (CLI)
/background <prompt> Run prompt in background
/queue <prompt>      Queue for next turn
/steer <prompt>      Inject a message after the next tool call without interrupting
/agents (/tasks)     Show active agents and running tasks
/resume [name]       Resume a named session
/goal [text|sub]     Set a standing goal Kopi works on across turns until achieved
                     (subcommands: status, pause, resume, clear)
/redraw              Force a full UI repaint (CLI)
```

### Configuration
```
/config              Show config (CLI)
/model [name]        Show or change model
/personality [name]  Set personality
/reasoning [level]   Set reasoning (none|minimal|low|medium|high|xhigh|max|ultra|show|hide)
/verbose             Cycle: off → new → all → verbose
/voice [on|off|tts]  Voice mode
/yolo                Toggle approval bypass
/busy [sub]          Control what Enter does while Kopi is working (CLI)
                     (subcommands: queue, steer, interrupt, status)
/indicator [style]   Pick the TUI busy-indicator style (CLI)
                     (styles: kaomoji, emoji, unicode, ascii)
/footer [on|off]     Toggle gateway runtime-metadata footer on final replies
/skin [name]         Change theme (CLI)
/statusbar           Toggle status bar (CLI)
```

### Tools & Skills
```
/tools               Manage tools (CLI)
/toolsets            List toolsets (CLI)
/skills              Search/install skills (CLI)
/skill <name>        Load a skill into session
/reload-skills       Re-scan ~/.kopi/skills/ for added/removed skills
/reload              Reload .env variables into the running session (CLI)
/reload-mcp          Reload MCP servers
/cron                Manage cron jobs (CLI)
/curator [sub]       Background skill maintenance (status, run, pin, archive, …)
/kanban [sub]        Multi-profile collaboration board (tasks, links, comments)
/plugins             List plugins (CLI)
```

### Gateway
```
/approve             Approve a pending command (gateway)
/deny                Deny a pending command (gateway)
/restart             Restart gateway (gateway)
/sethome             Set current chat as home channel (gateway)
/update              Update Kopi to latest (gateway)
/topic [sub]         Enable or inspect Telegram DM topic sessions (gateway)
/platforms (/gateway) Show platform connection status (gateway)
```

### Utility
```
/branch (/fork)      Branch the current session
/handoff <platform>  Hand the live session off to a messaging platform (CLI)
/fast                Toggle priority/fast processing
/browser             Open CDP browser connection
/history             Show conversation history (CLI)
/save                Save conversation to file (CLI)
/copy [N]            Copy the last assistant response to clipboard (CLI)
/paste               Attach clipboard image (CLI)
/image               Attach local image file (CLI)
```

### Info
```
/help                Show commands
/commands [page]     Browse all commands (gateway)
/usage               Token usage
/insights [days]     Usage analytics
/status              Session info (gateway)
/profile             Active profile info
/debug               Upload debug report (system info + logs) and get shareable links
```

### Exit
```
/quit (/exit, /q)    Exit CLI
```

---

## Key Paths & Config

```
~/.kopi/config.yaml       Main configuration
~/.kopi/.env              API keys and secrets (under $KOPI_HOME if set)
$KOPI_HOME/skills/        Installed skills
~/.kopi/sessions/         Gateway routing index, request dumps, *.jsonl transcripts (and optional per-session JSON snapshots when sessions.write_json_snapshots: true)
~/.kopi/state.db          Canonical session store (SQLite + FTS5)
~/.kopi/logs/             Gateway and error logs
~/.kopi/auth.json         OAuth tokens and credential pools
~/.kopi/kopi-agent/     Source code (if git-installed)
```

Profiles use `~/.kopi/profiles/<name>/` with the same layout.

### Config Sections

Edit with `kopi config edit` or `kopi config set section.key value`.

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length` |
| `agent` | `max_turns` (90), `tool_use_enforcement` |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `interface` (cli/tui), `tool_progress`, `show_reasoning`, `show_cost`, `language` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider` |
| `security` | `tirith_enabled`, `website_blocklist` |
| `delegation` | `model`, `provider`, `base_url`, `api_key`, `max_iterations` (50), `reasoning_effort` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |
| `curator` | `enabled`, `consolidate` (false — opt-in aux-model skill consolidation), `interval_hours`, `stale_after_days` |

Full config reference: https://kopi-agent.nousresearch.com/docs/user-guide/configuration

### Providers

20+ providers supported. Set via `kopi model` or `kopi setup`.

| Provider | Auth | Key env var |
|----------|------|-------------|
| OpenRouter | API key | `OPENROUTER_API_KEY` |
| Anthropic | API key | `ANTHROPIC_API_KEY` |
| Nous Portal | OAuth | `kopi auth` |
| OpenAI Codex | OAuth | `kopi auth` |
| GitHub Copilot | Token | `COPILOT_GITHUB_TOKEN` |
| Google Gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| DeepSeek | API key | `DEEPSEEK_API_KEY` |
| xAI / Grok | API key | `XAI_API_KEY` |
| Hugging Face | Token | `HF_TOKEN` |
| Z.AI / GLM | API key | `GLM_API_KEY` |
| MiniMax | API key | `MINIMAX_API_KEY` |
| MiniMax CN | API key | `MINIMAX_CN_API_KEY` |
| Kimi / Moonshot | API key | `KIMI_API_KEY` |
| Alibaba / DashScope | API key | `DASHSCOPE_API_KEY` |
| Xiaomi MiMo | API key | `XIAOMI_API_KEY` |
| Kilo Code | API key | `KILOCODE_API_KEY` |
| OpenCode Zen | API key | `OPENCODE_ZEN_API_KEY` |
| OpenCode Go | API key | `OPENCODE_GO_API_KEY` |
| Qwen OAuth | OAuth | `kopi auth add qwen-oauth` |
| Custom endpoint | Config | `model.base_url` + `model.api_key` in config.yaml |
| GitHub Copilot ACP | External | `COPILOT_CLI_PATH` or Copilot CLI |

Full provider docs: https://kopi-agent.nousresearch.com/docs/integrations/providers

### Toolsets

Enable/disable via `kopi tools` (interactive) or `kopi tools enable/disable NAME`.

| Toolset | What it provides |
|---------|-----------------|
| `web` | Web search and content extraction |
| `search` | Web search only (subset of `web`) |
| `browser` | Browser automation (Browserbase, Camofox, or local Chromium) |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `vision` | Image analysis |
| `image_gen` | AI image generation and image-to-image editing |
| `video` | Video analysis (`video_analyze`) and generation |
| `x_search` | First-class X (Twitter) search (X OAuth or API key) |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `messaging` | Cross-platform message sending |
| `todo` | In-session task planning and tracking |
| `kanban` | Multi-agent work-queue tools (gated to workers) |
| `debugging` | Extra introspection/debug tools (off by default) |
| `safe` | Minimal, low-risk toolset for locked-down sessions |
| `spotify` | Spotify playback and playlist control |
| `homeassistant` | Smart home control (off by default) |
| `discord` | Discord integration tools |
| `discord_admin` | Discord admin/moderation tools |
| `feishu_doc` | Feishu (Lark) document tools |
| `feishu_drive` | Feishu (Lark) drive tools |
| `yuanbao` | Yuanbao integration tools |
| `rl` | Reinforcement learning tools (off by default) |

Full enumeration lives in `toolsets.py` as the `TOOLSETS` dict; `_KOPI_CORE_TOOLS` is the default bundle most platforms inherit from.

Tool changes take effect on `/reset` (new session). They do NOT apply mid-conversation to preserve prompt caching.

---

## Project Context Files

Kopi injects project-level instructions into the system prompt by reading context files from the working directory. The discovery order is **first match wins** — only one project context source is loaded per session.

| File (in priority order) | Discovery | Use when |
|---|---|---|
| `.kopi.md` / `KOPI.md` | Walks parents up to the git root, stops at git root | You want hierarchical project rules (root + per-package overrides) |
| `AGENTS.md` / `agents.md` | **Cwd only** — subdirectory and parent copies are ignored | You want portable agent instructions that work the same in Kopi, Claude Code, Codex, etc. |
| `CLAUDE.md` / `claude.md` | Cwd only | Same as AGENTS.md, Claude-flavored |
| `.cursorrules` / `.cursor/rules/*.mdc` | Cwd only | Migrating from Cursor |

`SOUL.md` (in `$KOPI_HOME`) is independent and always loaded when present — it sets the agent's identity, not project rules.

### Pick the right one

- **Use `.kopi.md`** when you want Kopi-specific behavior that lives above the cwd (root + subtree), or when you want rules to inherit from a parent directory. The parent walk stops at the git root, so a home-level `.kopi.md` won't leak into every project (a git repo's root is the boundary).
- **Use `AGENTS.md`** when the same project will also be worked on by other agents (Codex, Claude Code, OpenCode). Those tools all have their own conventions for `AGENTS.md`, and the "cwd only" contract keeps the file portable.
- **Don't put project rules in `~/.kopi/AGENTS.md`** (or any other home-level location). When Kopi runs with that directory as cwd, the file loads — but only for that one directory. For cross-project context, use `SOUL.md` (in `$KOPI_HOME`, identity-only) or install a skill via `kopi skills install`.

### Size and truncation

Each context file is capped at 20,000 characters. Files longer than that get **head + tail** truncated (the middle is dropped, with a `[...truncated...]` marker). For large project rules, prefer splitting into multiple skills over cramming one file.

### Security

All context files pass through the threat-pattern scanner before reaching the system prompt. Patterns matching prompt injection or promptware are replaced with a `[BLOCKED: ...]` placeholder. This means an `AGENTS.md` containing obvious injection attempts won't reach the model — the scanner blocks the content, not the file, so the rest of the file still loads.

### Disable for one session

`kopi --ignore-rules` skips auto-injection of all project context files (`.kopi.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`) **and** `SOUL.md` identity, plus user config, plugins, and MCP servers. Use it to isolate whether a problem is your setup or Kopi itself.

### Example: a small `.kopi.md`

```markdown
# My Project

Kopi: when working in this repo, follow these rules.

## Build
- Always run `make test` before declaring a change done.
- Use `uv run` for Python, not `pip install`.

## Style
- Prefer `pathlib.Path` over `os.path`.
- No `print()` in production code — use the `logger`.
```

That file at `/home/me/projects/myrepo/.kopi.md` is auto-loaded when Kopi runs in any subdirectory of `/home/me/projects/myrepo`, but not when it runs in `/home/me/other-project`.

## Security & Privacy Toggles

Common "why is Kopi doing X to my output / tool calls / commands?" toggles — and the exact commands to change them. Most of these need a fresh session (`/reset` in chat, or start a new `kopi` invocation) because they're read once at startup.

### Secret redaction in tool output

Secret redaction is **on by default** — tool output (terminal stdout, `read_file`, web content, subagent summaries, etc.) is scanned for strings that look like API keys, tokens, and secrets before it enters the conversation context and logs. Leave it enabled for normal use:

```bash
kopi config set security.redact_secrets true       # keep enabled globally
```

**Restart required.** `security.redact_secrets` is snapshotted at import time — toggling it mid-session (e.g. via `export KOPI_REDACT_SECRETS=false` from a tool call) will NOT take effect for the running process. Tell the user to change it in config from a terminal, then start a new session. This is deliberate — it prevents an LLM from flipping the toggle on itself mid-task.

Disable only when you deliberately need raw credential-like strings for debugging or redactor development:
```bash
kopi config set security.redact_secrets false
```

### PII redaction in gateway messages

Separate from secret redaction. When enabled, the gateway hashes user IDs and strips phone numbers from the session context before it reaches the model:

```bash
kopi config set privacy.redact_pii true    # enable
kopi config set privacy.redact_pii false   # disable (default)
```

### Command approval prompts

By default (`approvals.mode: smart`), Kopi asks an auxiliary LLM to assess shell commands flagged as destructive (`rm -rf`, `git reset --hard`, etc.). The modes are:

- `smart` — auto-approve a low-risk command once, deny high-risk commands, and prompt when uncertain (default)
- `manual` — always prompt
- `off` — skip all approval prompts (equivalent to `--yolo`)

```bash
kopi config set approvals.mode smart       # recommended middle ground
kopi config set approvals.mode off         # bypass everything (not recommended)
```

Per-invocation bypass without changing config:
- `kopi --yolo …`
- `export KOPI_YOLO_MODE=1`

Note: YOLO / `approvals.mode: off` does NOT turn off secret redaction. They are independent.

### Shell hooks allowlist

Some shell-hook integrations require explicit allowlisting before they fire. Managed via `~/.kopi/shell-hooks-allowlist.json` — prompted interactively the first time a hook wants to run.

### Disabling the web/browser/image-gen tools

To keep the model away from network or media tools entirely, open `kopi tools` and toggle per-platform. Takes effect on next session (`/reset`). See the Tools & Skills section above.

---

## Voice & Transcription

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

Provider priority (auto-detected):
1. **Local faster-whisper** — free, no API key: `pip install faster-whisper`
2. **Groq Whisper** — free tier: set `GROQ_API_KEY`
3. **OpenAI Whisper** — paid: set `VOICE_TOOLS_OPENAI_KEY`
4. **Mistral Voxtral** — set `MISTRAL_API_KEY`

Config:
```yaml
stt:
  enabled: true
  provider: local        # local, groq, openai, mistral
  local:
    model: base          # tiny, base, small, medium, large-v3
```

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS | None | Yes (default) |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral (Voxtral) | `MISTRAL_API_KEY` | Paid |
| NeuTTS (local) | None (`pip install neutts[all]` + `espeak-ng`) | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.

---

## Spawning Additional Kopi Instances

Run additional Kopi processes as fully independent subprocesses — separate sessions, tools, and environments.

### When to Use This vs delegate_task

| | `delegate_task` | Spawning `kopi` process |
|-|-----------------|--------------------------|
| Isolation | Separate conversation, shared process | Fully independent process |
| Duration | Minutes (bounded by parent loop) | Hours/days |
| Tool access | Subset of parent's tools | Full tool access |
| Interactive | No | Yes (PTY mode) |
| Use case | Quick parallel subtasks | Long autonomous missions |

### One-Shot Mode

```
terminal(command="kopi chat -q 'Research GRPO papers and write summary to ~/research/grpo.md'", timeout=300)

# Background for long tasks:
terminal(command="kopi chat -q 'Set up CI/CD for ~/myapp'", background=true)
```

### Interactive PTY Mode (via tmux)

Kopi uses prompt_toolkit, which requires a real terminal. Use tmux for interactive spawning:

```
# Start
terminal(command="tmux new-session -d -s agent1 -x 120 -y 40 'kopi'", timeout=10)

# Wait for startup, then send a message
terminal(command="sleep 8 && tmux send-keys -t agent1 'Build a FastAPI auth service' Enter", timeout=15)

# Read output
terminal(command="sleep 20 && tmux capture-pane -t agent1 -p", timeout=5)

# Send follow-up
terminal(command="tmux send-keys -t agent1 'Add rate limiting middleware' Enter", timeout=5)

# Exit
terminal(command="tmux send-keys -t agent1 '/exit' Enter && sleep 2 && tmux kill-session -t agent1", timeout=10)
```

### Multi-Agent Coordination

```
# Agent A: backend
terminal(command="tmux new-session -d -s backend -x 120 -y 40 'kopi -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t backend 'Build REST API for user management' Enter", timeout=15)

# Agent B: frontend
terminal(command="tmux new-session -d -s frontend -x 120 -y 40 'kopi -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t frontend 'Build React dashboard for user management' Enter", timeout=15)

# Check progress, relay context between them
terminal(command="tmux capture-pane -t backend -p | tail -30", timeout=5)
terminal(command="tmux send-keys -t frontend 'Here is the API schema from the backend agent: ...' Enter", timeout=5)
```

### Session Resume

```
# Resume most recent session
terminal(command="tmux new-session -d -s resumed 'kopi --continue'", timeout=10)

# Resume specific session
terminal(command="tmux new-session -d -s resumed 'kopi --resume 20260225_143052_a1b2c3'", timeout=10)
```

### Tips

- **Prefer `delegate_task` for quick subtasks** — less overhead than spawning a full process
- **Use `-w` (worktree mode)** when spawning agents that edit code — prevents git conflicts
- **Set timeouts** for one-shot mode — complex tasks can take 5-10 minutes
- **Use `kopi chat -q` for fire-and-forget** — no PTY needed
- **Use tmux for interactive sessions** — raw PTY mode has `\r` vs `\n` issues with prompt_toolkit
- **For scheduled tasks**, use the `cronjob` tool instead of spawning — handles delivery and retry

---

## Durable & Background Systems

Four systems run alongside the main conversation loop. Quick reference
here; full developer notes live in `AGENTS.md`, user-facing docs under
`website/docs/user-guide/features/`.

### Delegation (`delegate_task`)

Spawn a subagent with an isolated context + terminal session.

- **Single:** `delegate_task(goal, context)`.
- **Batch:** `delegate_task(tasks=[{goal, ...}, ...])` runs children in
  parallel, capped by `delegation.max_concurrent_children` (default 3).
- **Background:** `delegate_task(background=true)` returns a handle
  immediately and keeps the parent loop going; the child's result
  re-enters the conversation as a new turn when it finishes.
- **Roles:** `leaf` (default; cannot re-delegate) vs `orchestrator`
  (can spawn its own workers, bounded by `delegation.max_spawn_depth`).
- **Not durable.** A backgrounded child is still process-local — if the
  parent process exits, the child is lost. For work that must outlive
  the process, use `cronjob` or
  `terminal(background=True, notify_on_complete=True)`.

Config: `delegation.*` in `config.yaml`.

### Cron (scheduled jobs)

Durable scheduler — `cron/jobs.py` + `cron/scheduler.py`. Drive it via
the `cronjob` tool, the `kopi cron` CLI (`list`, `add`, `edit`,
`pause`, `resume`, `run`, `remove`), or the `/cron` slash command.

- **Schedules:** duration (`"30m"`, `"2h"`), "every" phrase
  (`"every monday 9am"`), 5-field cron (`"0 9 * * *"`), or ISO timestamp.
- **Per-job knobs:** `skills`, `model`/`provider` override, `script`
  (pre-run data collection; `no_agent=True` makes the script the whole
  job), `context_from` (chain job A's output into job B), `workdir`
  (run in a specific dir with its `AGENTS.md` / `CLAUDE.md` loaded),
  multi-platform delivery.
- **Invariants:** 3-minute hard interrupt per run, `.tick.lock` file
  prevents duplicate ticks across processes, cron sessions pass
  `skip_memory=True` by default, and cron deliveries are framed with a
  header/footer instead of being mirrored into the target gateway
  session (keeps role alternation intact).

User docs: https://kopi-agent.nousresearch.com/docs/user-guide/features/cron

### Curator (skill lifecycle)

Background maintenance for agent-created skills. Tracks usage, marks
idle skills stale, archives stale ones, keeps a pre-run tar.gz backup
so nothing is lost.

- **CLI:** `kopi curator <verb>` — `status`, `run`, `pause`, `resume`,
  `pin`, `unpin`, `archive`, `restore`, `prune`, `backup`, `rollback`.
- **Slash:** `/curator <subcommand>` mirrors the CLI.
- **Scope:** only touches skills with `created_by: "agent"` provenance.
  Bundled + hub-installed skills are off-limits. **Never deletes** —
  max destructive action is archive. Pinned skills are exempt from
  every auto-transition and every LLM review pass.
- **Cost:** the deterministic inactivity/prune sweep runs for free. The
  aux-model "consolidate overlapping skills into umbrellas" pass is
  **off by default** — opt in with `curator.consolidate: true` or
  `kopi curator run --consolidate`. Routine background curation costs
  zero tokens.
- **Telemetry:** sidecar at `~/.kopi/skills/.usage.json` holds
  per-skill `use_count`, `view_count`, `patch_count`,
  `last_activity_at`, `state`, `pinned`.

Config: `curator.*` (`enabled`, `interval_hours`, `min_idle_hours`,
`stale_after_days`, `archive_after_days`, `backup.*`).
User docs: https://kopi-agent.nousresearch.com/docs/user-guide/features/curator

### Kanban (multi-agent work queue)

Durable SQLite board for multi-profile / multi-worker collaboration.
Users drive it via `kopi kanban <verb>`; dispatcher-spawned workers
see a focused `kanban_*` toolset gated by `KOPI_KANBAN_TASK`, and
orchestrator profiles can opt into the broader `kanban` toolset. Normal
sessions still have zero `kanban_*` schema footprint unless configured.

- **CLI verbs (common):** `init`, `create`, `list` (alias `ls`),
  `show`, `assign`, `link`, `unlink`, `comment`, `complete`, `block`,
  `unblock`, `archive`, `tail`. Less common: `watch`, `stats`, `runs`,
  `log`, `dispatch`, `daemon`, `gc`.
- **Worker/orchestrator toolset:** `kanban_show`, `kanban_complete`,
  `kanban_block`, `kanban_heartbeat`, `kanban_comment`, `kanban_create`,
  `kanban_link`; profiles that explicitly enable the `kanban` toolset
  outside a dispatcher-spawned task also get `kanban_list` and
  `kanban_unblock` for board routing.
- **Dispatcher** runs inside the gateway by default
  (`kanban.dispatch_in_gateway: true`) — reclaims stale claims,
  promotes ready tasks, atomically claims, spawns assigned profiles.
  Auto-blocks a task after `failure_limit` consecutive spawn failures
  (default 2; configurable via `kanban.failure_limit` or per-task
  `max_retries`).
- **Isolation:** board is the hard boundary (workers get
  `KOPI_KANBAN_BOARD` pinned in env); tenant is a soft namespace
  within a board for workspace-path + memory-key isolation.

User docs: https://kopi-agent.nousresearch.com/docs/user-guide/features/kanban

---

## Surfaces & Other Capabilities

Beyond the CLI and gateway, a few things worth knowing about:

- **Desktop app** (`kopi desktop` / `kopi gui`) — native Electron app
  for macOS/Linux/Windows: streaming chat, session list, drag-and-drop +
  clipboard-paste files, Cmd+K palette, status-bar model picker,
  rebindable shortcuts, native notifications, live subagent watch-windows,
  VS Code Marketplace themes, and per-profile remote-gateway login (OAuth
  or username/password) so a thin local GUI can drive a heavy remote agent.
- **Web dashboard** (`kopi dashboard`) — full admin panel: configure
  every messaging channel, the MCP catalog, webhooks/hooks, memory, and a
  complete profile builder (model + skills + MCPs) from the browser, plus
  an embedded `kopi --tui` chat. Secured behind an OAuth/token gate.
- **OpenAI-compatible proxy** (`kopi proxy`) — exposes a
  `http://localhost:port` OpenAI API backed by whichever OAuth provider
  you're signed into (Claude Pro, ChatGPT Pro, SuperGrok). Point Codex
  CLI, Aider, Cline, Continue, or any script at it — no API key.
- **Automation Blueprints** — pick a named automation and Kopi asks for
  what it needs (no cron syntax). One definition renders as a dashboard
  form, a slash command, an agent conversation, and a docs-catalog entry.
- **`memory` tool batch operations** — pass an `operations` array of
  add/replace/remove edits applied atomically against the final character
  budget, so a single call can free space and add entries even when an add
  alone would overflow.
- **`session_search`** — FTS5-backed, no aux-LLM, effectively free. One
  tool, three modes inferred from which args are set: discovery (`query`),
  scroll (`session_id` + `around_message_id`), browse (no args).
- **xAI Grok via SuperGrok OAuth** — sign in with your xAI account (no API
  key); includes Cursor's `grok-composer-2.5-fast` coding model.

---

## Windows-Specific Quirks

Kopi runs natively on Windows (PowerShell, cmd, Windows Terminal, git-bash
mintty, VS Code integrated terminal). Most of it just works, but a handful
of differences between Win32 and POSIX have bitten us — document new ones
here as you hit them so the next person (or the next session) doesn't
rediscover them from scratch.

### Input / Keybindings

**Alt+Enter doesn't insert a newline** — Windows Terminal (and mintty) grab it
for fullscreen before prompt_toolkit sees it. Use **Ctrl+Enter** instead (the
CLI binds it to newline on Windows; raw Ctrl+J does the same, harmlessly).
To inspect how your terminal reports a keystroke, run
`python scripts/keystroke_diagnostic.py` from the repo root.

### Config / Files

**HTTP 400 "No models provided" on first run** — `config.yaml` was saved with
a UTF-8 BOM (Notepad does this). Re-save as UTF-8 without BOM;
`kopi config edit` writes correctly.

### `execute_code` / Sandbox

**WinError 10106** from the sandbox child process — it can't create an
`AF_INET` socket. Root cause is usually Kopi's env scrubber dropping
`SYSTEMROOT`/`WINDIR`/`COMSPEC` (Python's `socket` needs `SYSTEMROOT` to find
`mswsock.dll`), not a broken Winsock LSP. The `_WINDOWS_ESSENTIAL_ENV_VARS`
allowlist in `tools/code_execution_tool.py` covers it; if you still hit it,
echo `os.environ` inside an `execute_code` block to confirm `SYSTEMROOT` is set.

### Testing on Windows

`scripts/run_tests.sh` is POSIX-only (expects `.venv/bin/activate`); the
Kopi-installed `venv/Scripts/` has no pip/pytest (stripped for size).
Install pytest into a system Python and run directly with `-n 0`
(`pyproject.toml`'s `addopts` already sets `-n`):

```bash
"/c/Program Files/Python311/python" -m pip install --user pytest pytest-xdist pyyaml
export PYTHONPATH="$(pwd)"
"/c/Program Files/Python311/python" -m pytest tests/foo/test_bar.py -v --tb=short -n 0
```

(POSIX-only tests need skip guards — see the cross-platform guard list in the
Contributor section below.)

### Path / Filesystem

**Line endings.** Git may warn `LF will be replaced by CRLF`. Cosmetic — the
repo's `.gitattributes` normalizes. Don't let editors auto-convert committed
POSIX-newline files to CRLF.

**Forward slashes work almost everywhere.** `C:/Users/...` is accepted by
every Kopi tool and most Windows APIs. Prefer forward slashes in code
and logs — avoids shell-escaping backslashes in bash.

---

## Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `pip install faster-whisper` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `kopi tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `kopi doctor` — check config and dependencies
2. `kopi auth` — re-authenticate OAuth providers (or `kopi auth add <provider>`)
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for Copilot API. You must use the Copilot-specific OAuth device code flow via `kopi model` → GitHub Copilot.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process

### Skills not showing
1. `kopi skills list` — verify installed
2. `kopi skills config` — check platform enablement
3. Load explicitly: `/skill name` or `kopi -s name`

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.kopi/logs/gateway.log | tail -20
```

Common gateway problems:
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed kopi-gateway`

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows-specific issues** (`Alt+Enter` newline, WinError 10106, UTF-8 BOM config, test suite, line endings): see the dedicated **Windows-Specific Quirks** section above.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search) fail silently, the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure each auxiliary task's provider:
```bash
kopi config set auxiliary.vision.provider <your_provider>
kopi config set auxiliary.vision.model <model_name>
```

---

## Where to Find Things

| Looking for... | Location |
|----------------|----------|
| Config options | `kopi config edit` or [Configuration docs](https://kopi-agent.nousresearch.com/docs/user-guide/configuration) |
| Available tools | `kopi tools list` or [Tools reference](https://kopi-agent.nousresearch.com/docs/reference/tools-reference) |
| Slash commands | `/help` in session or [Slash commands reference](https://kopi-agent.nousresearch.com/docs/reference/slash-commands) |
| Skills catalog | `kopi skills browse` or [Skills catalog](https://kopi-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `kopi model` or [Providers guide](https://kopi-agent.nousresearch.com/docs/integrations/providers) |
| Platform setup | `kopi gateway setup` or [Messaging docs](https://kopi-agent.nousresearch.com/docs/user-guide/messaging/) |
| MCP servers | `kopi mcp list` or [MCP guide](https://kopi-agent.nousresearch.com/docs/user-guide/features/mcp) |
| Profiles | `kopi profile list` or [Profiles docs](https://kopi-agent.nousresearch.com/docs/user-guide/profiles) |
| Cron jobs | `kopi cron list` or [Cron docs](https://kopi-agent.nousresearch.com/docs/user-guide/features/cron) |
| Memory | `kopi memory status` or [Memory docs](https://kopi-agent.nousresearch.com/docs/user-guide/features/memory) |
| Env variables | `kopi config env-path` or [Env vars reference](https://kopi-agent.nousresearch.com/docs/reference/environment-variables) |
| CLI commands | `kopi --help` or [CLI reference](https://kopi-agent.nousresearch.com/docs/reference/cli-commands) |
| Gateway logs | `~/.kopi/logs/gateway.log` |
| Session files | `kopi sessions browse` (reads state.db) |
| Source code | `~/.kopi/kopi-agent/` |

---

## Contributor Quick Reference

For occasional contributors and PR authors. Full developer docs: https://kopi-agent.nousresearch.com/docs/developer-guide/

### Project Layout

```
kopi-agent/
├── run_agent.py          # AIAgent — core conversation loop
├── model_tools.py        # Tool discovery and dispatch
├── toolsets.py           # Toolset definitions
├── cli.py                # Interactive CLI (KopiCLI)
├── kopi_state.py       # SQLite session store
├── agent/                # Prompt builder, context compression, memory, model routing, credential pooling, skill dispatch
├── kopi_cli/           # CLI subcommands, config, setup, commands
│   ├── commands.py       # Slash command registry (CommandDef)
│   ├── config.py         # DEFAULT_CONFIG, env var definitions
│   └── main.py           # CLI entry point and argparse
├── tools/                # One file per tool
│   └── registry.py       # Central tool registry
├── gateway/              # Messaging gateway
│   └── platforms/        # Platform adapters (telegram, discord, etc.)
├── cron/                 # Job scheduler
├── tests/                # Extensive pytest suite (run via scripts/run_tests.sh)
└── website/              # Docusaurus docs site
```

Config: `~/.kopi/config.yaml` (settings), `~/.kopi/.env` (API keys) — both under `$KOPI_HOME` when it is set.

### Adding a Tool

Two files. Auto-discovery imports any `tools/*.py` with a top-level
`registry.register()` call, but a tool is only *exposed* to an agent once
its name appears in a toolset.

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(
        param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Wire it into a toolset in `toolsets.py`** — add the name to
`_KOPI_CORE_TOOLS` (every platform) or to a specific toolset.

All handlers must return JSON strings. Use `get_kopi_home()` for paths,
never hardcode `~/.kopi`. For custom/local-only tools, write a plugin in
`~/.kopi/plugins/` instead of editing core — see the developer docs.

### Adding a Slash Command

1. Add `CommandDef` to `COMMAND_REGISTRY` in `kopi_cli/commands.py`
2. Add handler in `cli.py` → `process_command()`
3. (Optional) Add gateway handler in `gateway/run.py`

All consumers (help text, autocomplete, Telegram menu, Slack mapping) derive from the central registry automatically.

### Agent Loop (High Level)

```
run_conversation():
  1. Build system prompt
  2. Loop while iterations < max:
     a. Call LLM (OpenAI-format messages + tool schemas)
     b. If tool_calls → dispatch each via handle_function_call() → append results → continue
     c. If text response → return
  3. Context compression triggers automatically near token limit
```

### Testing

Use the canonical runner — it enforces CI-parity (hermetic env, unset
credentials, TZ=UTC, xdist workers, per-test subprocess isolation):

```bash
scripts/run_tests.sh                          # full suite
scripts/run_tests.sh tests/tools/             # one directory
scripts/run_tests.sh tests/tools/test_x.py    # one file
scripts/run_tests.sh -v --tb=long             # pass-through pytest flags
```

- Tests auto-redirect `KOPI_HOME` to temp dirs — never touch real `~/.kopi/`.
- The script probes `.venv`, then `venv`, then the shared worktree venv.
- **Windows:** the wrapper is POSIX-only; see the **Windows-Specific Quirks**
  section above for the direct-pytest workaround.

**Cross-platform test guards:** tests using POSIX-only syscalls need a skip marker. Common ones already in the codebase:
- Symlink creation → `@pytest.mark.skipif(sys.platform == "win32", reason="Symlinks require elevated privileges on Windows")` (see `tests/cron/test_cron_script.py`)
- POSIX file modes (0o600, etc.) → `@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX mode bits not enforced on Windows")` (see `tests/kopi_cli/test_auth_toctou_file_modes.py`)
- `signal.SIGALRM` → Unix-only (see `tests/conftest.py::_enforce_test_timeout`)
- Live Winsock / Windows-specific regression tests → `@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific regression")`

**Monkeypatching `sys.platform` is not enough** when the code under test also calls `platform.system()` / `platform.release()` / `platform.mac_ver()`. Those functions re-read the real OS independently, so a test that sets `sys.platform = "linux"` on a Windows runner will still see `platform.system() == "Windows"` and route through the Windows branch. Patch all three together:

```python
monkeypatch.setattr(sys, "platform", "linux")
monkeypatch.setattr(platform, "system", lambda: "Linux")
monkeypatch.setattr(platform, "release", lambda: "6.8.0-generic")
```

See `tests/agent/test_prompt_builder.py::TestEnvironmentHints` for a worked example.

### System prompt's execution-environment block

Factual host/backend guidance (OS, `$HOME`, cwd, terminal backend, shell)
is emitted by `agent/prompt_builder.py::build_environment_hints()`. The key
invariant for prompt authors: with a **remote** terminal backend
(`docker, singularity, modal, daytona, ssh, managed_modal`), host info is
suppressed and *every* file tool runs inside the backend container — the
prompt must never describe the host the agent can't touch.

### Commit Conventions

```
type: concise subject line

Optional body.
```

Types: `fix:`, `feat:`, `refactor:`, `docs:`, `chore:`

### Key Rules

- **Never break prompt caching** — don't change context, tools, or system prompt mid-conversation
- **Message role alternation** — never two assistant or two user messages in a row
- Use `get_kopi_home()` from `kopi_constants` for all paths (profile-safe)
- Config values go in `config.yaml`, secrets go in `.env`
- New tools need a `check_fn` so they only appear when requirements are met
