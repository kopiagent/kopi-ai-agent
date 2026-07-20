"""Windows installer must auto-provision the Kopi API key.

The POSIX installer has long provisioned a first-run KOPI_API_KEY.  The Windows
installer used to only copy .env/config.yaml templates, leaving users with an
empty KOPI_API_KEY after a successful install.  These source-level checks keep
the PowerShell installer aligned without requiring Windows CI.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"


def _install_ps1() -> str:
    return INSTALL_PS1.read_text(encoding="utf-8")


def test_windows_installer_defines_kopi_auto_provision_endpoint() -> None:
    text = _install_ps1()

    assert "$KopiProxyBaseUrl" in text
    assert "$KopiAutoProvisionUrl = \"$KopiProxyBaseUrl/auto-provision/ready\"" in text
    assert "KOPI_PROXY_BASE_URL" in text


def test_windows_config_stage_auto_provisions_kopi_api_key() -> None:
    text = _install_ps1()

    body = re.search(
        r"function Copy-ConfigTemplates \{(?P<body>[\s\S]*?)^\}",
        text,
        re.MULTILINE,
    )
    assert body is not None
    assert "Ensure-KopiApiKey -EnvPath $envPath" in body.group("body")

    provision = re.search(
        r"function Ensure-KopiApiKey \{(?P<body>[\s\S]*?)^function ",
        text,
        re.MULTILINE,
    )
    assert provision is not None
    provision_body = provision.group("body")

    assert "Get-ExistingKopiApiKey -EnvPath $EnvPath" in provision_body
    assert "Invoke-WebRequest -UseBasicParsing -Method Post -Uri $KopiAutoProvisionUrl" in provision_body
    assert "$payload = $response.Content | ConvertFrom-Json" in provision_body
    assert "$apiKey = \"$($payload.api_key)\".Trim()" in provision_body
    assert 'Set-DotEnvValue -Path $EnvPath -Key "KOPI_API_KEY" -Value $apiKey' in provision_body
    assert 'Join-Path $KopiHome "kopi-credentials"' in provision_body


def test_windows_auto_provision_respects_existing_keys() -> None:
    text = _install_ps1()

    existing = re.search(
        r"function Get-ExistingKopiApiKey \{(?P<body>[\s\S]*?)^function ",
        text,
        re.MULTILINE,
    )
    assert existing is not None
    body = existing.group("body")

    assert '$provided = "$env:KOPI_API_KEY".Trim()' in body
    assert 'Join-Path $KopiHome "kopi-credentials"' in body
    assert 'Get-DotEnvValue -Path $EnvPath -Key "KOPI_API_KEY"' in body
    assert 'if ($provided) { return $provided }' in body
