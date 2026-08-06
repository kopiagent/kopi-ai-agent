/**
 * Shared E2E fixtures for the Kopi desktop Playwright suite.
 *
 * Two fixture modes:
 *
 *  1. `mockBackend` — starts a mock inference server, writes a config.yaml
 *     that points at it, and launches the desktop app so the full chain
 *     (electron → kopi serve → provider → inference → renderer) is
 *     exercised with a real backend but a fake LLM.
 *
 *  2. `noProvider` — launches the app with an empty config (no provider
 *     configured). The onboarding overlay should appear. Used to test the
 *     first-run flow without real credentials.
 *
 * Both modes launch the *dev* Electron app (`electron .` against the built
 * `dist/`), not the packaged binary. This avoids the multi-minute
 * `electron-builder --dir` step and matches `kopi desktop --source`. The
 * packaged-binary path is already covered by `launch.spec.ts`.
 *
 * Prerequisite: `npm run build` must have been run so that `dist/` exists.
 */

import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'

import { _electron, type ElectronApplication, type Page } from '@playwright/test'

import { startMockServer, type MockServerOptions } from './mock-server'
import { installErrorBannerGuard } from './test'

const DESKTOP_ROOT = path.resolve(import.meta.dirname, '..')
const REPO_ROOT = path.resolve(DESKTOP_ROOT, '..', '..')
const RELEASE_ROOT = path.join(DESKTOP_ROOT, 'release')

// ─── Credential stripping (matches launch.spec.ts) ──────────────────────

const CREDENTIAL_SUFFIXES: string[] = [
  '_API_KEY',
  '_TOKEN',
  '_SECRET',
  '_PASSWORD',
  '_CREDENTIALS',
  '_ACCESS_KEY',
  '_PRIVATE_KEY',
  '_OAUTH_TOKEN',
]

const CREDENTIAL_NAMES = new Set([
  'ANTHROPIC_BASE_URL',
  'ANTHROPIC_TOKEN',
  'AWS_ACCESS_KEY_ID',
  'AWS_SECRET_ACCESS_KEY',
  'AWS_SESSION_TOKEN',
  'CUSTOM_API_KEY',
  'GEMINI_BASE_URL',
  'OPENAI_BASE_URL',
  'OPENROUTER_BASE_URL',
  'OLLAMA_BASE_URL',
  'GROQ_BASE_URL',
  'XAI_BASE_URL',
])

function isCredentialEnvVar(name: string): boolean {
  if (CREDENTIAL_NAMES.has(name)) {
    return true
  }

  return CREDENTIAL_SUFFIXES.some((suffix) => name.endsWith(suffix))
}

function stripCredentials(env: Record<string, string | undefined>): Record<string, string> {
  const clean: Record<string, string> = {}

  for (const [key, value] of Object.entries(env)) {
    if (!value) {
      continue
    }

    if (isCredentialEnvVar(key)) {
      continue
    }

    clean[key] = value
  }

  return clean
}

// ─── Sandbox creation ──────────────────────────────────────────────────

export interface Sandbox {
  root: string
  kopiHome: string
  userDataDir: string
  cleanup: () => void
}

/**
 * Copy the backend's own log into `test-results/` before the sandbox is
 * deleted, so it ships with the uploaded artifact.
 *
 * Without this a boot hang is undiagnosable. `electron/main.ts` writes the
 * spawned `kopi` child's output to `$KOPI_HOME/logs/desktop.log`, and in E2E
 * `KOPI_HOME` is a temp sandbox that `sandbox.cleanup()` rm -rf's on the way
 * out — so a workflow step that collects logs after the run always finds
 * nothing. The uploaded artifacts only ever held the Playwright report and
 * traces, neither of which says why the child failed.
 *
 * Concretely: CI boots hung at 86% on `advanceBootProgress('backend.port',
 * 'Waiting for Kopi backend to launch')` — the child never announced its
 * port, and nothing recorded what it printed instead (see #32).
 *
 * Deliberately a plain file copy rather than `testInfo.attach()`: fixtures are
 * torn down from `test.afterAll`, where `test.info()` is not guaranteed to be
 * available, so an attach-based version would silently no-op in exactly the
 * runs we need it for. `test-results/` is Playwright's default `outputDir` and
 * is what the workflow uploads.
 *
 * Best-effort: never throws, so a missing log cannot mask a real failure.
 */
