# Kopi CLI Reference

Live sources when anything looks stale: `kopi --help`, `kopi <command> --help`,
https://kopi-ai-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
kopi [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
kopi chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
kopi setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
kopi model                Interactive model/provider picker
kopi fallback [add|remove|list]  Fallback provider chain
kopi config [show|edit|get|set|unset|path|env-path|check|migrate]
kopi login / logout       OAuth sign-in / clear stored auth
kopi doctor [--fix]       Check dependencies and config
kopi status [--all]       Component status
```

### Tools & Skills

```
kopi tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

kopi skills list|browse|search QUERY|inspect ID
kopi skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
kopi skills config        Enable/disable skills per platform
kopi skills check|update|uninstall|publish PATH
kopi skills tap add REPO  Add a GitHub repo as a skill source
kopi bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
kopi mcp add NAME (--url or --command) | remove | list | test NAME
kopi mcp catalog | install NAME     Curated catalog install
kopi mcp configure NAME             Toggle tool selection
kopi mcp serve                      Run Kopi as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
kopi gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `kopi photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://kopi-ai-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
kopi sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
kopi cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
kopi webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
kopi profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
kopi profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
kopi auth                 Interactive credential manager
kopi auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
kopi auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
kopi desktop / gui        Native desktop app
kopi dashboard            Web admin panel + embedded chat (--stop / --status)
kopi proxy                OpenAI-compatible local proxy backed by an OAuth provider
kopi portal               Quick setup / sign in via Nous Portal
kopi kanban <verb>        Multi-agent work-queue board
kopi project              Named multi-folder workspaces
kopi skin list|use|set    Switch/tweak skins (see references/themes.md)
kopi pets <verb>          Pet mascots (see references/petdex.md)
kopi memory setup|status|off|reset   Memory provider
kopi secrets bitwarden|onepassword   External secret stores
kopi moa                  Mixture-of-Agents slots
kopi hooks / security / backup / import / checkpoints / console
kopi logs [-f] [errors]   View agent/error logs
kopi send                 One-off message through a gateway platform
kopi pairing / plugins / insights / journey / computer-use
kopi acp                  ACP server (IDE integration)
kopi completion bash|zsh|fish
kopi update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `kopi photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `kopi config edit` · [Configuration docs](https://kopi-ai-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `kopi tools list` · [Tools reference](https://kopi-ai-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `kopi skills browse` · [Skills catalog](https://kopi-ai-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `kopi model` · [Providers guide](https://kopi-ai-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `kopi config env-path` · [Env vars reference](https://kopi-ai-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.kopi/logs/gateway.log` (or `kopi logs`) |
| Sessions | `kopi sessions browse` (reads state.db) |
