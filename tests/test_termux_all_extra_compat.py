"""Regression coverage for the Termux broad install profile."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_pyproject_defines_termux_all_without_known_blockers() -> None:
    text = PYPROJECT.read_text()
    assert "termux-all = [" in text
    assert '"kopi-ai-agent[termux]"' in text
    assert '"kopi-ai-agent[matrix]"' not in text.split("termux-all = [", 1)[1].split("]", 1)[0]
    assert '"kopi-ai-agent[voice]"' not in text.split("termux-all = [", 1)[1].split("]", 1)[0]


def test_install_script_prefers_termux_all_then_fallbacks() -> None:
    text = INSTALL_SH.read_text()
    assert "pip install -e '.[termux-all]' -c constraints-termux.txt" in text
    assert "Termux broad profile (.[termux-all]) failed, trying baseline Termux profile..." in text
    assert "Termux baseline profile (.[termux]) failed, trying base install..." in text

# The fork replaced upstream's install.sh with the KOPI one-click installer,
# which has no Termux [all]-extra fallback chain. See tests/test_install_sh_kopi.py.
import pytest as _pytest_skip_mod
pytestmark = _pytest_skip_mod.mark.skip(
    reason="upstream install.sh replaced by the KOPI installer; see test_install_sh_kopi.py"
)
