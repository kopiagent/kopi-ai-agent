#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Kopi Ai Agent — 一键安装脚本 (Linux + macOS)
# By Kopi Ai Agent Pte Ltd (Singapore)
#
# Usage:
#   curl -fsSL https://kopiaiagent.com/install.sh | bash
#   curl -fsSL https://kopiaiagent.com/install.sh | TG_TOKEN=xxx:yyy bash
#   curl -fsSL https://kopiaiagent.com/install.sh | KOPI_API_KEY=kopi_xxx bash
#
# 多实例隔离安装:
#   curl -fsSL https://kopiaiagent.com/install.sh | \
#     KOPI_HOME=/root/tw1/.kopi \
#     KOPI_INSTANCE_NAME=tw1 \
#     KOPI_INSTALL_DIR=/root/tw1/kopi-ai-agent \
#     bash
#
# Environment variables:
#   TG_TOKEN          - Telegram Bot Token (from @BotFather)
#   KOPI_API_KEY      - Existing API key (skip auto-provision if set)
#   KOPI_MODEL        - Default model (default: kopi-o)
#   KOPI_HOME         - Config/data directory (default: ~/.kopi)
#   KOPI_INSTANCE_NAME- Instance name for multi-instance (default: "")
#                       Empty = main instance (kopi / kopi-gateway)
#                       Non-empty = isolated (kopi-tw1 / kopi-gateway-tw1)
#   KOPI_INSTALL_DIR  - Engine installation directory
#                       (default: /opt/kopi-ai-agent[-NAME] Linux,
#                        ~/.kopi[-NAME]/kopi-ai-agent macOS)
#   KOPI_SKIP_ENGINE  - Skip engine uv sync if "true" (default: false)
#   KOPI_SKIP_SERVICE - Skip systemd/launchd service install (default: false)
#   KOPI_SKIP_SKILLS  - Skip skill sync (default: false)
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
KOPI_INSTANCE_NAME="${KOPI_INSTANCE_NAME:-}"
# Override KOPI_PROXY_BASE_URL to target a different deployment/API version.
KOPI_PROXY_BASE="${KOPI_PROXY_BASE_URL:-https://kopiaiagent.com/v1}"
KOPI_PROXY_FALLBACK="https://kopi.readinghero.xyz/v1"
AUTO_PROVISION_URL="${KOPI_PROXY_BASE}/auto-provision/ready"
PROVISION_URL="${KOPI_PROXY_BASE}/provision"
KOPI_MODEL="${KOPI_MODEL:-kopi-o}"
KOPI_SKIP_ENGINE="${KOPI_SKIP_ENGINE:-false}"
KOPI_SKIP_SERVICE="${KOPI_SKIP_SERVICE:-false}"
KOPI_SKIP_SKILLS="${KOPI_SKIP_SKILLS:-false}"
REPO_URL="https://github.com/kopiagent/kopi-ai-agent.git"

# ── Platform detection ─────────────────────────────────────────────────
OS="$(uname -s)"
IS_MACOS=false
IS_LINUX=false

if [[ "$OS" == "Darwin" ]]; then
    IS_MACOS=true
elif [[ "$OS" == "Linux" ]]; then
    IS_LINUX=true
fi

# ── Instance-aware naming ──────────────────────────────────────────────
SUFFIX=""
INSTANCE_DISPLAY=""
if [[ -n "$KOPI_INSTANCE_NAME" ]]; then
    SUFFIX="-$KOPI_INSTANCE_NAME"
    INSTANCE_DISPLAY=" [$KOPI_INSTANCE_NAME]"
fi

# Service and binary names
SERVICE_NAME="kopi-gateway${SUFFIX}"
CLI_NAME="kopi${SUFFIX}"

# Install directory
if [[ -z "${KOPI_INSTALL_DIR:-}" ]]; then
    if [[ "$IS_MACOS" == true ]]; then
        KOPI_INSTALL_DIR="${KOPI_HOME}/kopi-ai-agent"
    else
        KOPI_INSTALL_DIR="/opt/kopi-ai-agent${SUFFIX}"
    fi
fi

# Credential file (instance-aware)
CRED_FILE="${KOPI_HOME}/kopi-credentials"

# ── Helpers ────────────────────────────────────────────────────────────
info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()  { echo -e "${RED}✗${NC}  $*"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# Cross-platform sed -i
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
    echo -e "${DIM}  一键安装，一步到位${INSTANCE_DISPLAY}${NC}"
    if [[ "$IS_MACOS" == true ]]; then
        echo -e "${DIM}  检测到 macOS ($(uname -m))${NC}"
    else
        echo -e "${DIM}  检测到 Linux${NC}"
    fi
    echo ""
}

