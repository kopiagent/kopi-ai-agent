"""Harness: dashboard opt-in via KOPI_DASHBOARD.

Today (tini): dashboard starts once when KOPI_DASHBOARD=1; if it crashes
it stays dead. After Phase 2 (s6): dashboard starts once; if it crashes
it is restarted under supervision. The restart-after-crash test lives in
Phase 2 Task 2.5; this file only locks the opt-in surface (which must
not change between tini and s6).

Every ``docker exec`` here runs as the unprivileged ``kopi`` user
(via :func:`docker_exec`/:func:`docker_exec_sh` in conftest), matching
the realistic runtime context. See the conftest module docstring.
"""
from __future__ import annotations

import json
import time

from tests.docker.conftest import (
    docker_exec,
    docker_exec_sh,
    restart_container,
    start_container,
    wait_for_docker_logs,
)


def test_dashboard_not_running_by_default(
    built_image: str, container_name: str,
) -> None:
    """Without KOPI_DASHBOARD, no dashboard process should be running."""
    start_container(built_image, container_name, cmd="sleep 60")
    r = docker_exec(container_name, "pgrep", "-f", "kopi dashboard")
    # pgrep exits non-zero when no match found
    assert r.returncode != 0, (
        "Dashboard should not be running without KOPI_DASHBOARD"
    )












# ---------------------------------------------------------------------------
# OAuth auth-gate behaviour — regression guard for the dashboard-insecure
# auto-injection bug. Pre-fix, the s6 run script appended `--insecure`
# whenever `KOPI_DASHBOARD_HOST` was non-loopback, silently disabling
# the OAuth gate on every container-deployed dashboard. The matching
# static-text guard lives in tests/test_docker_home_override_scripts.py;
# this is the behavioural end-to-end check.
# ---------------------------------------------------------------------------


