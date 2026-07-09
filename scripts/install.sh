#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Kopi Ai Agent — 一键安装脚本 (Linux + macOS)
# By Kopi Ai Agent Pte Ltd (Singapore)
#
# Usage:
#   curl -fsSL https://kopiaiagent.com/install.sh | bash
#   curl -fsSL https://kopiaiagent.com/install.sh | TG_TOKEN=xxx:yyy bash
#   curl -fsSL https://kopiaiagent.com/install.sh | KOPI_API_KEY=kopi_xxx TG_TOKEN=xxx:yyy bash
#
# Environment variables:
#   TG_TOKEN       - Telegram Bot Token (from @BotFather)
#   KOPI_API_KEY   - Existing API key (skip auto-provision if set)
#   KOPI_MODEL     - Default model (default: kopi-o)
#
# Supported platforms:
#   - Linux (Ubuntu/Debian/CentOS/RHEL) — requires root
#   - macOS (Intel & Apple Silicon)      — normal user, uses brew + launchd
#
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Config ─────────────────────────────────────────────────────────────
KOPI_HOME="${KOPI_HOME:-$HOME/.kopi}"
KOPI_PROXY_BASE="https://kopiaiagent.com/v1"
KOPI_PROXY_FALLBACK="https://kopi.readinghero.xyz/v1"
AUTO_PROVISION_URL="${KOPI_PROXY_BASE}/auto-provision/ready"
PROVISION_URL="${KOPI_PROXY_BASE}/provision"
KOPI_MODEL="${KOPI_MODEL:-kopi-o}"
KOPI_INSTALL_URL="https://raw.githubusercontent.com/kopiagent/kopi-ai-agent/main/scripts/install.sh"

# ── Platform detection ─────────────────────────────────────────────────
OS="$(uname -s)"
IS_MACOS=false
IS_LINUX=false

if [[ "$OS" == "Darwin" ]]; then
    IS_MACOS=true
elif [[ "$OS" == "Linux" ]]; then
    IS_LINUX=true
fi