# ── Pre-flight checks ─────────────────────────────────────────────────
preflight() {
    if [[ "$IS_MACOS" == false && "$IS_LINUX" == false ]]; then
        fail "不支持的系统: $OS。仅支持 Linux 和 macOS。"
    fi

    if [[ "$IS_LINUX" == true ]] && [[ $EUID -ne 0 ]]; then
        fail "Linux 上请使用 root 运行: sudo bash 或 curl ... | sudo bash"
    fi

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

    # macOS needs Homebrew (for python3)
    if [[ "$IS_MACOS" == true ]]; then
        if ! command -v brew &>/dev/null; then
            warn "macOS 需要 Homebrew 来安装 Python3 等依赖"
            info "安装 Homebrew（可能需要输入密码）..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            if [[ -f /opt/homebrew/bin/brew ]]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [[ -f /usr/local/bin/brew ]]; then
                eval "$(/usr/local/bin/brew shellenv)"
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

    # git is required for cloning
    if ! command -v git &>/dev/null; then
        info "安装 git..."
        if [[ "$IS_MACOS" == true ]]; then
            brew install git
        else
            apt-get update -qq && apt-get install -y -qq git 2>/dev/null || \
            yum install -y -q git 2>/dev/null || \
            fail "无法安装 git，请手动安装后重试"
        fi
    fi

    ok "系统检查通过 ($OS)"
}

# ── Step 1: Clone or Update Repo ───────────────────────────────────────
clone_or_update_repo() {
    step "下载 Kopi Ai Agent 引擎${INSTANCE_DISPLAY}"

    mkdir -p "$(dirname "$KOPI_INSTALL_DIR")"

    if [[ -d "$KOPI_INSTALL_DIR/.git" ]]; then
        info "检测到已有代码目录，更新中..."
        cd "$KOPI_INSTALL_DIR"
        git fetch --depth=1 origin main 2>/dev/null || \
            git fetch --depth=1 origin master 2>/dev/null || true
        git reset --hard origin/main 2>/dev/null || \
            git reset --hard origin/master 2>/dev/null || true
        cd /tmp
    else
        info "克隆代码到 $KOPI_INSTALL_DIR ..."
        git clone --depth=1 "$REPO_URL" "$KOPI_INSTALL_DIR"
    fi

    ok "代码已就绪: $KOPI_INSTALL_DIR"
}

