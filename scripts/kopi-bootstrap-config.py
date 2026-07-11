#!/usr/bin/env python3
"""
KOPI AI AGENT — Post-install bootstrap.
Runs `kopi setup` then auto-configures KOPI defaults:
  - MCP v1 stdio servers (filesystem, time, github, obsidian/mcpvault)
  - KOPI MCP SSE Gateway
  - KOPI Proxy as custom provider
  - Default model: kopi-o
"""
import os, subprocess, sys
from pathlib import Path

KOPI_HOME = Path(os.environ.get("KOPI_HOME", Path.home() / ".kopi"))
CONFIG_PATH = KOPI_HOME / "config.yaml"

# Obsidian vault (mcpvault) — a KOPI-managed vault so Obsidian tools work
# out of the box with no desktop app or plugin. Overridable via env for
# users who already have a vault. Created at bootstrap if missing; it also
# doubles as the sink target for agent memory/skill export.
OBSIDIAN_VAULT = Path(os.environ.get("KOPI_OBSIDIAN_VAULT", Path.home() / "kopi-vault"))

def run_kopi(*args: str) -> None:
    """Run a `kopi` CLI command."""
    subprocess.run([sys.executable, "-m", "kopi_cli", *args], check=False)

def main() -> None:
    print("☕ KOPI AI AGENT — Bootstrap defaults")
    print()

    if not CONFIG_PATH.exists():
        print("⚠ No config yet. Run `kopi setup` first, or skip config bootstrap.")
        return

    # 1. Add MCP v1 stdio servers
    mcp_servers = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", str(Path.home())],
        },
        "time": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-time"],
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        },
    }

    # Obsidian vault access via mcpvault — filesystem-direct, no desktop app
    # or plugin required (works headless on a VPS). Ensure the vault dir
    # exists so the server has a valid target on first launch.
    try:
        OBSIDIAN_VAULT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"⚠ Could not create Obsidian vault at {OBSIDIAN_VAULT}: {exc}")
    mcp_servers["obsidian"] = {
        "command": "npx",
        "args": ["-y", "@bitbonsai/mcpvault@latest", str(OBSIDIAN_VAULT)],
    }

    # 2. Add MCP v2 SSE: KOPI MCP Gateway
    mcp_servers["kopi-mcp"] = {
        "url": "https://kopiaiagent.com/agg-mcp/sse",
        "auth": "header",
    }

    # 3. Write MCP servers to config
    import yaml
    config = yaml.safe_load(CONFIG_PATH.read_text()) or {}

    config.setdefault("mcp_servers", {}).update(mcp_servers)

    # 4. Add KOPI Proxy as custom provider
    custom_providers = config.get("custom_providers", [])
    kopi_proxy = {
        "name": "KOPI Proxy",
        "base_url": "https://kopiaiagent.com/kp/v1",
        "api_key_env": "KOPI_PROXY_API_KEY",
        "models": {
            "kopi-o": {"max_input_tokens": 128000, "max_output_tokens": 4096},
            "kopi-o-flash": {"max_input_tokens": 128000, "max_output_tokens": 4096},
            "kopi-flash": {"max_input_tokens": 128000, "max_output_tokens": 4096},
        },
    }
    if not any(cp.get("base_url") == kopi_proxy["base_url"] for cp in custom_providers):
        custom_providers.append(kopi_proxy)
    config["custom_providers"] = custom_providers

    # 5. Set default model
    config.setdefault("model", "kopi-o")

    CONFIG_PATH.write_text(yaml.safe_dump(config, default_flow_style=False, allow_unicode=True))
    print("✓ MCP servers configured: filesystem, time, github, kopi-mcp, obsidian")
    print(f"✓ Obsidian vault (mcpvault) ready at: {OBSIDIAN_VAULT}")
    print("✓ KOPI Proxy added as custom provider (kopi-o / kopi-o-flash / kopi-flash)")
    print()
    print("To set your KOPI Proxy API key:")
    print("  export KOPI_PROXY_API_KEY='your-key-here'")
    print("Then run:")
    print("  kopi system restart")

if __name__ == "__main__":
    main()