# ── Helpers ────────────────────────────────────────────────────────────
info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# Cross-platform sed -i (macOS requires backup extension with BSD sed)
sedi() {
    if [[ "$IS_MACOS" == true ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

banner() {
    echo -e "${BOLD}${CYAN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════╗
    ║                                               ║
    ║   ██╗  ██╗ ██████╗ ██████╗ ██╗               ║
    ║   ██║ ██╔╝██╔═══██╗██╔══██╗██║               ║
    ║   █████╔╝ ██║   ██║██████╔╝██║               ║
    ║   ██╔═██╗ ██║   ██║██╔═══╝ ██║               ║
    ║   ██║  ██╗╚██████╔╝██║     ██║██╗            ║
    ║   ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝            ║
    ║                                               ║
    ║   Ai Agent — Powered by Kopi                ║
    ║   by Kopi Ai Agent Pte Ltd                      ║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "${DIM}  一键安装，一步到位${NC}"
    if [[ "$IS_MACOS" == true ]]; then
        echo -e "${DIM}  检测到 macOS ($(uname -m))${NC}"
    else
        echo -e "${DIM}  检测到 Linux${NC}"
    fi
    echo ""
}

# ── Pre-flight checks ─────────────────────────────────────────────────
preflight() {
    # Platform check
    if [[ "$IS_MACOS" == false && "$IS_LINUX" == false ]]; then
        fail "不支持的系统: $OS。仅支持 Linux 和 macOS。"
    fi

    # Linux requires root
    if [[ "$IS_LINUX" == true ]] && [[ $EUID -ne 0 ]]; then
        fail "Linux 上请使用 root 运行: sudo bash 或 curl ... | sudo bash"
    fi

    # macOS: no root needed
    if [[ "$IS_MACOS" == true ]]; then
        info "macOS 模式 — 无需 root 权限"
    fi

    # Need curl
    if ! command -v curl &>/dev/null; then
        info "安装 curl..."
        if [[ "$IS_MACOS" == true ]]; then
            if command -v brew &>/dev/null; then
                brew install curl
            else
                fail "请先安装 Homebrew: https://brew.sh"
            fi
        else
            apt-get update -qq && apt-get install -y -qq curl 2>/dev/null || \
            yum install -y -q curl 2>/dev/null || \
            fail "无法安装 curl，请手动安装后重试"
        fi
    fi

    # macOS needs Homebrew (for python3 at minimum)
    if [[ "$IS_MACOS" == true ]]; then
        if ! command -v brew &>/dev/null; then
            warn "未检测到 Homebrew"
            echo "  Homebrew 安装 Python3 等依赖。是否安装？[Y/n]"
            echo -n "  > "
            local answer
            read -r answer
            if [[ "${answer,,}" == "n" ]]; then
                # Check if python3 exists without brew
                if ! command -v python3 &>/dev/null; then
                    fail "需要 Python3，请先安装 Homebrew 或 Python3"
                fi
            else
                info "安装 Homebrew（可能需要输入密码）..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                # Add brew to PATH for this session
                if [[ -f /opt/homebrew/bin/brew ]]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                elif [[ -f /usr/local/bin/brew ]]; then
                    eval "$(/usr/local/bin/brew shellenv)"
                fi
            fi
        fi
    fi

    # Python3 is required
    if ! command -v python3 &>/dev/null; then
        info "安装 Python3..."
        if [[ "$IS_MACOS" == true ]]; then
            brew install python3
        else
            apt-get update -qq && apt-get install -y -qq python3 2>/dev/null || \
            yum install -y -q python3 2>/dev/null || \
            fail "无法安装 Python3，请手动安装后重试"
        fi
    fi

    ok "系统检查通过 ($OS)"
}

# ── Step 1: Install Kopi Ai Agent ──────────────────────────────────────
install_kopi() {
    step "安装 Kopi Ai Agent 引擎"

    # Download and run official installer with --skip-setup (non-interactive)
    info "从 GitHub 下载 Kopi Ai Agent 安装程序..."

    local install_args="--skip-setup --skip-browser"

    # If already installed, still run to update
    if command -v kopi &>/dev/null; then
        info "检测到已有 Kopi Ai Agent 安装，更新中..."
    fi

    curl -fsSL "$KOPI_INSTALL_URL" | bash -s -- $install_args

    # Verify installation — binary is `kopi`, not `hermes`
    local kopi_cmd=""
    if command -v kopi &>/dev/null; then
        kopi_cmd="kopi"
    elif [[ -x /usr/local/bin/kopi ]]; then
        kopi_cmd="/usr/local/bin/kopi"
    elif [[ -x "$HOME/.local/bin/kopi" ]]; then
        kopi_cmd="$HOME/.local/bin/kopi"
    elif [[ -x "$KOPI_HOME/kopi-ai-agent/venv/bin/kopi" ]]; then
        kopi_cmd="$KOPI_HOME/kopi-ai-agent/venv/bin/kopi"
    else
        fail "Kopi Ai Agent 安装失败 — 命令未找到"
    fi

    local raw_version=$($kopi_cmd --version 2>/dev/null || echo "unknown")
    local version=$(echo "$raw_version" | sed 's/[Hh]ermes[[:space:]]*[Aa]gent[[:space:]]*//g; s/[Kk]opi[[:space:]]*[Aa][Ii][[:space:]]*[Aa]gent[[:space:]]*//g; s/[Hh]ermes//g' | xargs)
    [[ -z "$version" ]] && version="installed"
    ok "Kopi Ai Agent 已安装: v$version"
    KOPI_CMD="$kopi_cmd"
}

# ── Step 2: Auto-Provision API Key ────────────────────────────────────
provision_api_key() {
    step "开通 KOPI Proxy API 账号"

    # Use existing key if provided
    if [[ -n "${KOPI_API_KEY:-}" ]]; then
        ok "使用提供的 API Key"
        return
    fi

    # Check if key already exists
    # Linux: /etc/kopi-agent/credentials, macOS: ~/.kopi/kopi-credentials
    local cred_file
    if [[ "$IS_MACOS" == true ]]; then
        cred_file="$KOPI_HOME/kopi-credentials"
    else
        cred_file="/etc/kopi-agent/credentials"
    fi

    if [[ -f "$cred_file" ]]; then
        local existing_key
        existing_key=$(cat "$cred_file" 2>/dev/null | tr -d '[:space:]')
        # Accept both old kp-* and new kopi_ prefix
        if [[ -n "$existing_key" ]] && [[ "$existing_key" == kp-* || "$existing_key" == kopi-* ]]; then
            ok "已有 API Key，跳过开通"
            KOPI_API_KEY="$existing_key"
            return
        fi
    fi

    echo -n "  🔑 正在开通账号..."

    # Auto-provision returns API key directly in one call
    local auto_resp
    auto_resp=$(curl -s -X POST "$AUTO_PROVISION_URL" \
        -H "Content-Type: application/json" \
        --connect-timeout 10 \
        --max-time 30 2>/dev/null || echo "")

    KOPI_API_KEY=$(echo "$auto_resp" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('api_key', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [[ -z "$KOPI_API_KEY" ]]; then
        echo -e "${RED}失败${NC}"
        echo ""
        echo "  无法自动获取 API Key。请手动提供:"
        echo "    curl -fsSL https://kopiaiagent.com/install.sh | KOPI_API_KEY=kopi-xxx bash"
        fail "获取 API Key 失败"
    fi
    echo -e "${GREEN}✓${NC}"

    # Save credentials securely
    mkdir -p "$(dirname "$cred_file")"
    echo "$KOPI_API_KEY" > "$cred_file"
    chmod 600 "$cred_file"
    ok "API Key 已安全存储到 $cred_file"
}

# ── Step 3: Write KOPI Proxy Config ──────────────────────────────────
write_config() {
    step "写入 KOPI Proxy 配置"

    mkdir -p "$KOPI_HOME"

    # Backup existing config if present
    if [[ -f "$KOPI_HOME/config.yaml" ]]; then
        local backup="$KOPI_HOME/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$KOPI_HOME/config.yaml" "$backup"
        info "已备份旧配置到 $backup"
    fi

    # Write config.yaml
    cat > "$KOPI_HOME/config.yaml" << CONFIG
# ═══════════════════════════════════════════════════════════════════════
# Kopi Ai Agent 配置文件
# By Kopi Ai Agent Pte Ltd
# Auto-generated at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Platform: $OS
# ═══════════════════════════════════════════════════════════════════════

# ── 大模型配置 (KOPI Proxy) ────────────────────────────────────────────
model:
  default: ${KOPI_MODEL}
  provider: kopi-proxy
  base_url: ${KOPI_PROXY_BASE}
  api_key: ${KOPI_API_KEY}
  context_length: 256000

# ── Agent 配置 ─────────────────────────────────────────────────────────
agent:
  max_turns: 90
  gateway_timeout: 1800
  restart_drain_timeout: 180
  reasoning_effort: medium

# ── 终端配置 ───────────────────────────────────────────────────────────
terminal:
  timeout: 180

# ── 显示配置 ───────────────────────────────────────────────────────────
display:
  show_cost: false

# ── 内存配置 ───────────────────────────────────────────────────────────
memory:
  memory_enabled: true
  user_profile_enabled: true

# ── 安全配置 ───────────────────────────────────────────────────────────
approvals:
  mode: smart

# ── 压缩配置 ───────────────────────────────────────────────────────────
compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
CONFIG

    chmod 600 "$KOPI_HOME/config.yaml"
    ok "配置文件已写入: $KOPI_HOME/config.yaml"

    # Write .env file
    local env_file="$KOPI_HOME/.env"
    if [[ ! -f "$env_file" ]]; then
        cat > "$env_file" << ENV
# Kopi Ai Agent Environment Variables
TZ=Asia/Singapore
ENV
    fi

    # Add Telegram token to .env if provided
    if [[ -n "${TG_TOKEN:-}" ]]; then
        # Remove existing TELEGRAM_BOT_TOKEN if any
        if [[ -f "$env_file" ]]; then
            sedi '/^TELEGRAM_BOT_TOKEN=/d' "$env_file"
        fi
        echo "TELEGRAM_BOT_TOKEN=${TG_TOKEN}" >> "$env_file"
    fi

    chmod 600 "$env_file"
    ok "环境变量已写入: $env_file"
}

# ── Step 4: Configure Telegram Gateway ────────────────────────────────
configure_telegram() {
    # Skip if no token
    if [[ -z "${TG_TOKEN:-}" ]]; then
        info "未提供 Telegram Bot Token，跳过 Gateway 配置"
        info "稍后配置: kopi config set telegram_bot_token 'YOUR_TOKEN'"
        return
    fi

    step "配置 Telegram Gateway"

    # Validate token format (basic check)
    if [[ ! "$TG_TOKEN" =~ ^[0-9]+:.+ ]]; then
        warn "Telegram Bot Token 格式可能不正确，继续配置..."
    fi

    # Verify token with Telegram API
    echo -n "  🤖 验证 Bot Token..."
    local bot_info
    bot_info=$(curl -s "https://api.telegram.org/bot${TG_TOKEN}/getMe" 2>/dev/null || echo "")
    local bot_ok
    bot_ok=$(echo "$bot_info" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('ok' if d.get('ok') else 'fail')
except:
    print('fail')
" 2>/dev/null || echo "fail")

    if [[ "$bot_ok" == "ok" ]]; then
        local bot_name
        bot_name=$(echo "$bot_info" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['result'].get('username', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✓${NC} (@${bot_name})"
    else
        echo -e "${YELLOW}⚠${NC} (无法验证，继续配置)"
    fi

    # Add telegram config to config.yaml (append safely)
    if ! grep -q "^telegram:" "$KOPI_HOME/config.yaml" 2>/dev/null; then
        cat >> "$KOPI_HOME/config.yaml" << TGCONF

# ── Telegram 配置 ──────────────────────────────────────────────────────
telegram:
  reactions: false
TGCONF
    fi

    ok "Telegram 配置完成"
}

# ── Step 5: Install Gateway Service ───────────────────────────────────
install_gateway() {
    # Skip if no Telegram token
    if [[ -z "${TG_TOKEN:-}" ]]; then
        return
    fi

    step "安装 Gateway 服务"

    # Try built-in gateway install first
    if [[ -n "${KOPI_CMD:-}" ]] && $KOPI_CMD gateway install 2>/dev/null; then
        ok "Gateway 服务已安装"

        # Start the gateway
        if $KOPI_CMD gateway start 2>/dev/null; then
            ok "Gateway 已启动"
        else
            warn "Gateway 启动失败，请手动运行: kopi gateway start"
        fi
    else
        if [[ "$IS_MACOS" == true ]]; then
            install_gateway_launchd
        else
            install_gateway_systemd
        fi
    fi
}

# Linux: systemd service
install_gateway_systemd() {
    info "使用 systemd 创建 Gateway 服务..."

    local kopi_bin="${KOPI_CMD:-/usr/local/bin/kopi}"
    local install_dir="$KOPI_HOME/kopi-ai-agent"
    local venv_dir="$install_dir/venv"

    # Find the correct python path
    local python_path=""
    if [[ -x "$venv_dir/bin/python3" ]]; then
        python_path="$venv_dir/bin/python3"
    elif [[ -x "$install_dir/.venv/bin/python3" ]]; then
        python_path="$install_dir/.venv/bin/python3"
    else
        python_path="$(which python3)"
    fi

    cat > /etc/systemd/system/kopi-gateway.service << SERVICE
[Unit]
Description=Kopi Ai Agent Gateway
After=network.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=${install_dir}
Environment=PATH=${venv_dir}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EnvironmentFile=${KOPI_HOME}/.env
ExecStart=${python_path} -m kopi_cli.main gateway run --replace
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable kopi-gateway 2>/dev/null || true
    systemctl start kopi-gateway 2>/dev/null || warn "Gateway 启动失败"

    ok "Gateway 服务已安装 (systemd)"
    info "查看状态: systemctl status kopi-gateway"
    info "查看日志: journalctl -u kopi-gateway -f"
}

# macOS: launchd service
install_gateway_launchd() {
    info "使用 launchd 创建 Gateway 服务..."

    local plist_dir="$HOME/Library/LaunchAgents"
    mkdir -p "$plist_dir"

    local plist_file="$plist_dir/com.kopi.agent.gateway.plist"
    local install_dir="$KOPI_HOME/kopi-ai-agent"
    local venv_dir="$install_dir/venv"
    local log_dir="$KOPI_HOME/logs"
    mkdir -p "$log_dir"

    # Find the correct python path
    local python_path=""
    if [[ -x "$venv_dir/bin/python3" ]]; then
        python_path="$venv_dir/bin/python3"
    elif [[ -x "$install_dir/.venv/bin/python3" ]]; then
        python_path="$install_dir/.venv/bin/python3"
    else
        python_path="$(which python3)"
    fi

    # Unload if already exists
    launchctl unload "$plist_file" 2>/dev/null || true

    cat > "$plist_file" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kopi.agent.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>${python_path}</string>
        <string>-m</string>
        <string>kopi_cli.main</string>
        <string>gateway</string>
        <string>run</string>
        <string>--replace</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${install_dir}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${venv_dir}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${log_dir}/gateway-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${log_dir}/gateway-stderr.log</string>
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
PLIST

    # Load the service
    launchctl load "$plist_file" 2>/dev/null || warn "Gateway 启动失败"

    ok "Gateway 服务已安装 (launchd)"
    info "查看状态: launchctl list com.kopi.agent.gateway"
    info "查看日志: tail -f $log_dir/gateway-stdout.log"
    info "停止服务: launchctl unload $plist_file"
    info "启动服务: launchctl load $plist_file"
}

# ── Step 6: Install Skills ────────────────────────���───────────────────
install_skills() {
    step "安装预置技能"

    local skills_dir="$KOPI_HOME/skills"
    mkdir -p "$skills_dir"

    # Copy bundled skills from the Kopi install if they exist
    local kopi_lib="$KOPI_HOME/kopi-ai-agent"
    if [[ -d "$kopi_lib/skills" ]]; then
        local count=0
        for skill_dir in "$kopi_lib/skills/"*/; do
            local skill_name
            skill_name=$(basename "$skill_dir")
            if [[ ! -d "$skills_dir/$skill_name" ]]; then
                cp -r "$skill_dir" "$skills_dir/$skill_name" 2>/dev/null || true
                ((count++)) || true
            fi
        done
        if [[ $count -gt 0 ]]; then
            ok "已安装 $count 个内置技能"
        fi
    fi

    # Copy optional skills
    if [[ -d "$kopi_lib/optional-skills" ]]; then
        for skill_dir in "$kopi_lib/optional-skills/"*/; do
            local skill_name
            skill_name=$(basename "$skill_dir")
            if [[ ! -d "$skills_dir/$skill_name" ]]; then
                cp -r "$skill_dir" "$skills_dir/$skill_name" 2>/dev/null || true
            fi
        done
    fi

    local total
    total=$(find "$skills_dir" -name "SKILL.md" 2>/dev/null | wc -l)
    ok "共 $total 个技能可用"
}

# ── Completion ─────────────────────────────────────────────────────────
show_completion() {
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  ✓ Kopi Ai Agent 安装完成!${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}快速开始:${NC}"
    echo -e "    kopi                # 交互式聊天"
    echo -e "    kopi gateway        # 启动消息网关"
    echo -e "    kopi doctor         # 诊断问题"
    echo ""
    echo -e "  ${BOLD}Gateway 管理:${NC}"
    if [[ "$IS_MACOS" == true ]]; then
        echo -e "    launchctl load ~/Library/LaunchAgents/com.kopi.agent.gateway.plist    # 启动"
        echo -e "    launchctl unload ~/Library/LaunchAgents/com.kopi.agent.gateway.plist  # 停止"
        echo -e "    launchctl list com.kopi.agent.gateway                                 # 状态"
        echo -e "    tail -f ~/.kopi/logs/gateway-stdout.log                          # 日志"
    else
        echo -e "    systemctl start kopi-gateway    # 启动"
        echo -e "    systemctl stop kopi-gateway     # 停止"
        echo -e "    systemctl status kopi-gateway   # 状态"
        echo -e "    journalctl -u kopi-gateway -f   # 日志"
    fi
    echo ""
    echo -e "  ${BOLD}配置文件:${NC}"
    echo -e "    ~/.kopi/config.yaml"
    echo -e "    ~/.kopi/.env"
    echo ""

    if [[ -n "${TG_TOKEN:-}" ]]; then
        echo -e "  ${BOLD}Telegram Bot:${NC}"
        echo -e "    已配置完成，在 Telegram 中向你的 Bot 发送消息即可使用!"
        echo ""
    fi

    echo -e "  ${DIM}API Key: ${KOPI_API_KEY:0:12}...${NC}"
    echo -e "  ${DIM}文档: https://kopiaiagent.com/docs${NC}"
    echo -e "  ${DIM}支持: support@kopiaiagent.com${NC}"
    echo ""
    echo -e "${BOLD}  Built with ❤️ by Kopi Ai Agent Pte Ltd${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

main() {
    banner
    preflight
    install_kopi
    provision_api_key
    write_config
    configure_telegram
    install_gateway
    install_skills
    show_completion
}

main "$@"