export function saveBackendLog(sandbox: Sandbox): void {
  try {
    const src = path.join(sandbox.kopiHome, 'logs', 'desktop.log')
    if (!fs.existsSync(src)) {
      return
    }

    const dir = path.join(DESKTOP_ROOT, 'test-results', 'backend-logs')
    fs.mkdirSync(dir, { recursive: true })
    fs.copyFileSync(src, path.join(dir, `${path.basename(sandbox.root)}.log`))
  } catch {
    // Best-effort diagnostics only.
  }
}

export function createSandbox(prefix: string): Sandbox {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), `kopi-e2e-${prefix}-${Math.random()}`))
  const kopiHome = path.join(root, 'kopi-home')
  const userDataDir = path.join(root, 'electron-user-data')

  fs.mkdirSync(kopiHome, { recursive: true })
  fs.mkdirSync(userDataDir, { recursive: true })

  // Write a fixed window-state.json so the Electron window opens at a
  // consistent size — helps with visual regression screenshots.  The
  // exact size is also enforced right before each screenshot (see
  // expectVisualSnapshot in visual-snapshot.ts) because window managers
  // may resize after launch.
  fs.writeFileSync(
    path.join(userDataDir, 'window-state.json'),
    JSON.stringify(
      { x: 0, y: 0, width: 1220, height: 800, isMaximized: false },
      null,
      2,
    ),
    'utf8',
  )

  // Pin Chromium actual-size zoom (level 0) for the suite. Fresh installs
  // ship DEFAULT_ZOOM_LEVEL at the Appearance 90% preset, but Playwright
  // click hit-testing and the committed visual baselines were calibrated at
  // 100%. Without this file every sandbox would inherit the product default
  // and fail pointer interception + snapshot diffs.
  fs.writeFileSync(
    path.join(userDataDir, 'zoom-state.json'),
    JSON.stringify({ zoomLevel: 0 }, null, 2),
    'utf8',
  )

  return {
    root,
    kopiHome,
    userDataDir,
    cleanup: () => {
      try {
        fs.rmSync(root, { recursive: true, force: true })
      } catch {
        // best-effort
      }
    },
  }
}

// ─── Config writing ─────────────────────────────────────────────────────

/**
 * Write a config.yaml that pre-configures a mock provider pointing at the
 * mock inference server. The provider is set as the active model provider so
 * the desktop app skips onboarding and boots straight to the chat UI.
 *
 * @param extraDisplayConfig optional YAML lines appended to the `display:`
 *   section, used by the interim-message e2e test.
 * @param extraConfig optional top-level YAML sections for a test scenario.
 * @param modelContextLength optional primary-model context limit.
 */
export function writeMockProviderConfig(
  kopiHome: string,
  mockUrl: string,
  extraDisplayConfig?: string,
  extraConfig?: string,
  modelContextLength?: number,
): void {
  const configPath = path.join(kopiHome, 'config.yaml')

  const displaySection = extraDisplayConfig
    ? `\ndisplay:\n${extraDisplayConfig}\n`
    : ''

  const config = `# Auto-generated by E2E test fixtures
model:
  default: mock-model
  provider: mock
${modelContextLength ? `  context_length: ${modelContextLength}\n` : ''}providers:
  mock:
    api: ${mockUrl}/v1
    name: Mock
    api_mode: chat_completions
    key_env: MOCK_API_KEY
    models:
      mock-model: {}
    context_length: 4096
${displaySection}${extraConfig ? `\n${extraConfig.trim()}\n` : ''}`

  fs.writeFileSync(configPath, config, 'utf8')
}

/**
 * Write a minimal .env with the mock API key. The key_env in config.yaml
 * references MOCK_API_KEY, so the backend resolves credentials from here.
 */
