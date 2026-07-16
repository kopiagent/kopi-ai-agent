from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    assert "%LOCALAPPDATA%\\kopi\\kopi-ai-agent\\venv\\Scripts" in doc
    assert "Get-Command kopi        # should print C:\\Users\\<you>\\AppData\\Local\\kopi\\kopi-ai-agent\\venv\\Scripts\\kopi.exe" in doc
    assert '$kopiBin = "$InstallDir\\venv\\Scripts"' in install
