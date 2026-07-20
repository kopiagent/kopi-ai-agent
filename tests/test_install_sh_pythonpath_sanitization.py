"""Regression tests for install.sh Python environment sanitization.

When install.sh is launched from another Python-driven tool session, inherited
PYTHONPATH/PYTHONHOME can shadow the freshly installed checkout. The installer
must sanitize those vars both during installation and at runtime launch.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_install_script_unsets_pythonpath_and_pythonhome_early() -> None:
    text = INSTALL_SH.read_text()

    # During install, inherited Python env must be sanitized before pip/venv use.
    assert 'unset PYTHONPATH' in text
    assert 'unset PYTHONHOME' in text


def test_kopi_launcher_wrapper_clears_python_env_before_exec() -> None:
    text = INSTALL_SH.read_text()

    # Wrapper should clear env and forward args untouched to the venv entrypoint.
    assert 'cat > "$command_link_dir/kopi" <<EOF' in text
    assert 'unset PYTHONPATH' in text
    assert 'unset PYTHONHOME' in text
    assert 'exec "$KOPI_BIN" "\\$@"' in text

# The fork replaced upstream's install.sh with the KOPI one-click installer
# (git clone + uv sync + kopi-proxy provisioning), so this module's assertions
# target a script structure that no longer exists. Coverage for the current
# installer lives in tests/test_install_sh_kopi.py.
import pytest as _pytest_skip_mod
pytestmark = _pytest_skip_mod.mark.skip(
    reason="upstream install.sh replaced by the KOPI installer; see test_install_sh_kopi.py"
)