export function writeEnvFile(kopiHome: string, apiKey = 'e2e-mock-key'): void {
  const envPath = path.join(kopiHome, '.env')
  fs.writeFileSync(envPath, `MOCK_API_KEY=${apiKey}\n`, 'utf8')
}

/**
 * Write an empty config (no providers). The desktop app should show the
 * onboarding overlay because no inference provider is configured.
 */
function writeEmptyConfig(kopiHome: string): void {
  const configPath = path.join(kopiHome, 'config.yaml')
  fs.writeFileSync(configPath, '# Auto-generated by E2E test fixtures — no providers configured\n', 'utf8')
}

// ─── Env building ──────────────────────────────────────────────────────

/**
 * Build the environment for the Electron app process.
 *
 * Key env vars:
 *  - KOPI_HOME → sandbox kopi-home (isolated config/sessions)
 *  - KOPI_DESKTOP_USER_DATA_DIR → sandbox electron-user-data
 *  - KOPI_DESKTOP_IGNORE_EXISTING=1 → don't pick up `kopi` from PATH
 *    (we want the dev checkout at REPO_ROOT)
 *  - KOPI_DESKTOP_KOPI_ROOT → REPO_ROOT (dev checkout resolution)
 *  - KOPI_DESKTOP_APP_NAME → unique-ish per test (avoids single-instance lock)
 *  - XDG_RUNTIME_DIR → ensure Electron has a writable runtime dir on Linux
 */
export function buildAppEnv(sandbox: Sandbox, extra: Record<string, string> = {}): Record<string, string> {
  const clean = stripCredentials(process.env)

  // ELECTRON_RUN_AS_NODE turns the Electron binary into a plain Node, so it
  // rejects the Chromium flags Playwright's launcher passes and dies before a
  // single test runs:
  //
  //   Electron.app/Contents/MacOS/Electron: bad option: --remote-debugging-port=0
  //
  // ("bad option" is Node's wording, not Chromium's — that is the tell.)
  //
  // Nothing sets this on a CI runner, but any terminal hosted inside an
  // Electron app exports it — VS Code, Cursor, the Claude Code extension — so
  // the whole suite is unrunnable locally for most developers while being
  // perfectly green on GitHub. That asymmetry is what kept #32 from being
  // reproduced off-CI. `kopi_cli/main.py` already pops it for the
  // `kopi desktop` path (see the KOPI comment there); this is the same guard
  // for the E2E launcher. stripCredentials() does not catch it — the name
  // looks nothing like a credential.
  delete clean.ELECTRON_RUN_AS_NODE

  // XDG_RUNTIME_DIR is needed for Electron on Linux when running in a
  // headless/CI context — without it the zygote may fail to initialize.
  if (!clean.XDG_RUNTIME_DIR && process.env.XDG_RUNTIME_DIR) {
    clean.XDG_RUNTIME_DIR = process.env.XDG_RUNTIME_DIR
  }

  // DISPLAY — needed for Electron to open a window.
  if (!clean.DISPLAY && process.env.DISPLAY) {
    clean.DISPLAY = process.env.DISPLAY
  }

  return {
    ...clean,
    KOPI_HOME: sandbox.kopiHome,
    KOPI_DESKTOP_USER_DATA_DIR: sandbox.userDataDir,
    KOPI_DESKTOP_IGNORE_EXISTING: '1',
    KOPI_DESKTOP_KOPI_ROOT: REPO_ROOT,
    KOPI_DESKTOP_APP_NAME: `KopiE2E-${Date.now()}`,
    // `app.close()` in teardown must exit even when a spec leaves a turn
    // mid-flight — otherwise the quit confirmation waits on a click that no
    // one is there to make, and the worker dies on a teardown timeout.
    KOPI_DESKTOP_SKIP_QUIT_CONFIRM: '1',
    // Clear dev-server override — we want the built dist/, not a vite server.
    // The dev-server check in main.ts looks for this env var; if it's set,
    // it loads from the vite URL instead of the local file.
    ...extra,
  }
}

// ─── Electron launch ────────────────────────────────────────────────────