def _http_probe(
    container: str,
    path: str,
    *,
    deadline_s: float = 60.0,
) -> tuple[int, str]:
    """Poll ``http://127.0.0.1:9119<path>`` from inside the container.

    Returns ``(status_code, body)`` as soon as the dashboard answers any
    HTTP response — 200, 401, 503, anything. The image doesn't ship
    ``curl`` but the venv's stdlib ``urllib`` is good enough; we use a
    proper ``try``/``except`` to intercept ``HTTPError`` because
    ``urlopen`` raises on 4xx/5xx, and we treat those as legitimate
    responses (the OAuth gate's 401 IS the success signal for the
    gate-engaged test).

    Connection errors (uvicorn still starting, fail-closed exited) keep
    the poll loop running until ``deadline_s`` elapses.

    The probe Python program is fed over stdin (``python -``) rather
    than ``python -c`` so we can use proper multi-line syntax with
    ``try``/``except`` blocks without escaping hell.

    Raises ``AssertionError`` on timeout.
    """
    py_program = f"""\
import urllib.request, urllib.error
req = urllib.request.Request("http://127.0.0.1:9119{path}")
try:
    r = urllib.request.urlopen(req, timeout=5)
    print(r.status)
    print(r.read().decode(), end="")
except urllib.error.HTTPError as h:
    print(h.code)
    print(h.read().decode(), end="")
"""
    # Feed the program over stdin via a heredoc so docker_exec_sh's
    # single bash string stays clean. The 'PY' delimiter is quoted to
    # disable shell expansion inside the heredoc body.
    probe = (
        "/opt/kopi/.venv/bin/python - <<'PY'\n"
        f"{py_program}"
        "PY"
    )
    end = time.monotonic() + deadline_s
    last_err = ""
    while time.monotonic() < end:
        r = docker_exec_sh(container, probe, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.split("\n", 1)
            try:
                status = int(lines[0].strip())
                body = lines[1] if len(lines) > 1 else ""
                return status, body
            except (ValueError, IndexError) as exc:
                last_err = f"parse: {exc!r} / stdout={r.stdout!r}"
        else:
            last_err = f"rc={r.returncode} stderr={r.stderr!r}"
        time.sleep(0.5)
    raise AssertionError(
        f"Probe of {path} never returned HTTP within {deadline_s}s; "
        f"last error: {last_err}"
    )


def test_dashboard_oauth_gate_engages_on_non_loopback_bind(
    built_image: str, container_name: str,
) -> None:
    """The s6 dashboard run script must NOT auto-add ``--insecure`` when the
    dashboard binds to ``0.0.0.0``. The OAuth auth gate engages on its own
    when a ``DashboardAuthProvider`` is registered (the bundled nous
    provider activates whenever ``KOPI_DASHBOARD_OAUTH_CLIENT_ID`` is
    set).

    Regression guard for the wildcard-subdomain rollout where every
    portal-provisioned agent binds ``0.0.0.0`` and relies on the OAuth
    gate to authenticate browser callers. Before this fix, the run script
    flipped ``--insecure`` on for any non-loopback bind, which routed
    ``start_server`` straight back into the legacy ``allow_public=True``
    branch and disabled the gate every time.

    We verify two independent observable consequences of the gate being
    on:

    1. ``/api/auth/providers`` (publicly reachable through the gate so
       the login page can bootstrap) returns 200 with ``nous`` in the
       provider list — proves the bundled provider registered.
    2. ``/api/sessions`` (a gated route under both the legacy
       ``_SESSION_TOKEN`` middleware and the OAuth gate) returns 401
       to an unauthenticated caller — proves the OAuth gate is actively
       intercepting browser traffic. We deliberately probe a gated route
       here rather than ``/api/status``: status sits in the shared
       ``PUBLIC_API_PATHS`` allowlist (portal liveness probe target) and
       responds 200 without a cookie under both gates, so it cannot
       distinguish "gate on" from "gate off".
    """
    start_container(
        built_image, container_name,
        "KOPI_DASHBOARD=1",
        "KOPI_DASHBOARD_HOST=0.0.0.0",
        "KOPI_DASHBOARD_OAUTH_CLIENT_ID=agent:test-instance",
        cmd="sleep 120",
    )

    # (1) Provider registry visible via the public bootstrap endpoint.
    status_code, body = _http_probe(container_name, "/api/auth/providers")
    assert status_code == 200, (
        f"/api/auth/providers should return 200 when a provider is "
        f"registered; got {status_code} body={body!r}"
    )
    payload = json.loads(body)
    provider_names = [p.get("name") for p in payload.get("providers", [])]
    assert "nous" in provider_names, (
        "Bundled dashboard_auth/nous provider should register when "
        f"KOPI_DASHBOARD_OAUTH_CLIENT_ID is set. Got: {payload!r}"
    )

    # (2) A gated route (``/api/sessions``) returns 401 to an
    #     unauthenticated caller — the OAuth gate is intercepting.
    status_code, body = _http_probe(container_name, "/api/sessions")
    assert status_code == 401, (
        "OAuth gate must intercept gated /api/* routes on 0.0.0.0 bind "
        "when a provider is registered and KOPI_DASHBOARD_INSECURE "
        f"is unset. Got: status={status_code} body={body!r}"
    )

    # (3) ``/api/status`` remains 200 under the gate — it's in the shared
    #     ``PUBLIC_API_PATHS`` allowlist so NAS's wildcard-subdomain
    #     liveness probe (``fly-provider.ts`` ``getInstanceRuntimeStatus``)
    #     can reach it without a cookie. Regression guard: this allowlist
    #     drifted once already and surfaced every healthy agent as
    #     STARTING/down in the portal UI.
    status_code, body = _http_probe(container_name, "/api/status")
    assert status_code == 200, (
        "/api/status must remain publicly reachable under the OAuth gate "
        "— the portal uses it as the wildcard-subdomain liveness probe. "
        f"Got: status={status_code} body={body!r}"
    )
    status = json.loads(body)
    assert status.get("auth_required") is True, (
        "/api/status must report auth_required=True when the OAuth gate "
        f"is engaged so the SPA/portal can distinguish modes. Got: {status!r}"
    )


def test_dashboard_insecure_env_var_no_longer_bypasses_gate(
    built_image: str, container_name: str,
) -> None:
    """``KOPI_DASHBOARD_INSECURE=1`` NO LONGER disables the auth gate
    (June 2026 hardening) — asserted against KOPI's image, where a provider
    is ALWAYS present.

    Upstream proves this by the fail-closed path: with no provider
    registered, ``start_server`` raises SystemExit before binding, so
    nothing answers. That premise cannot hold here. ``docker/cont-init.d/
    04-dashboard-auth`` is KOPI-only and unconditionally seeds a basic-auth
    credential at boot (tier 3 falls back to the image's baked default), so
    ``list_providers()`` is never empty and the dashboard always binds.

    Same security property, observed the other way round: the gate must
    still intercept gated routes even though ``--insecure`` was passed. That
    is a STRONGER statement than "the server didn't start" — it proves the
    escape hatch is closed rather than proving nothing was listening.

    Do NOT probe ``/api/status`` to decide this. It sits in the shared
    ``PUBLIC_API_PATHS`` allowlist and answers 200 with or without the gate,
    so it cannot tell "gate on" from "gate off" — see the note in
    ``test_dashboard_oauth_gate_engages_on_non_loopback_bind`` above. The
    original probe did exactly that, over a 12s ``curl`` window: on the
    heavily contended amd64 runner the container needed ~300s to come up, so
    the probe never connected and the assertion passed without testing
    anything. It only failed once arm64 came up fast enough to answer.
    ``_http_probe`` waits up to 60s for a real HTTP response, which is what
    keeps this honest.
    """
    start_container(
        built_image, container_name,
        "KOPI_DASHBOARD=1",
        "KOPI_DASHBOARD_HOST=0.0.0.0",
        "KOPI_DASHBOARD_INSECURE=1",
        cmd="sleep 120",
    )

    # (1) The seeded basic provider is what keeps the gate satisfied. Assert
    #     it explicitly: if 04-dashboard-auth ever stops seeding, this fails
    #     here with a clear cause instead of silently changing what (2) means.
    status_code, body = _http_probe(container_name, "/api/auth/providers")
    assert status_code == 200, (
        f"/api/auth/providers should answer 200 once the dashboard binds; "
        f"got {status_code} body={body!r}"
    )
    provider_names = [
        p.get("name") for p in json.loads(body).get("providers", [])
    ]
    assert "basic" in provider_names, (
        "docker/cont-init.d/04-dashboard-auth must seed the bundled basic "
        f"provider at boot. Got: {provider_names!r}"
    )

    # (2) The actual assertion: --insecure did NOT reopen the hole. A gated
    #     route still answers 401 to an unauthenticated caller.
    status_code, body = _http_probe(container_name, "/api/sessions")
    assert status_code == 401, (
        "KOPI_DASHBOARD_INSECURE=1 must NOT bypass dashboard auth on a "
        "public bind — the unauthenticated escape hatch is gone. Gated "
        f"/api/sessions returned status={status_code} body={body!r}"
    )

    # (3) And the server reports the gate as engaged, so the SPA/portal
    #     cannot be tricked into rendering the unauthenticated layout.
    status_code, body = _http_probe(container_name, "/api/status")
    assert status_code == 200, (
        f"/api/status must stay publicly reachable; got {status_code}"
    )
    status = json.loads(body)
    assert status.get("auth_required") is True, (
        "/api/status must report auth_required=True with --insecure on a "
        f"non-loopback bind. Got: {status!r}"
    )


# ---------------------------------------------------------------------------
# tier-3 credential seeding — regression guards for the shared-default hole.
# Before this, 04-dashboard-auth fell back to the literal `kopi-admin`, so
# every instance of the published image sat behind one publicly-known password
# on a dashboard that binds 0.0.0.0 by default. tier 3 now generates a
# per-instance password on first boot and prints it once to the container log.
#
# Both tests wait on docker logs rather than reading files immediately:
# start_container's readiness signal (profile=default) is written by
# 02-reconcile-profiles, which sorts BEFORE 04 — the same cont-init race that
# produced test_model_base_url.py's impossible-looking first CI round.
# ---------------------------------------------------------------------------


def test_generated_password_is_per_instance_and_logged_once(
    built_image: str, container_name: str,
) -> None:
    start_container(built_image, container_name, cmd="sleep 240")

    logs = wait_for_docker_logs(
        container_name, "generated dashboard password:", deadline_s=180,
    )

    line = next(
        ln for ln in logs.splitlines() if "generated dashboard password:" in ln
    )
    password = line.split("generated dashboard password:", 1)[1].split()[0]

    assert password != "kopi-admin", (
        "tier 3 must generate, not fall back to the old shared literal"
    )
    assert len(password) >= 12, f"generated password too short: {password!r}"

    env = docker_exec_sh(container_name, "cat /opt/data/.env").stdout
    assert "KOPI_DASHBOARD_BASIC_AUTH_USERNAME=" in env
    assert "KOPI_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$" in env
    assert password not in env, (
        "only the scrypt hash may be persisted, never the plaintext"
    )

    # The hash must actually verify against the logged password — otherwise
    # the operator copies a value from the logs that the dashboard rejects.
    check = docker_exec_sh(
        container_name,
        "PYTHONPATH=/opt/kopi /opt/kopi/.venv/bin/python - <<'PY'\n"
        "from plugins.dashboard_auth.basic import _verify_password\n"
        "import re\n"
        "env = open('/opt/data/.env').read()\n"
        "hash_ = re.search(r'^KOPI_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=(.+)$', env, re.M).group(1)\n"
        f"print(_verify_password({password!r}, hash_))\n"
        "PY",
    )
    assert check.stdout.strip() == "True", (
        f"logged password does not verify against the persisted hash: "
        f"{check.stdout!r} {check.stderr!r}"
    )

    # tier 1 idempotence: a restart must neither regenerate nor re-log the
    # password. docker logs accumulate across restarts, so after boot #2 the
    # "already present" line exists and "generated" still appears exactly once.
    restart_container(container_name)
    logs = wait_for_docker_logs(
        container_name, "dashboard credential already present", deadline_s=180,
    )
    assert logs.count("generated dashboard password:") == 1, (
        "the generated password must be logged exactly once, on first boot"
    )


def test_env_password_override_beats_generation(
    built_image: str, container_name: str,
) -> None:
    """tier 2: an injected password is used as-is — nothing is generated,
    nothing plaintext lands in .env."""
    start_container(
        built_image, container_name,
        "KOPI_DASHBOARD_BASIC_AUTH_PASSWORD=operator-chosen-pw",
        cmd="sleep 120",
    )

    logs = wait_for_docker_logs(
        container_name, "seeded dashboard credential", deadline_s=180,
    )

    assert "source=env" in logs, "injected password should be tier 2 (source=env)"
    assert "generated dashboard password:" not in logs, (
        "tier 3 generation must not run when a password is injected"
    )

    env = docker_exec_sh(container_name, "cat /opt/data/.env").stdout
    assert "operator-chosen-pw" not in env, (
        "the injected plaintext must never be persisted — only its hash"
    )
    assert "KOPI_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$" in env