# ── Step 2: Install Engine (uv sync) ──────────────────────────────────
install_engine() {
    if [[ "$KOPI_SKIP_ENGINE" == "true" ]]; then
        info "KOPI_SKIP_ENGINE=true，跳过引擎安装"
        return
    fi

    step "安装依赖${INSTANCE_DISPLAY}"

    cd "$KOPI_INSTALL_DIR"

    # Install / locate uv
    local UV_CMD=""
    if command -v uv &>/dev/null; then
        UV_CMD="uv"
    elif [[ -x "$HOME/.local/bin/uv" ]]; then
        UV_CMD="$HOME/.local/bin/uv"
    elif [[ -x "$HOME/.cargo/bin/uv" ]]; then
        UV_CMD="$HOME/.cargo/bin/uv"
    fi

    if [[ -z "$UV_CMD" ]]; then
        info "安装 uv (Python 包管理器)..."
        local uv_installer
        uv_installer="$(mktemp)"
        curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer"
        sh "$uv_installer"
        rm -f "$uv_installer"
        if [[ -x "$HOME/.local/bin/uv" ]]; then
            UV_CMD="$HOME/.local/bin/uv"
        elif [[ -x "$HOME/.cargo/bin/uv" ]]; then
            UV_CMD="$HOME/.cargo/bin/uv"
        else
            # Fallback: try pip install uv
            pip3 install uv 2>/dev/null && UV_CMD="uv" || \
            fail "无法安装 uv。请手动安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        fi
    fi

    # Create venv and install
    info "创建虚拟环境并安装依赖 (uv sync)..."
    info "这可能需要 1-5 分钟，取决于网络速度"
    export UV_NO_CONFIG=1

    # Try hash-verified install first, fall back to pip
    if [[ -f "uv.lock" ]]; then
        if $UV_CMD venv venv --python 3.11 2>/dev/null || $UV_CMD venv venv 2>/dev/null; then
            ok "虚拟环境已创建"
        else
            # uv venv failed, try python directly
            python3 -m venv venv
            ok "虚拟环境已创建 (stdlib venv)"
        fi

        if UV_PROJECT_ENVIRONMENT="$KOPI_INSTALL_DIR/venv" $UV_CMD sync --extra all --locked 2>/dev/null; then
            ok "依赖已安装 (hash-verified via uv.lock)"
        elif UV_PROJECT_ENVIRONMENT="$KOPI_INSTALL_DIR/venv" $UV_CMD sync 2>/dev/null; then
            ok "依赖已安装 (re-resolved)"
        else
            warn "uv sync 失败，尝试 pip install 降级..."
            cd "$KOPI_INSTALL_DIR"
            ./venv/bin/pip install -e ".[all]" 2>/dev/null || \
            ./venv/bin/pip install -e "." 2>/dev/null || \
            fail "pip install 也失败。请检查网络和 Python 环境后重试"
        fi
    else
        python3 -m venv venv
        info "未找到 uv.lock，使用 pip 安装..."
        ./venv/bin/pip install --upgrade pip setuptools wheel
        ./venv/bin/pip install -e ".[all]" 2>/dev/null || \
        ./venv/bin/pip install -e "." 2>/dev/null || \
        fail "pip install 失败。请检查网络后重试"
    fi

    # Create symlink for CLI
    local bin_dir
    if [[ "$IS_MACOS" == true ]]; then
        bin_dir="$HOME/.local/bin"
    else
        bin_dir="/usr/local/bin"
    fi
    mkdir -p "$bin_dir"

    if [[ -x "$KOPI_INSTALL_DIR/venv/bin/kopi" ]]; then
        # Instance-aware CLI symlink
        ln -sf "$KOPI_INSTALL_DIR/venv/bin/kopi" "$bin_dir/$CLI_NAME"
        ok "CLI 命令: $bin_dir/$CLI_NAME"
    else
        fail "安装后未找到 kopi 可执行文件"
    fi

    local raw_version
    raw_version=$("$bin_dir/$CLI_NAME" --version 2>/dev/null || echo "installed")
    local version
    version=$(echo "$raw_version" | sed 's/[Hh]ermes[[:space:]]*[Aa]gent[[:space:]]*//g; s/[Kk]opi[[:space:]]*[Aa][Ii][[:space:]]*[Aa]gent[[:space:]]*//g; s/[Hh]ermes//g' | xargs)
    [[ -z "$version" ]] && version="installed"
    ok "Kopi Ai Agent 已安装: v$version"
}

# ── Step 3: Auto-Provision API Key ────────────────────────────────────
provision_api_key() {
    step "开通 KOPI Proxy API 账号${INSTANCE_DISPLAY}"

    if [[ -n "${KOPI_API_KEY:-}" ]]; then
        ok "使用提供的 API Key"
        return
    fi

    # Check existing credential file (instance-aware: $KOPI_HOME)
    if [[ -f "$CRED_FILE" ]]; then
        local existing_key
        existing_key=$(cat "$CRED_FILE" 2>/dev/null | tr -d '[:space:]')
        if [[ -n "$existing_key" ]] && [[ "$existing_key" == kp-* || "$existing_key" == kopi-* || "$existing_key" == kopi_* ]]; then
            ok "已有 API Key，跳过开通"
            KOPI_API_KEY="$existing_key"
            return
        fi
    fi

    echo -n "  🔑 正在开通账号..."

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

    mkdir -p "$(dirname "$CRED_FILE")"
    echo "$KOPI_API_KEY" > "$CRED_FILE"
    chmod 600 "$CRED_FILE"
    ok "API Key 已安全存储到 $CRED_FILE"
}

# ── Step 4: Write Config ──────────────────────────────────────────────
write_config() {
    step "写入 KOPI Proxy 配置${INSTANCE_DISPLAY}"

    mkdir -p "$KOPI_HOME"

    if [[ -f "$KOPI_HOME/config.yaml" ]]; then
        local backup="$KOPI_HOME/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$KOPI_HOME/config.yaml" "$backup"
        info "已备份旧配置到 $backup"
    fi

    cat > "$KOPI_HOME/config.yaml" << CONFIG
# ═══════════════════════════════════════════════════════════════════════
# Kopi Ai Agent 配置文件
# By Kopi Ai Agent Pte Ltd
# Auto-generated at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Instance: ${KOPI_INSTANCE_NAME:-main}
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
# Instance: ${KOPI_INSTANCE_NAME:-main}
TZ=Asia/Singapore
ENV
    fi

    if [[ -n "${TG_TOKEN:-}" ]]; then
        if [[ -f "$env_file" ]]; then
            sedi '/^TELEGRAM_BOT_TOKEN=/d' "$env_file"
        fi
        echo "TELEGRAM_BOT_TOKEN=${TG_TOKEN}" >> "$env_file"
    fi

    chmod 600 "$env_file"
    ok "环境变量已写入: $env_file"
}

