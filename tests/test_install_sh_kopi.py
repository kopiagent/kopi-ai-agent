"""Hermetic tests for the KOPI staged installer (scripts/install.sh).

The installer is Hermes's staged bootstrap protocol (rebranded), which the
desktop app drives via `--manifest` then per-stage `--stage NAME --json
--non-interactive`. These tests exercise those real entry points with a
stubbed `curl` and an isolated HOME/KOPI_HOME — no live network, no touching
the developer's real ~/.kopi.

The KOPI fork adds one thing on top of Hermes: `provision_kopi_proxy_key`
runs inside the non-interactive `config` stage so both the CLI installer and
the desktop bootstrap land with a KOPI Proxy key in ~/.kopi/.env.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _run(
    args: list[str],
    tmp_path: Path,
    *,
    env: dict[str, str] | None = None,
    curl_response: str | None = None,
) -> tuple[subprocess.CompletedProcess, Path, Path]:
    """Run install.sh with the given flags in an isolated HOME/KOPI_HOME.

    When ``curl_response`` is given, a fake ``curl`` on PATH records its argv
    and replays that body — so provisioning flows never hit the network.
    """
    home = tmp_path / "home"
    kopi_home = home / ".kopi"
    kopi_home.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    curl_log = bin_dir / "curl-calls.log"

    path_prefix = ""
    if curl_response is not None:
        stub = bin_dir / "curl"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            f'echo "$@" >> "{curl_log}"\n'
            f"cat <<'RESP'\n{curl_response}\nRESP\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        path_prefix = f"{bin_dir}:"

    merged = {
        "PATH": f"{path_prefix}{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "KOPI_HOME": str(kopi_home),
        "KOPI_INSTALL_DIR": str(tmp_path / "install-dir"),
        "TERM": "dumb",
    }
    merged.update(env or {})

    proc = subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        timeout=90,
        env=merged,
        stdin=subprocess.DEVNULL,  # the installer must never block on a prompt
        cwd=tmp_path,
    )
    return proc, kopi_home, curl_log


def _last_json(stdout: str) -> dict:
    """Return the last JSON object line from stdout (the protocol result frame)."""
    for line in reversed([ln for ln in stdout.splitlines() if ln.strip()]):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"no JSON frame in output:\n{stdout}")


# ---------------------------------------------------------------------------
# --manifest: the desktop bootstrap protocol entry point
# ---------------------------------------------------------------------------


def test_manifest_emits_expected_stages(tmp_path: Path) -> None:
    proc, _, _ = _run(["--manifest"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    manifest = _last_json(proc.stdout)
    assert manifest.get("protocol_version") == 1
    names = [s["name"] for s in manifest["stages"]]
    # The desktop bootstrap-runner iterates exactly these stage names.
    for required in ("prerequisites", "repository", "venv", "python-deps", "config", "complete"):
        assert required in names, f"{required} missing from manifest: {names}"


def test_manifest_marks_setup_needs_user_input(tmp_path: Path) -> None:
    """The interactive stages must be flagged so the desktop skips them."""
    proc, _, _ = _run(["--manifest"], tmp_path)
    manifest = _last_json(proc.stdout)
    by_name = {s["name"]: s for s in manifest["stages"]}
    assert by_name["setup"]["needs_user_input"] is True
    assert by_name["config"]["needs_user_input"] is False  # runs on desktop


# ---------------------------------------------------------------------------
# config stage: where the KOPI fork provisions the proxy key (non-interactive)
# ---------------------------------------------------------------------------


def test_config_stage_persists_env_provided_key(tmp_path: Path) -> None:
    proc, kopi_home, curl_log = _run(
        ["--stage", "config", "--json", "--non-interactive"],
        tmp_path,
        env={"KOPI_API_KEY": "kopi-preset-key"},
        curl_response="{}",
    )
    assert _last_json(proc.stdout).get("ok") is True, proc.stdout
    env_text = (kopi_home / ".env").read_text(encoding="utf-8")
    assert "KOPI_API_KEY=kopi-preset-key" in env_text
    assert not curl_log.exists(), "must not hit the network when a key is supplied"


def test_config_stage_auto_provisions_via_endpoint(tmp_path: Path) -> None:
    proc, kopi_home, curl_log = _run(
        ["--stage", "config", "--json", "--non-interactive"],
        tmp_path,
        curl_response='{"api_key": "kopi-fresh-key"}',
    )
    assert _last_json(proc.stdout).get("ok") is True, proc.stdout
    assert "KOPI_API_KEY=kopi-fresh-key" in (kopi_home / ".env").read_text(encoding="utf-8")
    assert curl_log.exists(), "auto-provision must call the endpoint when no key is set"


def test_config_stage_is_idempotent_on_existing_key(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".kopi").mkdir(parents=True)
    (home / ".kopi" / ".env").write_text("KOPI_API_KEY=kopi-existing\n", encoding="utf-8")

    proc, kopi_home, curl_log = _run(
        ["--stage", "config", "--json", "--non-interactive"],
        tmp_path,
        curl_response='{"api_key": "kopi-should-not-be-used"}',
    )
    assert _last_json(proc.stdout).get("ok") is True, proc.stdout
    env_text = (kopi_home / ".env").read_text(encoding="utf-8")
    assert "kopi-existing" in env_text
    assert "kopi-should-not-be-used" not in env_text
    assert not curl_log.exists(), "existing key must skip provisioning"


def test_config_stage_provision_failure_is_soft(tmp_path: Path) -> None:
    """An empty provisioning response must not fail the stage."""
    proc, kopi_home, _ = _run(
        ["--stage", "config", "--json", "--non-interactive"],
        tmp_path,
        curl_response="",
    )
    # Stage still succeeds; the user can add a key later.
    assert _last_json(proc.stdout).get("ok") is True, proc.stdout
    env_text = (kopi_home / ".env").read_text(encoding="utf-8")
    assert "KOPI_API_KEY=" not in env_text or "KOPI_API_KEY=\n" in env_text


def test_provision_url_follows_base_url_override(tmp_path: Path) -> None:
    _, _, curl_log = _run(
        ["--stage", "config", "--json", "--non-interactive"],
        tmp_path,
        env={"KOPI_PROXY_BASE_URL": "https://kopiaiagent.com/v3"},
        curl_response='{"api_key": "kopi-v3"}',
    )
    calls = curl_log.read_text(encoding="utf-8")
    assert "https://kopiaiagent.com/v3/auto-provision/ready" in calls


# ---------------------------------------------------------------------------
# non-interactive invariant: interactive stages are skipped, never prompt
# ---------------------------------------------------------------------------


def test_setup_stage_skips_in_non_interactive(tmp_path: Path) -> None:
    """setup is needs_user_input=true → --non-interactive must skip, not prompt."""
    proc, _, _ = _run(["--stage", "setup", "--json", "--non-interactive"], tmp_path)
    frame = _last_json(proc.stdout)
    assert frame.get("skipped") is True, frame


# ---------------------------------------------------------------------------
# Static invariants
# ---------------------------------------------------------------------------


def test_repo_org_pinned_and_no_hermes_residue() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "kopiagent/kopi-ai-agent" in text
    assert "NousResearch" not in text
    assert "hermes" not in text.lower()