/**
 * Verify that the desktop app has been built (dist/ exists). Playwright
 * tests can't run without it — the Electron main process loads
 * dist/electron-main.mjs and the renderer loads dist/index.html.
 */
function assertDistBuilt(): void {
  const distDir = path.join(DESKTOP_ROOT, 'dist')
  const electronMain = path.join(distDir, 'electron-main.mjs')
  const indexHtml = path.join(distDir, 'index.html')

  if (!fs.existsSync(electronMain)) {
    throw new Error(
      `Desktop dist not built. Run 'cd apps/desktop && npm run build' first.\n` +
        `Missing: ${electronMain}`,
    )
  }

  if (!fs.existsSync(indexHtml)) {
    throw new Error(
      `Desktop dist/index.html not found. Run 'cd apps/desktop && npm run build' first.\n` +
        `Missing: ${indexHtml}`,
    )
  }
}

/**
 * Find the Electron binary. In the nix devshell, `electron` is on PATH.
 * As a fallback, use the node_modules/.bin/electron from the desktop package.
 */
export function findElectron(): string {
  // In dev mode, we use the `electron` binary directly (not the packaged app).
  // The dev:electron script in package.json does exactly this: `electron .`
  // after building. We replicate that here.
  const localElectron = path.join(REPO_ROOT, 'node_modules', 'electron', 'dist', 'electron')

  if (fs.existsSync(localElectron)) {
    return localElectron
  }

  // Fall back to PATH
  const result = spawnSync('which', ['electron'], {
    encoding: 'utf8',
  })

  if (result.status === 0 && result.stdout.trim()) {
    return result.stdout.trim()
  }

  throw new Error(
    'Electron binary not found. Run "npm install" from the repo root to install devDependencies.',
  )
}

/**
 * Launch the desktop app in dev mode.
 *
 * @param sandbox  - isolated KOPI_HOME + userData
 * @param env      - the process environment (already has KOPI_HOME etc.)
 * @returns the ElectronApplication + first Page
 */
export async function launchDesktop(
  env: Record<string, string>,
): Promise<{ app: ElectronApplication; page: Page }> {
  assertDistBuilt()

  const electronBin = findElectron()

  // `electron .` loads from the package.json `main` field
  // (dist/electron-main.mjs after build).
  const app = await _electron.launch({
    executablePath: electronBin,
    args: [
      DESKTOP_ROOT, // `electron .` — the `.` is the desktop package dir
      '--disable-gpu',
      '--no-sandbox',
    ],
    env,
    cwd: DESKTOP_ROOT,
  })

  const page = await app.firstWindow()

  // Install the error-banner guard so any [role="alert"] that appears
  // during a test is collected and surfaced in afterEach.
  installErrorBannerGuard(page)

  return { app, page }
}

/**
 * Time a fixture phase and print it to stdout.
 *
 * Deliberately `console.log` and not Playwright's own reporting: the JSON
 * reporter only writes `results.json` when the run *finishes*, and this suite
 * is killed by `timeout-minutes` before it ever does — so its timings are
 * unavailable for exactly the runs we need to explain. Anything printed to
 * stdout is already in the job log, with a GitHub timestamp on it, whether or
 * not the run survives.
 *
 * Motivation: on CI a spec file costs roughly 95s beyond the tests it runs
 * (net test time 8.4 min against a 45.3 min wall clock), while the Electron
 * process itself finishes all of its boot work in a median of 2.2s — measured,
 * not assumed, from the `[kopi +Ns]` backend logs. So the cost is in the
 * fixture around the app, and this narrows it to a phase. See #32.
 */
async function timed<T>(label: string, fn: () => Promise<T>): Promise<T> {
  const started = Date.now()

  try {
    return await fn()
  } finally {
    console.log(`[e2e-timing] ${label} ${Date.now() - started}ms`)
  }
}

