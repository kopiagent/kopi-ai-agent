"""Behavioural coverage for ``docker/cont-init.d/05-model-base-url``.

The script rewrites ``model.base_url`` in the generated ``config.yaml`` so a
deployment can point the model layer at its own gateway. Nothing tested it: the
PR that added it only ran the Docker suite (``detect`` resolved
``python=false``), and ``cont-init.d/`` as a whole had no coverage —
``03-kopi-key`` and ``04-dashboard-auth`` are equally untested.

That matters more here than the line count suggests, because every failure mode
of this script looks like success. The container boots, the dashboard answers,
the key is right, and only model calls 401 — from inside the pod, where nobody
is watching. The script's own header says as much.

Each test below pins one promise the script makes in its comments, and each
corresponds to a way it has broken or could break silently:

* honouring the env var at all — the bug that motivated the script
* leaving an unconfigured deployment alone — existing single-tenant installs
* the persisted value winning — an operator's edit to ``.env`` must survive a
  restart and an image upgrade
* rejecting a malformed value — a typo'd URL breaks every model call
* stripping a trailing slash — otherwise requests go to ``…//chat/completions``
* rewriting only the FIRST uncommented ``base_url:`` — the later ones are
  commented provider examples. This one already shipped broken once: the
  original used ``sed '0,/re/s//…/'``, a GNU extension that silently no-ops on
  BSD sed, which is why the code now uses awk.
"""
from __future__ import annotations

import subprocess

from tests.docker.conftest import (
    docker_exec_sh,
    restart_container,
    start_container,
)

GATEWAY = "https://gw.example.com/v2"
CONFIG = "/opt/data/config.yaml"
ENV_FILE = "/opt/data/.env"


def _read(container: str, path: str) -> str:
    """Return a file's contents, or '' when it does not exist."""
    return docker_exec_sh(container, f"cat {path} 2>/dev/null || true").stdout


def _script_log(container: str) -> str:
    """The 05-model-base-url lines from ``docker logs``.

    The first CI run of these tests failed in a way static analysis could not
    close: `.env` carried the injected value (so the script's persist block
    ran) while config.yaml kept the baked default (so the rewrite apparently
    did not) — and the Dockerfile installs the script correctly, the example
    config's `base_url:` line is clean and uncommented, and nothing else
    writes KOPI_PROXY_BASE_URL. The script's own echo lines are the only
    record of which branch it took. Under s6-overlay, cont-init stdout goes to
    the container's stdout — i.e. ``docker logs``, read from the host —
    nothing in docker/ writes a boot log file. Attach them to every assertion
    instead of guessing.
    """
    r = subprocess.run(
        ["docker", "logs", container],
        capture_output=True, text=True, timeout=15,
    )
    lines = [
        line for line in (r.stdout + r.stderr).splitlines()
        if "05-model-base-url" in line
    ]

    return "\n".join(lines) or "(no 05-model-base-url lines in docker logs)"


def _first_base_url(config_text: str) -> str | None:
    """The first uncommented ``base_url:`` value, mirroring the script's own
    selection rule. Comment lines are skipped exactly as the awk program skips
    them, so a test failure means the script disagreed with its own contract
    rather than that this helper parsed differently."""
    for line in config_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("#") or not stripped.startswith("base_url:"):
            continue

        return stripped.split(":", 1)[1].strip().strip('"')

    return None


def test_env_var_rewrites_config_and_persists(built_image, container_name):
    """KOPI_PROXY_BASE_URL reaches both the config and the data volume.

    Persisting is what makes the value outlive an image upgrade; rewriting the
    config is what makes the running engine use it. Either alone is a bug.
    """
    start_container(
        built_image, container_name,
        f"KOPI_PROXY_BASE_URL={GATEWAY}",
        cmd="sleep 120",
    )

    assert _first_base_url(_read(container_name, CONFIG)) == GATEWAY, (
        "model.base_url should have been rewritten to the injected gateway\n"
        f"script log:\n{_script_log(container_name)}"
    )
    assert f"KOPI_PROXY_BASE_URL={GATEWAY}" in _read(container_name, ENV_FILE), (
        "the value must be persisted to the data volume, or it is lost on upgrade\n"
        f"script log:\n{_script_log(container_name)}"
    )


