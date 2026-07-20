#!/usr/bin/env bash
# ============================================================================
# KOPI AI AGENT — install.sh 端到端回归测试
#
# 在干净的 Docker 容器里跑真实的 scripts/install.sh(本地当前版本,不是网站
# 托管副本),然后验收最终状态。单元测试(tests/test_install_sh_kopi.py)里
# curl/git 都是假的;这里回答的是终极问题:"一台全新机器装得上、能运行吗?"
#
# 用法:
#   KOPI_API_KEY=kopi-xxx scripts/test-install-e2e.sh                # 默认 ubuntu:24.04
#   KOPI_API_KEY=kopi-xxx scripts/test-install-e2e.sh ubuntu:22.04 debian:12   # 镜像矩阵
#
# 环境变量:
#   KOPI_API_KEY          必填。预置 key 跳过自动开通,避免每次测试都在生产
#                         环境创建新账号(开通链路已有密封单测覆盖)。
#   KOPI_PROXY_BASE_URL   可选。覆盖接入端点(如 /v3 预发布验证)。
#
# 已知边界:容器无 systemd,服务安装段用 KOPI_SKIP_SERVICE=true 跳过;
# macOS 安装路径分支不在本测试覆盖范围。
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_SH="$REPO_ROOT/scripts/install.sh"

if [[ -z "${KOPI_API_KEY:-}" ]]; then
    echo "✗ 需要 KOPI_API_KEY(预置 key,避免测试在生产环境开新账号)" >&2
    echo "  用法: KOPI_API_KEY=kopi-xxx $0 [镜像...]" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "✗ 需要 docker" >&2
    exit 2
fi

IMAGES=("$@")
[[ ${#IMAGES[@]} -eq 0 ]] && IMAGES=("ubuntu:24.04")

FAILED=()
for IMAGE in "${IMAGES[@]}"; do
    echo ""
    echo "══════════════════════════════════════════════════════════"
    echo "  E2E: $IMAGE"
    echo "══════════════════════════════════════════════════════════"
    if docker run --rm \
        -v "$INSTALL_SH":/install.sh:ro \
        -e KOPI_API_KEY="$KOPI_API_KEY" \
        -e KOPI_PROXY_BASE_URL="${KOPI_PROXY_BASE_URL:-}" \
        -e KOPI_SKIP_SERVICE=true \
        "$IMAGE" bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
echo "=== [1/3] 准备基础依赖 ==="
apt-get update -qq >/dev/null
apt-get install -y -qq curl git ca-certificates python3 >/dev/null 2>&1
echo "=== [2/3] 运行 install.sh ==="
bash /install.sh
echo "=== [3/3] 验收断言 ==="
test -x /usr/local/bin/kopi        && echo "PASS: /usr/local/bin/kopi 存在且可执行"
grep -q "provider: kopi-proxy" ~/.kopi/config.yaml && echo "PASS: config 指向 kopi-proxy"
grep -Eq "api_key: (kopi[-_]|kp-)" ~/.kopi/config.yaml && echo "PASS: config 含 API key"
test -d /opt/kopi-ai-agent/venv    && echo "PASS: venv 已创建"
/usr/local/bin/kopi --version >/dev/null && echo "PASS: kopi --version 可运行"
echo "=== E2E ALL PASS ($(uname -sr)) ==="
'; then
        echo "✓ $IMAGE 通过"
    else
        echo "✗ $IMAGE 失败"
        FAILED+=("$IMAGE")
    fi
done

echo ""
if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "✗ 失败镜像: ${FAILED[*]}"
    exit 1
fi
echo "✓ 全部镜像通过 (${IMAGES[*]})"
