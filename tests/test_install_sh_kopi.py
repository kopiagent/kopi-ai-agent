"""Hermetic tests for the rewritten KOPI one-click installer (scripts/install.sh).

The fork replaced upstream's install.sh with its own installer (git clone +
uv sync + kopi-proxy provisioning), so the upstream ``test_install_sh_*``
suites assert a script structure that no longer exists. These tests target
the *current* script the same way upstream did: run the real function bodies
in bash with stubbed commands and isolated HOME/KOPI_HOME, and assert on
observable outcomes (files written, curl calls made, exit codes) — never on
live network or the developer's real ~/.kopi.

Harness: the script ends with ``main "$@"``; we source everything above that
line to get the real functions + config derivation, then invoke one function.
``curl`` is stubbed via a PATH shim that records its argv and replays a canned
response, so provisioning flows are fully offline.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _sourceable(tmp_path: Path) -> Path:
    """Copy install.sh with the trailing ``main "$@"`` stripped, for sourcing."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    body, sep, tail = text.rpartition('main "$@"')
    assert sep, "install.sh must end by invoking main — harness expects to strip it"
    out = tmp_path / "install-sourceable.sh"
    out.write_text(body + tail, encoding="utf-8")
    return out


def _write_curl_stub(bin_dir: Path, response: str) -> Path:
    """Install a fake ``curl`` on PATH that logs argv and prints ``response``."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    log = bin_dir / "curl-calls.log"
    stub = bin_dir / "curl"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log}"\n'
        f"cat <<'RESP'\n{response}\nRESP\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return log


def _run_function(
    tmp_path: Path,
    function: str,
    *,
    env: dict[str, str] | None = None,
    curl_response: str = "",
) -> tuple[subprocess.CompletedProcess, Path]:
    """Source the real install.sh and invoke ``function`` hermetically."""
    home = tmp_path / "home"
    kopi_home = home / ".kopi"
    kopi_home.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "stub-bin"
    curl_log = _write_curl_stub(bin_dir, curl_response)
    script = _sourceable(tmp_path)

    merged = {
        # Stubs first so our curl wins; keep real python3/bash/coreutils.
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "KOPI_HOME": str(kopi_home),
        # Never write to /opt or the real checkout in tests.
        "KOPI_INSTALL_DIR": str(tmp_path / "install-dir"),
        "TERM": "dumb",
    }
    merged.update(env or {})

    proc = subprocess.run(
        ["bash", "-c", f'source "{script}" && {function}'],
        capture_output=True,
        text=True,
        timeout=60,
        env=merged,
        stdin=subprocess.DEVNULL,  # the installer must never block on a prompt
        cwd=tmp_path,
    )
    return proc, curl_log


# ---------------------------------------------------------------------------
# provision_api_key
# ---------------------------------------------------------------------------


def test_provision_skips_when_key_provided_via_env(tmp_path: Path) -> None:
    """KOPI_API_KEY in the environment must short-circuit provisioning."""
    proc, curl_log = _run_function(
        tmp_path, "provision_api_key", env={"KOPI_API_KEY": "kopi-preset-key"}
    )
    assert proc.returncode == 0, proc.stderr
    assert not curl_log.exists(), "must not hit the network when a key is supplied"


def test_provision_is_idempotent_with_existing_credential(tmp_path: Path) -> None:
    """A stored credential is reused; no re-provision, no overwrite.

    Covers every key format the service has issued: kp-*, kopi-* and the
    underscore kopi_* form — an unrecognized prefix silently re-provisions
    on every reinstall.
    """
    for key in ("kopi-existing-key", "kopi_existing_key", "kp-existing-key"):
        kopi_home = tmp_path / f"home-{key[:6]}" / ".kopi"
        home_root = kopi_home.parent
        kopi_home.mkdir(parents=True)
        cred = kopi_home / "kopi-credentials"
        cred.write_text(f"{key}\n", encoding="utf-8")

        proc, curl_log = _run_function(
            tmp_path, "provision_api_key",
            env={"HOME": str(home_root), "KOPI_HOME": str(kopi_home)},
        )
        assert proc.returncode == 0, f"{key}: {proc.stderr}"
        assert not curl_log.exists(), f"{key}: existing credential must skip provisioning"
        assert cred.read_text(encoding="utf-8").strip() == key
        curl_log.unlink(missing_ok=True)


def test_provision_writes_credential_with_0600_perms(tmp_path: Path) -> None:
    """A successful auto-provision stores the key at $KOPI_HOME, mode 600."""
    proc, curl_log = _run_function(
        tmp_path,
        "provision_api_key",
        curl_response='{"api_key": "kopi-fresh-key"}',
    )
    assert proc.returncode == 0, proc.stderr
    assert curl_log.exists(), "auto-provision must call the provisioning endpoint"
    cred = tmp_path / "home" / ".kopi" / "kopi-credentials"
    assert cred.read_text(encoding="utf-8").strip() == "kopi-fresh-key"
    assert stat.S_IMODE(cred.stat().st_mode) == 0o600


def test_provision_failure_exits_with_manual_guidance(tmp_path: Path) -> None:
    """Empty/garbage provisioning response fails loudly with a manual fallback."""
    proc, _ = _run_function(tmp_path, "provision_api_key", curl_response="")
    assert proc.returncode != 0, "provisioning failure must not be silent success"
    combined = proc.stdout + proc.stderr
    assert "KOPI_API_KEY=" in combined, "failure message must show the manual path"
    cred = tmp_path / "home" / ".kopi" / "kopi-credentials"
    assert not cred.exists(), "no credential file may be written on failure"


def test_provision_url_follows_base_url_override(tmp_path: Path) -> None:
    """KOPI_PROXY_BASE_URL must re-target the provisioning endpoints."""
    proc, curl_log = _run_function(
        tmp_path,
        "provision_api_key",
        env={"KOPI_PROXY_BASE_URL": "https://kopiaiagent.com/v3"},
        curl_response='{"api_key": "kopi-v3-key"}',
    )
    assert proc.returncode == 0, proc.stderr
    calls = curl_log.read_text(encoding="utf-8")
    assert "https://kopiaiagent.com/v3/auto-provision/ready" in calls
    assert "https://kopiaiagent.com/v1/" not in calls


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------


def test_write_config_targets_kopi_proxy(tmp_path: Path) -> None:
    """config.yaml pins provider kopi-proxy with the resolved base_url + key."""
    proc, _ = _run_function(
        tmp_path,
        "write_config",
        env={"KOPI_API_KEY": "kopi-cfg-key", "KOPI_MODEL": "kopi-o"},
    )
    assert proc.returncode == 0, proc.stderr
    cfg = (tmp_path / "home" / ".kopi" / "config.yaml").read_text(encoding="utf-8")
    assert "provider: kopi-proxy" in cfg
    assert "base_url: https://kopiaiagent.com/v1" in cfg
    assert "api_key: kopi-cfg-key" in cfg
    assert "default: kopi-o" in cfg


def test_write_config_backs_up_existing_config(tmp_path: Path) -> None:
    """Re-running the installer must never destroy a user's config silently."""
    kopi_home = tmp_path / "home" / ".kopi"
    kopi_home.mkdir(parents=True)
    (kopi_home / "config.yaml").write_text("original: true\n", encoding="utf-8")

    proc, _ = _run_function(tmp_path, "write_config", env={"KOPI_API_KEY": "kopi-x"})
    assert proc.returncode == 0, proc.stderr
    backups = list(kopi_home.glob("config.yaml.backup.*"))
    assert backups, "existing config.yaml must be backed up before overwrite"
    assert backups[0].read_text(encoding="utf-8") == "original: true\n"


def test_write_config_base_url_override(tmp_path: Path) -> None:
    proc, _ = _run_function(
        tmp_path,
        "write_config",
        env={
            "KOPI_API_KEY": "kopi-x",
            "KOPI_PROXY_BASE_URL": "https://kopiaiagent.com/v3",
        },
    )
    assert proc.returncode == 0, proc.stderr
    cfg = (tmp_path / "home" / ".kopi" / "config.yaml").read_text(encoding="utf-8")
    assert "base_url: https://kopiaiagent.com/v3" in cfg


# ---------------------------------------------------------------------------
# Static invariants
# ---------------------------------------------------------------------------


def test_script_has_no_interactive_prompts() -> None:
    """curl | bash installs run with no TTY — the script must never `read`."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        assert not code.strip().startswith("read "), (
            f"install.sh:{lineno} uses `read` — a piped install has no TTY and "
            "would hang forever."
        )


def test_script_clones_the_kopi_org_repo() -> None:
    """Pin the repo org — a wrong org here installs somebody else's product."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert 'REPO_URL="https://github.com/kopiagent/kopi-ai-agent.git"' in text
    assert "NousResearch" not in text