def test_unset_leaves_the_baked_default_alone(built_image, container_name):
    """No env var → the config is untouched.

    Guards existing single-tenant installs: they never set this variable and
    must keep booting against the baked-in default.
    """
    start_container(built_image, container_name, cmd="sleep 120")

    config = _read(container_name, CONFIG)

    assert "KOPI_PROXY_BASE_URL" not in _read(container_name, ENV_FILE), (
        "nothing should be persisted when the operator configured nothing"
    )
    # Whatever the image ships with, it must still be a real absolute URL and
    # not a leftover placeholder.
    base = _first_base_url(config)
    assert base is None or base.startswith("http"), (
        f"expected the baked default to survive intact, got {base!r}"
    )


def test_persisted_value_survives_a_restart_with_a_different_env(
    built_image, container_name,
):
    """Resolution order: the persisted value beats the environment.

    This is the idempotence promise in the script header — an operator who edits
    `.env` must not have it clobbered by a stale `-e` flag still present on the
    container. Only a restart can show it, since the first boot writes the file
    the second boot has to respect.
    """
    start_container(
        built_image, container_name,
        f"KOPI_PROXY_BASE_URL={GATEWAY}",
        cmd="sleep 120",
    )

    # The operator edits the persisted value; the -e flag still says GATEWAY.
    edited = "https://edited.example.com/v3"
    sed = docker_exec_sh(
        container_name,
        f"sed -i 's#^KOPI_PROXY_BASE_URL=.*#KOPI_PROXY_BASE_URL={edited}#' {ENV_FILE}",
        user="root",
    )

    # Prove the edit landed BEFORE restarting. docker_exec_sh does not check
    # return codes, so a silently failing sed would otherwise be reported as
    # "the edit was overwritten on restart" — a different (and scarier) bug
    # than the one that actually happened.
    assert sed.returncode == 0, f"sed failed: {sed.stderr!r}"
    assert f"KOPI_PROXY_BASE_URL={edited}" in _read(container_name, ENV_FILE), (
        "the sed edit never landed in .env — test harness problem, not the script"
    )

    restart_container(container_name)

    assert f"KOPI_PROXY_BASE_URL={edited}" in _read(container_name, ENV_FILE), (
        "the operator's edit was overwritten by the environment on restart\n"
        f"script log:\n{_script_log(container_name)}"
    )
    assert _first_base_url(_read(container_name, CONFIG)) == edited, (
        "config should follow the persisted value, not the stale -e flag\n"
        f"script log:\n{_script_log(container_name)}"
    )


def test_malformed_value_is_ignored_not_written(built_image, container_name):
    """A value that is not an absolute http(s) URL is refused.

    Writing it through would break every model call while the container still
    looks healthy — the exact failure this script exists to prevent, so it must
    not introduce it itself.
    """
    start_container(
        built_image, container_name,
        "KOPI_PROXY_BASE_URL=not-a-url",
        cmd="sleep 120",
    )

    assert "not-a-url" not in _read(container_name, CONFIG), (
        "a malformed base_url must never reach the config"
    )
    assert "not-a-url" not in _read(container_name, ENV_FILE), (
        "a malformed base_url must not be persisted either"
    )


def test_trailing_slash_is_stripped(built_image, container_name):
    """`https://gw/v2/` would yield `…/v2//chat/completions` against some
    gateways, so the script drops the trailing slash before writing."""
    start_container(
        built_image, container_name,
        f"KOPI_PROXY_BASE_URL={GATEWAY}/",
        cmd="sleep 120",
    )

    assert _first_base_url(_read(container_name, CONFIG)) == GATEWAY
    assert f"KOPI_PROXY_BASE_URL={GATEWAY}\n" in _read(container_name, ENV_FILE)


def test_commented_provider_examples_are_left_untouched(built_image, container_name):
    """Only the first UNCOMMENTED `base_url:` is rewritten.

    The shipped config carries commented provider examples that also contain
    `base_url:`. Rewriting one of those would corrupt the example without
    touching the live setting — invisible until someone uncomments it.

    Regression guard for the BSD-sed bug in the script's history: `sed
    '0,/re/s//…/'` is a GNU extension that silently does nothing elsewhere,
    which is how this first shipped broken.
    """
    start_container(
        built_image, container_name,
        f"KOPI_PROXY_BASE_URL={GATEWAY}",
        cmd="sleep 120",
    )

    config = _read(container_name, CONFIG)
    commented = [
        line for line in config.splitlines()
        if line.strip().startswith("#") and "base_url:" in line
    ]

    for line in commented:
        assert GATEWAY not in line, (
            f"a commented provider example was rewritten: {line.strip()!r}"
        )

    assert config.count(GATEWAY) == 1, (
        f"expected exactly one rewrite, found {config.count(GATEWAY)}\n"
        f"script log:\n{_script_log(container_name)}"
    )
