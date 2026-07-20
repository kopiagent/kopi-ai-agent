"""Contract test: install.sh stamps the install method next to the code tree
($INSTALL_DIR), not into the shared $KOPI_HOME.

Background (shared-$KOPI_HOME bug)
------------------------------------
$KOPI_HOME is a data directory users frequently bind-mount into a Docker
gateway as well (``~/.kopi:/opt/data``). The published image stamps 'docker'
there on boot, so if install.sh had written its 'git' marker into the same
$KOPI_HOME the two installs would fight over one slot — and the container,
booting last, would win and wrongly make the host install look like 'docker'
(blocking ``kopi update``).

The fix: detect_install_method() reads a CODE-scoped stamp first, and the
installer writes ``git`` into $INSTALL_DIR (the git checkout, e.g.
``~/.kopi/kopi-ai-agent``), which is unique to this install and immune to the
shared data dir.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_install_sh_stamps_code_tree_not_home() -> None:
    text = INSTALL_SH.read_text()

    # Stamps the code tree.
    assert text.count('echo "git" > "$INSTALL_DIR/.install_method"') >= 1, (
        "install.sh must stamp $INSTALL_DIR/.install_method (code-scoped)"
    )

    # Never stamps the shared data dir.
    assert not re.search(r'>\s*"\$KOPI_HOME/\.install_method"', text), (
        "install.sh must not stamp $KOPI_HOME/.install_method — that data "
        "dir may be shared with a Docker gateway whose 'docker' stamp would "
        "clobber it and block host-side `kopi update`"
    )

# The fork replaced upstream's install.sh with the KOPI one-click installer
# (git clone + uv sync + kopi-proxy provisioning), so this module's assertions
# target a script structure that no longer exists. Coverage for the current
# installer lives in tests/test_install_sh_kopi.py.
import pytest as _pytest_skip_mod
pytestmark = _pytest_skip_mod.mark.skip(
    reason="upstream install.sh replaced by the KOPI installer; see test_install_sh_kopi.py"
)