/**
 * Close the app and make sure the OS process is actually gone.
 *
 * `app.close()` resolves as soon as Electron accepts the request — measured at
 * a 0.3s median on CI — but that says nothing about the process having exited.
 * Playwright's worker teardown then blocks on the child-process tree, and the
 * gap from one fixture's last line to the next worker's first is a median 76.8s
 * with a cluster sitting on 91.0/91.0/91.1s. Values that identical are a fixed
 * timeout being served, not work being done. Every timed-out run also ends with
 * the runner force-killing orphan `electron` processes, which is the same fact
 * from the other side.
 *
 * `main.ts` has real reasons to linger — `before-quit` can `preventDefault()`
 * for SSH teardown or the active-work prompt, and the spawned `kopi` backend is
 * only SIGTERM'd — so rather than change shutdown semantics for the product,
 * the harness stops waiting on them: ask nicely, give it a grace period, then
 * SIGKILL. The app under test has already been closed by that point; what is
 * being reaped is a process that outlived its purpose.
 *
 * Logs `app.exit` separately from `app.close` so the two stay distinguishable
 * — the whole reason this went unexplained for so long is that the fast one was
 * being read as proof about the slow one.
 */
async function closeAppAndReap(app: ElectronApplication): Promise<void> {
  const proc = app.process()

  await timed('app.close', () => app.close().catch(() => undefined))

  await timed('app.exit', async () => {
    const deadline = Date.now() + 5_000

    while (Date.now() < deadline) {
      if (!proc || proc.exitCode !== null || proc.signalCode !== null) {
        return
      }

      await new Promise(resolve => setTimeout(resolve, 100))
    }

    if (proc?.pid) {
      console.log(`[e2e-timing] app.exit REAPING pid=${proc.pid} — still alive 5s after close()`)

      try {
        process.kill(proc.pid, 'SIGKILL')
      } catch {
        // Already gone between the check and the signal.
      }
    }
  })
}

// ─── Public fixtures ────────────────────────────────────────────────────

export interface MockBackendFixture {
  app: ElectronApplication
  page: Page
  mock: Awaited<ReturnType<typeof startMockServer>>
  mockUrl: string
  sandbox: Sandbox
  cleanup: () => Promise<void>
}

export interface MockBackendOptions {
  /**
   * Optional YAML lines to inject under the `display:` section of the
   * generated config.yaml. Used by the interim-message e2e test to toggle
   * `display.interim_assistant_messages`.
   */
  extraDisplayConfig?: string
  /** Additional top-level config.yaml sections for an E2E scenario. */
  extraConfig?: string
  /** Override the mock model's context window for compression scenarios. */
  modelContextLength?: number
}

/**
 * Set up a full mock-backend E2E environment:
 *   1. Start the mock inference server
 *   2. Create a sandbox with config.yaml pointing at it
 *   3. Launch the desktop app
 *   4. Return handles for test interaction
 */
export interface MockBackendOptions {
  mockServer?: MockServerOptions
}

export async function setupMockBackend(options: MockBackendOptions = {}): Promise<MockBackendFixture> {
  // 1. Start mock server
  const mock = await timed('mock.start', () => startMockServer(options.mockServer))

  // 2. Create sandbox + write config
  const sandbox = createSandbox('mock')
  writeMockProviderConfig(
    sandbox.kopiHome,
    mock.url,
    options.extraDisplayConfig,
    options.extraConfig,
    options.modelContextLength,
  )
  writeEnvFile(sandbox.kopiHome)

  // 3. Build env + launch
  const env = buildAppEnv(sandbox)
  const { app, page } = await timed('app.launch', () => launchDesktop(env))

  return {
    app,
    page,
    mock,
    mockUrl: mock.url,
    sandbox,
    cleanup: async () => {
      await closeAppAndReap(app)
      await timed('mock.close', () => mock.close())
      saveBackendLog(sandbox)
      sandbox.cleanup()
    },
  }
}

export interface NoProviderFixture {
  app: ElectronApplication
  page: Page
  sandbox: Sandbox
  cleanup: () => Promise<void>
}

/**
 * Launch the app with no provider configured. The onboarding overlay should
 * appear because there's no inference provider in config.yaml.
 */