# ── Step 5: Configure Telegram Gateway ────────────────────────────────
configure_telegram() {
    if [[ -z "${TG_TOKEN:-}" ]]; then
        info "未提供 Telegram Bot Token，跳过 Gateway 配置"
        info "稍后配置: KOPI_HOME=$KOPI_HOME $CLI_NAME config set telegram_bot_token 'YOUR_TOKEN'"
        return
    fi

    step "配置 Telegram Gateway${INSTANCE_DISPLAY}"

    if [[ ! "$TG_TOKEN" =~ ^[0-9]+:.+ ]]; then
        warn "Telegram Bot Token 格式可能不正确，继续配置..."
    fi

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

    if ! grep -q "^telegram:" "$KOPI_HOME/config.yaml" 2>/dev/null; then
        cat >> "$KOPI_HOME/config.yaml" << TGCONF

# ── Telegram 配置 ──────────────────────────────────────────────────────
telegram:
  reactions: false
TGCONF
    fi

    ok "Telegram 配置完成"
}

# ── Step 6: Install Gateway Service ───────────────────────────────────
install_gateway() {
    if [[ "$KOPI_SKIP_SERVICE" == "true" ]]; then
        info "KOPI_SKIP_SERVICE=true，跳过服务安装"
        return
    fi

    if [[ -z "${TG_TOKEN:-}" ]]; then
        return
    fi

    step "安装 Gateway 服务${INSTANCE_DISPLAY}"

    # Try built-in gateway install (instance-aware with KOPI_HOME)
    local kopi_bin="$KOPI_INSTALL_DIR/venv/bin/kopi"
    if [[ -x "$kopi_bin" ]]; then
        if KOPI_HOME="$KOPI_HOME" "$kopi_bin" gateway install 2>/dev/null; then
            ok "Gateway 服务已安装"

            if KOPI_HOME="$KOPI_HOME" "$kopi_bin" gateway start 2>/dev/null; then
                ok "Gateway 已启动"
            else
                warn "Gateway 启动失败，请手动运行: KOPI_HOME=$KOPI_HOME $CLI_NAME gateway start"
            fi
            return
        fi
    fi

    # Fallback: manual service installation
    if [[ "$IS_MACOS" == true ]]; then
        install_gateway_launchd
    else
        install_gateway_systemd
    fi
}

# Linux: systemd service (instance-aware)
install_gateway_systemd() {
    info "使用 systemd 创建 Gateway 服务..."

    local venv_dir="$KOPI_INSTALL_DIR/venv"
    local python_path=""
    if [[ -x "$venv_dir/bin/python3" ]]; then
        python_path="$venv_dir/bin/python3"
    elif [[ -x "$KOPI_INSTALL_DIR/.venv/bin/python3" ]]; then
        python_path="$KOPI_INSTALL_DIR/.venv/bin/python3"
    else
        python_path="$(which python3)"
    fi

    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    cat > "$service_file" << SERVICE
[Unit]
Description=Kopi Ai Agent Gateway${INSTANCE_DISPLAY}
After=network.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=${KOPI_INSTALL_DIR}
Environment=PATH=${venv_dir}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=KOPI_HOME=${KOPI_HOME}
EnvironmentFile=${KOPI_HOME}/.env
ExecStart=${python_path} -m kopi_cli.main gateway run --replace
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" 2>/dev/null || true
    systemctl start "$SERVICE_NAME" 2>/dev/null || warn "Gateway 启动失败"

    ok "Gateway 服务已安装 (systemd): $SERVICE_NAME"
    info "查看状态: systemctl status $SERVICE_NAME"
    info "查看日志: journalctl -u $SERVICE_NAME -f"
}

