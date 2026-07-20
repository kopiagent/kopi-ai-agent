#!/usr/bin/env bash
# ============================================================================
# KOPI — 统一版本号管理
#
# 项目只有一个客户可见的产品版本,写在四个地方,本脚本一次同步:
#   1. package.json            (根,产品版本的权威来源)
#   2. apps/desktop/package.json  (electron-builder 用它命名安装包)
#   3. pyproject.toml          (Python 包版本)
#   4. kopi_cli/__init__.py    (`kopi --version`、User-Agent、遥测 client 标签)
#
# 用法:
#   scripts/bump-version.sh 1.21.0     # 写入四处
#   scripts/bump-version.sh            # 只校验四处是否一致(CI 可用)
#
# 发布流程:
#   scripts/bump-version.sh 1.21.0
#   git commit -am "release: v1.21.0" && git tag v1.21.0
#   git push origin main v1.21.0      # tag 触发 desktop-release 三平台打包
#
# 上游同步注意:hermes sync 带来的版本号改动(pyproject/__init__/desktop)
# 一律保留我们自己的值 —— 上游版本记录在 .upstream-sync.json,不进产品版本。
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"

python3 - "$VERSION" <<'PYEOF'
import json, re, sys
from pathlib import Path

version = sys.argv[1] if len(sys.argv) > 1 else ""
if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
    sys.exit(f"✗ 版本号必须是 x.y.z 形式,收到: {version!r}")

def read_json_version(path):
    return json.loads(Path(path).read_text(encoding="utf-8")).get("version")

def write_json_version(path, v):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    old = read_json_version(path)
    # 只替换顶层 version 字段那一行,不重排整个 JSON
    new_text, n = re.subn(
        rf'^(\s*"version":\s*)"{re.escape(old)}"', rf'\g<1>"{v}"', text,
        count=1, flags=re.M,
    )
    assert n == 1, f"{path}: 未找到 version 字段"
    p.write_text(new_text, encoding="utf-8")

def write_pyproject(v):
    p = Path("pyproject.toml")
    text = p.read_text(encoding="utf-8")
    new_text, n = re.subn(r'^version = "[^"]+"', f'version = "{v}"', text, count=1, flags=re.M)
    assert n == 1, "pyproject.toml: 未找到 version 字段"
    p.write_text(new_text, encoding="utf-8")

def write_init(v):
    p = Path("kopi_cli/__init__.py")
    text = p.read_text(encoding="utf-8")
    new_text, n = re.subn(r'^__version__ = "[^"]+"', f'__version__ = "{v}"', text, count=1, flags=re.M)
    assert n == 1, "kopi_cli/__init__.py: 未找到 __version__"
    p.write_text(new_text, encoding="utf-8")

def current_versions():
    return {
        "package.json": read_json_version("package.json"),
        "apps/desktop/package.json": read_json_version("apps/desktop/package.json"),
        "pyproject.toml": re.search(r'^version = "([^"]+)"', Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1),
        "kopi_cli/__init__.py": re.search(r'^__version__ = "([^"]+)"', Path("kopi_cli/__init__.py").read_text(encoding="utf-8"), re.M).group(1),
    }

if version:
    write_json_version("package.json", version)
    write_json_version("apps/desktop/package.json", version)
    write_pyproject(version)
    write_init(version)

vs = current_versions()
for k, v in vs.items():
    print(f"  {k:32} {v}")
if len(set(vs.values())) != 1:
    sys.exit("✗ 四处版本不一致 — 用 scripts/bump-version.sh <x.y.z> 统一")
print(f"✓ 版本一致: {list(vs.values())[0]}")
PYEOF
