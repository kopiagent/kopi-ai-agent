# Kopi CLI Reference

Full command surface. `kopi --help` / `kopi <command> --help` and
https://kopi-ai-agent.nousresearch.com/docs/reference/cli-commands are the
live sources if anything here looks stale.

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
(`kopi mcp install <name>`): `skill_view(name="kopi-ai-agent", file_path="references/native-mcp.md")`.

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

Platform docs: https://kopi-ai-agent.nousresearch.com/docs/user-guide/messaging/

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
patterns: `skill_view(name="kopi-ai-agent", file_path="references/webhooks.md")`.

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

## Where to Find Things

| Looking for... | Location |
|----------------|----------|
| Config options | `kopi config edit` or [Configuration docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/configuration) |
| Available tools | `kopi tools list` or [Tools reference](https://kopi-ai-agent.nousresearch.com/docs/reference/tools-reference) |
| Slash commands | `/help` in session or [Slash commands reference](https://kopi-ai-agent.nousresearch.com/docs/reference/slash-commands) |
| Skills catalog | `kopi skills browse` or [Skills catalog](https://kopi-ai-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `kopi model` or [Providers guide](https://kopi-ai-agent.nousresearch.com/docs/integrations/providers) |
| Platform setup | `kopi gateway setup` or [Messaging docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/messaging/) |
| MCP servers | `kopi mcp list` or [MCP guide](https://kopi-ai-agent.nousresearch.com/docs/user-guide/features/mcp) |
| Profiles | `kopi profile list` or [Profiles docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/profiles) |
| Cron jobs | `kopi cron list` or [Cron docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/features/cron) |
| Memory | `kopi memory status` or [Memory docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/features/memory) |
| Env variables | `kopi config env-path` or [Env vars reference](https://kopi-ai-agent.nousresearch.com/docs/reference/environment-variables) |
| CLI commands | `kopi --help` or [CLI reference](https://kopi-ai-agent.nousresearch.com/docs/reference/cli-commands) |
| Gateway logs | `~/.kopi/logs/gateway.log` |
| Session files | `kopi sessions browse` (reads state.db) |
| Source code | `~/.kopi/kopi-ai-agent/` |