# macOS: launchd service (instance-aware)
install_gateway_launchd() {
    info "使用 launchd 创建 Gateway 服务..."

    local plist_dir="$HOME/Library/LaunchAgents"
    mkdir -p "$plist_dir"

    local plist_file="${plist_dir}/com.kopi.agent.gateway${SUFFIX}.plist"
    local venv_dir="$KOPI_INSTALL_DIR/venv"
    local log_dir="$KOPI_HOME/logs"
    mkdir -p "$log_dir"

    local python_path=""
    if [[ -x "$venv_dir/bin/python3" ]]; then
        python_path="$venv_dir/bin/python3"
    elif [[ -x "$KOPI_INSTALL_DIR/.venv/bin/python3" ]]; then
        python_path="$KOPI_INSTALL_DIR/.venv/bin/python3"
    else
        python_path="$(which python3)"
    fi

    local label="com.kopi.agent.gateway${SUFFIX}"

    # Unload if exists
    launchctl unload "$plist_file" 2>/dev/null || true

    cat > "$plist_file" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
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
    <string>${KOPI_INSTALL_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>KOPI_HOME</key>
        <string>${KOPI_HOME}</string>
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

    launchctl load "$plist_file" 2>/dev/null || warn "Gateway 启动失败"

    ok "Gateway 服务已安装 (launchd): ${label}"
    info "查看状态: launchctl list ${label}"
    info "查看日志: tail -f $log_dir/gateway-stdout.log"
}

# ── Step 7: Install Skills ────────────────────────────────────────────
install_skills() {
    if [[ "$KOPI_SKIP_SKILLS" == "true" ]]; then
        info "KOPI_SKIP_SKILLS=true，跳过技能安装"
        return
    fi

    step "安装预置技能${INSTANCE_DISPLAY}"

    local skills_dir="$KOPI_HOME/skills"
    mkdir -p "$skills_dir"

    if [[ -d "$KOPI_INSTALL_DIR/skills" ]]; then
        local count=0
        for skill_dir in "$KOPI_INSTALL_DIR/skills/"*/; do
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

    if [[ -d "$KOPI_INSTALL_DIR/optional-skills" ]]; then
        for skill_dir in "$KOPI_INSTALL_DIR/optional-skills/"*/; do
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
    echo -e "${BOLD}${GREEN}  ✓ Kopi Ai Agent 安装完成!${INSTANCE_DISPLAY}${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}使用:${NC}"
    echo -e "    KOPI_HOME=$KOPI_HOME $CLI_NAME        # 交互式聊天（多实例需设 KOPI_HOME）"
    echo -e "    $CLI_NAME                     # 如果已设 KOPI_HOME 环境变量"
    echo -e "    KOPI_HOME=$KOPI_HOME $CLI_NAME gateway  # 启动消息网关"
    echo -e "    KOPI_HOME=$KOPI_HOME $CLI_NAME doctor   # 诊断问题"
    echo ""
    echo -e "  ${BOLD}快速启动（不设 KOPI_HOME 的 alias）:${NC}"
    echo -e "    alias $CLI_NAME='KOPI_HOME=$KOPI_HOME $KOPI_INSTALL_DIR/venv/bin/kopi'"
    echo ""

    if [[ -z "${TG_TOKEN:-}" ]]; then
        echo -e "  ${BOLD}配置 API Key + Telegram:${NC}"
        echo -e "    KOPI_HOME=$KOPI_HOME $CLI_NAME setup"
        echo ""
    fi

    echo -e "  ${BOLD}Gateway 管理:${NC}"
    if [[ "$IS_MACOS" == true ]]; then
        local label="com.kopi.agent.gateway${SUFFIX}"
        local plist_file="$HOME/Library/LaunchAgents/${label}.plist"
        echo -e "    launchctl load $plist_file      # 启动"
        echo -e "    launchctl unload $plist_file    # 停止"
        echo -e "    launchctl list ${label}                    # 状态"
        echo -e "    tail -f $KOPI_HOME/logs/gateway-stdout.log  # 日志"
    else
        echo -e "    systemctl start $SERVICE_NAME   # 启动"
        echo -e "    systemctl stop $SERVICE_NAME    # 停止"
        echo -e "    systemctl status $SERVICE_NAME  # 状态"
        echo -e "    journalctl -u $SERVICE_NAME -f  # 日志"
    fi
    echo ""
    echo -e "  ${BOLD}配置文件:${NC}"
    echo -e "    $KOPI_HOME/config.yaml"
    echo -e "    $KOPI_HOME/.env"
    echo ""

    if [[ -n "${TG_TOKEN:-}" ]]; then
        echo -e "  ${BOLD}Telegram Bot:${NC}"
        echo -e "    已配置完成，在 Telegram 中向你的 Bot 发送消息即可使用!"
        echo ""
    fi

    echo -e "  ${DIM}API Key: ${KOPI_API_KEY:0:12}...${NC}"
    echo -e "  ${DIM}安装目录: ${KOPI_INSTALL_DIR}${NC}"
    echo -e "  ${DIM}配置目录: ${KOPI_HOME}${NC}"
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
    clone_or_update_repo
    install_engine
    provision_api_key
    write_config
    configure_telegram
    install_gateway
    install_skills
    show_completion
}

main "$@"
