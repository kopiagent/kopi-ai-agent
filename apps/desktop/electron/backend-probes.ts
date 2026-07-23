/**
 * backend-probes.ts
 *
 * Cheap "does this candidate backend actually work" checks used by
 * resolveKopiBackend (main.ts). The resolver walks a ladder of
 * candidates -- bootstrap marker, `kopi` on PATH, system Python with
 * kopi_cli installed -- and historically returned the first candidate
 * whose binary existed on disk. That assumption breaks when a user has
 * a pre-installed Python 3.11-3.13 (so findSystemPython() returns a
 * path) but no kopi_cli in its site-packages: the resolver hands back
 * a backend the spawn step can't actually run, and the user gets a
 * dead-on-arrival "ModuleNotFoundError: No module named 'kopi_cli'"
 * instead of the first-launch installer.
 *
 * These probes give the resolver a way to verify a candidate before
 * trusting it. Failure (non-zero exit, exception, timeout) means "skip
 * this rung, try the next one"; success means "spawn this for real."
 * Falling off the bottom of the ladder lands on the bootstrap-needed
 * sentinel, which is exactly what we want when nothing pre-existing
 * actually works.
 *
 * Both probes are deliberately fast and forgiving:
 *   - 5s timeout (a hung interpreter beats forever, but we still give
 *     slow disks / cold caches room to breathe)
 *   - stdio ignored (we only care about exit code; stdout/stderr are
 *     not surfaced to the user, just to recentKopiLog for forensics
 *     via the caller's catch block if it chooses)
 *   - any throw -> false (never propagate -- resolver wants a boolean)
 *
 * Kept in a standalone ts module so it can be unit-tested with
 * `node --test` without dragging in the electron runtime (same pattern
 * as bootstrap-platform.ts and hardening.ts).
 */

import { execFileSync } from 'node:child_process'

const PROBE_TIMEOUT_MS = 5000

/**
 * Return the Python snippet used to verify Kopi can import far enough to
 * launch the CLI. Kept exported for tests so dependency regressions are
 * caught without needing a real broken venv fixture.
 *
 * @returns {string}
 */
function kopiRuntimeImportProbe() {
  return 'import yaml; import dotenv; import kopi_cli.config'
}

/**
 * Return true iff the Kopi CLI module can start far enough to answer
 * ``--version``.
 *
 * Used to gate the "fallback to system Python with kopi_cli installed"
 * rung of resolveKopiBackend. Without this, a system Python 3.11-3.13
 * registered in PEP 514 makes findSystemPython() succeed regardless of
 * whether kopi_cli has actually been pip-installed into its
 * site-packages -- and the resolver returns a backend that immediately
 * dies on spawn.
 *
 * This intentionally exercises the same ``python -m kopi_cli.main`` entrypoint
 * the desktop backend will spawn. A shallow import can pass when the source tree
 * is visible on ``PYTHONPATH`` but runtime dependencies such as Rich are missing,
 * then the real backend dies before it announces a port.
 *
 * @param {string} pythonPath - Absolute path to a python.exe / python.
 * @param {object} [opts.env] - Additional environment for the probe.
 * @returns {boolean}
 */
function canImportKopiCli(pythonPath: string, opts: { env?: Record<string, string> } = {}) {
  if (!pythonPath) {
    return false
  }

  try {
    execFileSync(pythonPath, ['-m', 'kopi_cli.main', '--version'], {
      env: { ...process.env, ...(opts.env || {}) },
      stdio: 'ignore',
      timeout: PROBE_TIMEOUT_MS,
      windowsHide: true
    })

    return true
  } catch {
    return false
  }
}

/**
 * Return true iff `<kopiCommand> --version` exits 0.
 *
 * Used to gate the "existing `kopi` on PATH" rung. Without this, a
 * stale kopi.cmd shim left behind by an uninstalled pip install (or
 * a half-built venv whose `kopi` entry-point points at a deleted
 * Python) survives findOnPath() and gets selected as the backend.
 *
 * We intentionally avoid invoking the command with the dashboard args
 * here -- `--version` is the cheapest "is this binary alive" smoke
 * test that every kopi_cli entry-point has supported since 0.1.
 *
 * @param {string} kopiCommand - Resolved absolute path to a kopi
 *   executable (or an interpreter+script wrapper).
 * @param {boolean} [opts.shell] - Whether to run through a shell. For
 *   .cmd/.bat shims on Windows execFileSync needs shell:true to find
 *   the cmd interpreter; mirrors the same flag isCommandScript() drives
 *   in resolveKopiBackend.
 * @returns {boolean}
 */
/**
 * An explicit desktop backend command is a deployment contract, not a PATH
 * discovery candidate. In particular, the Nix desktop wrapper points this at
 * its immutable, matching Kopi package; it must never fall through to the
 * mutable install-script bootstrap path if a best-effort probe is slow.
 */
function shouldTrustKopiOverride(kopiOverride?: string) {
  return typeof kopiOverride === 'string' && kopiOverride.trim().length > 0
}

function verifyKopiCli(kopiCommand: string, opts?: { shell?: boolean }) {
  if (!kopiCommand) {
    return false
  }

  try {
    execFileSync(kopiCommand, ['--version'], {
      stdio: 'ignore',
      timeout: PROBE_TIMEOUT_MS,
      shell: Boolean(opts?.shell),
      windowsHide: true
    })

    return true
  } catch {
    return false
  }
}

export { canImportKopiCli, kopiRuntimeImportProbe, PROBE_TIMEOUT_MS, shouldTrustKopiOverride, verifyKopiCli }