export async function setupNoProvider(): Promise<NoProviderFixture> {
  const sandbox = createSandbox('noprovider')
  writeEmptyConfig(sandbox.kopiHome)

  const env = buildAppEnv(sandbox)
  const { app, page } = await launchDesktop(env)

  return {
    app,
    page,
    sandbox,
    cleanup: async () => {
      await closeAppAndReap(app)
      saveBackendLog(sandbox)
      sandbox.cleanup()
    },
  }
}

export interface DeadBackendFixture {
  app: ElectronApplication
  page: Page
  sandbox: Sandbox
  cleanup: () => Promise<void>
}

export interface DeadBackendOptions {
  /**
   * When true, inject a fake boot error via KOPI_DESKTOP_BOOT_FAKE_ERROR
   * so the backend resolution itself "fails" with a controlled error message.
   * This is the only reliable way to trigger BootFailureOverlay in dev mode
   * (the real backend always resolves via SOURCE_REPO_ROOT).
   */
  fakeError?: boolean
}

/**
 * Launch the app with a provider pointing at a dead endpoint (port 1, which
 * nothing listens on). By default the backend still boots (`kopi serve`
 * starts fine — the dead endpoint only matters at chat time). Pass
 * `{ fakeError: true }` to inject a fake boot failure, triggering the
 * BootFailureOverlay.
 */
export async function setupDeadBackend(options: DeadBackendOptions = {}): Promise<DeadBackendFixture> {
  const sandbox = createSandbox('dead')
  const configPath = path.join(sandbox.kopiHome, 'config.yaml')
  fs.writeFileSync(
    configPath,
    `# Auto-generated by E2E test fixtures — dead provider
model:
  default: mock-model
  provider: mock
providers:
  mock:
    api: http://127.0.0.1:1/v1
    name: Mock
    api_mode: chat_completions
    key_env: MOCK_API_KEY
    models:
      mock-model: {}
    context_length: 4096
`,
    'utf8',
  )
  writeEnvFile(sandbox.kopiHome)

  const env = buildAppEnv(sandbox, options.fakeError ? { KOPI_DESKTOP_BOOT_FAKE_ERROR: 'Failed to connect to Kopi backend: connection refused' } : {})
  const { app, page } = await launchDesktop(env)

  return {
    app,
    page,
    sandbox,
    cleanup: async () => {
      await closeAppAndReap(app)
      saveBackendLog(sandbox)
      sandbox.cleanup()
    },
  }
}

// ─── Packaged-binary fixture ───────────────────────────────────────────

/**
 * Resolve the packaged Electron binary path, per-platform, matching
 * electron-builder's output layout under release/.
 */
function resolvePackagedBinaryPath(): string {
  if (process.platform === 'win32') {
    return path.join(RELEASE_ROOT, 'win-unpacked', 'Kopi.exe')
  }

  if (process.platform === 'darwin') {
    const arch = process.arch === 'arm64' ? 'arm64' : 'x64'

    return path.join(RELEASE_ROOT, `mac-${arch}`, 'Kopi.app', 'Contents', 'MacOS', 'Kopi')
  }

  return path.join(RELEASE_ROOT, 'linux-unpacked', 'kopi')
}

export const PACKAGED_BINARY_PATH = resolvePackagedBinaryPath()

export function packagedBinaryExists(): boolean {
  return fs.existsSync(PACKAGED_BINARY_PATH)
}

export interface PackagedAppFixture {
  app: ElectronApplication
  page: Page
  sandbox: Sandbox
  cleanup: () => Promise<void>
}

/**
 * Launch the *packaged* Electron binary (from `npm run pack` →
 * `electron-builder --dir`) with `BOOT_FAKE=1` so it simulates boot
 * progress without spawning a real Kopi backend.
 *
 * Uses the same sandbox isolation (credential stripping, isolated
 * KOPI_HOME + userData, unique app name) as the dev-mode fixtures.
 *
 * Skips if the packaged binary doesn't exist — run `npm run pack` first.
 */
