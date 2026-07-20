"""Regression tests for Termux network prerequisite handling in install.sh."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_termux_pkg_list_includes_network_basics() -> None:
    text = INSTALL_SH.read_text()
    assert "local termux_pkgs=(clang rust make pkg-config libffi openssl ca-certificates curl)" in text


def test_install_script_has_connectivity_probe_and_termux_guidance() -> None:
    text = INSTALL_SH.read_text()
    assert "check_network_prerequisites()" in text
    assert "https://pypi.org/simple/" in text
    assert "https://duckduckgo.com/" in text
    assert "termux-change-repo" in text
    assert "pkg install -y ca-certificates curl && pkg update" in text
    assert "check_network_prerequisites" in text

# The fork replaced upstream's install.sh with the KOPI one-click installer
# (git clone + uv sync + kopi-proxy provisioning), so this module's assertions
# target a script structure that no longer exists. Coverage for the current
# installer lives in tests/test_install_sh_kopi.py.
import pytest as _pytest_skip_mod
pytestmark = _pytest_skip_mod.mark.skip(
    reason="upstream install.sh replaced by the KOPI installer; see test_install_sh_kopi.py"
)