export async function setupPackagedApp(): Promise<PackagedAppFixture> {
  if (!packagedBinaryExists()) {
    throw new Error(
      `Built app binary not found: ${PACKAGED_BINARY_PATH}. Run 'npm run pack' first.`,
    )
  }

  const sandbox = createSandbox('packaged')

  // Build the sandbox env using the shared helpers, then add the
  // packaged-binary-specific overrides.
  const env = buildAppEnv(sandbox, {
    // Fake boot: simulates progress steps without spawning the real backend.
    KOPI_DESKTOP_BOOT_FAKE: '1',
    KOPI_DESKTOP_BOOT_FAKE_STEP_MS: '120',
  })

  // Clear dev-server + kopi-root overrides — the packaged binary
  // should use its own bundled renderer, not the dev checkout.
  delete (env as Record<string, string | undefined>).KOPI_DESKTOP_DEV_SERVER
  delete (env as Record<string, string | undefined>).KOPI_DESKTOP_KOPI
  delete (env as Record<string, string | undefined>).KOPI_DESKTOP_KOPI_ROOT

  const app = await _electron.launch({
    executablePath: PACKAGED_BINARY_PATH,
    args: ['--disable-gpu', '--no-sandbox'],
    env,
  })

  const page = await app.firstWindow()
  installErrorBannerGuard(page)

  return {
    app,
    page,
    sandbox,
    cleanup: async () => {
      await closeAppAndReap(app)
      saveBackendLog(sandbox)
      sandbox.cleanup()
    },
  }
}

// ─── Wait helpers ──────────────────────────────────────────────────────

/**
 * Wait for the desktop app to finish booting and show the main chat UI.
 *
 * The boot overlay disappears when `completeDesktopBoot()` fires in the
 * renderer — at that point the gateway is open, config is loaded, and
 * sessions are loaded. We detect this by waiting for the boot/connecting
 * overlay to become invisible and the main app shell to be present.
 *
 * Two things must both be true before we return:
 *  1. The composer (chat input) is visible — it's disabled until the
 *     gateway is open.
 *  2. No full-screen overlay (onboarding Preparing, connecting overlay,
 *     boot-failure) covers the viewport center. The composer can be
 *     "visible" in Playwright's eyes (non-zero bounding box, not
 *     display:none) even when a z-1300+ overlay is painted on top of it,
 *     so checking the composer alone catches the app mid-boot at ~92%
 *     with the loading bar still showing.
 */
export async function waitForAppReady(fixture: MockBackendFixture | NoProviderFixture | DeadBackendFixture, timeoutMs = 60_000): Promise<void> {
  const { page, app } = fixture

  // Wait for the composer to exist in the DOM (not necessarily interactive yet).
  await timed('ready.composer', () =>
    page.waitForSelector('textarea, [contenteditable="true"]', {
      state: 'attached',
      timeout: timeoutMs,
    }),
  )

  // Now poll until no full-screen overlay covers the viewport center.
  // elementFromPoint returns the topmost element at a point — if it's part
  // of a fixed inset-0 overlay (onboarding/connecting/boot-failure), the
  // app isn't ready yet.
  await timed('ready.overlay', () => page.waitForFunction(
    () => {
      const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2)

      if (!el) {
        return false
      }

      // Walk up to the nearest positioned ancestor — overlays are
      // `position: fixed; inset: 0`. If the hit element or an ancestor
      // is a full-viewport fixed overlay, we're still covered.
      let node: Element | null = el
      while (node) {
        const cs = window.getComputedStyle(node)

        if (cs.position === 'fixed') {
          const rect = node.getBoundingClientRect()

          if (rect.left <= 0 && rect.top <= 0 && rect.right >= window.innerWidth && rect.bottom >= window.innerHeight) {
            return false
          }
        }

        node = node.parentElement
      }

      return true
    },
    undefined,
    { timeout: timeoutMs },
  ).catch(async (error: unknown) => {
    // This poll is where the CI suite actually burns its wall clock: 29 waits
    // of 80-101s against 8.4 min of real test time (#32). The backend is ready
    // in a median of 2.2s and every fixture phase is sub-second, so whatever
    // sits over the viewport centre is the whole cost — and the failure
    // screenshot shows a fully-loaded app that merely looks washed out, i.e. a
    // near-transparent cover rather than a boot overlay.
    //
    // Naming that element is a one-line answer that no artifact currently
    // carries: traces come back unfinalised because the kill lands mid-write,
    // and `results.json` is only written when the run completes.
    const chain = await page.evaluate(() => {
      const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2)
      const out: string[] = []
      let node: Element | null = el

      while (node && out.length < 8) {
        const cs = window.getComputedStyle(node)
        const r = node.getBoundingClientRect()

        out.push(
          `<${node.tagName.toLowerCase()} class="${node.className}" ` +
            `pos=${cs.position} opacity=${cs.opacity} pointer=${cs.pointerEvents} ` +
            `z=${cs.zIndex} rect=${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}>`,
        )
        node = node.parentElement
      }

      return { chain: out, viewport: `${window.innerWidth}x${window.innerHeight}` }
    }).catch(() => null)

    console.log(`[e2e-timing] waitForAppReady BLOCKED viewport=${chain?.viewport ?? '?'}`)
    for (const entry of chain?.chain ?? ['(could not read the DOM)']) {
      console.log(`[e2e-timing]   ${entry}`)
    }

    throw error
  }))

  // On Electron 40.x, ready-to-show may never fire (electron/electron#51972)
  // and the window stays hidden even though the DOM is rendered. The main
  // process has a TEST_WORKER_INDEX-gated fallback that force-shows the
  // window, but the DOM can be ready before that fires. Poll until the
  // window is actually visible so interactions (click, screenshot) don't
  // hit a hidden surface.
  if (app) {
    await timed('ready.visible', async () => {
      const deadline = Date.now() + timeoutMs

      while (Date.now() < deadline) {
        const visible = await app.evaluate(({ BrowserWindow }) => {
          const w = BrowserWindow.getAllWindows()[0]

          return w ? w.isVisible() : false
        }).catch(() => false)

        if (visible) {return}

        await page.waitForTimeout(500)
      }

      // Silent expiry, unlike the two waits above — it just falls through to
      // the test with a hidden window. Say so, or a 60s stall here reads as
      // the test itself being slow.
      console.log('[e2e-timing] ready.visible EXPIRED — window never reported visible')
    })
  }
}

/**
 * Wait for the onboarding overlay to appear (no provider configured).
 */
export async function waitForOnboarding(page: Page, timeoutMs = 60_000): Promise<void> {
  // The onboarding overlay contains a heading with "Choose your provider"
  // or similar text. We look for any text that indicates the picker.
  await page.waitForFunction(
    () => {
      const root = document.getElementById('root')

      if (!root) {
        return false
      }

      const text = root.textContent ?? ''

      return (
        text.includes('provider') ||
        text.includes('Provider') ||
        text.includes('Choose') ||
        text.includes('API key') ||
        text.includes('Sign in')
      )
    },
    undefined,
    { timeout: timeoutMs },
  )
}

/**
 * Wait for the boot failure overlay to appear.
 */
export async function waitForBootFailure(page: Page, timeoutMs = 60_000): Promise<void> {
  await page.waitForFunction(
    () => {
      // Boot failure is terminal: the backend gave up. The renderer shows
      // either BootFailureOverlay (z-1400, with Retry/Repair buttons) or
      // falls back to the onboarding picker (z-1300) as a recovery path.
      // We wait for the failure dialog itself — the Preparing component may
      // still paint its progress bar (recolored red) underneath the overlay,
      // which is harmless.
      const text = document.body.textContent ?? ''

      // BootFailureOverlay buttons.
      const hasFailureUI =
        text.includes('Retry') ||
        text.includes('Repair') ||
        text.includes('Use local gateway') ||
        text.includes('Connection settings')

      // The error toast / notification that fires on failDesktopBoot().
      const hasErrorToast = text.includes('Desktop boot failed')

      return hasFailureUI || hasErrorToast
    },
    undefined,
    { timeout: timeoutMs },
  )
}
