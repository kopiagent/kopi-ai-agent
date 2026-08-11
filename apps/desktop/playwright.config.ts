import './e2e/fix-electron-tracing'

import { defineConfig, type ReporterDescription } from '@playwright/test'

/**
 * Visual regression testing config.
 *
 * Screenshots are compared against baselines.  On `main`, baselines are
 * generated with `--update-snapshots` and cached.  On PRs, the cached
 * baselines are restored and screenshots are compared — but tests DON'T
 * fail on visual diffs (see `expectVisualSnapshot` in visual-snapshot.ts).
 * Instead, diffs are surfaced in the CI step summary and uploaded as
 * artifacts for human review.
 *
 * To update baselines after an intentional UI change:
 *   npx playwright test --update-snapshots
 */
const reporters: ReporterDescription[] = [
  ['list'],
  ['html', { open: 'never', outputFolder: 'playwright-report' }],
]

if (process.env.CI) {
  reporters.push(['json', { outputFile: 'playwright-report/results.json' }])
}

export default defineConfig({
  /* Test files live under e2e/ so they never collide with the vitest suite
   * under src/ or the node:test files under electron/. */
  testDir: './e2e',
  /* The desktop app can take a while to bootstrap on cold CI runners — 90 s
   * per test gives us headroom without masking real hangs. */
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  /* Each test gets its own worker so the Electron process is fully isolated. */
  fullyParallel: false,
  reporter: reporters,
  use: {
    /* `'on'` took an automatic screenshot at the end of EVERY test, and on CI
     * that capture hangs against an Electron page under xvfb — for the full
     * `timeout` above, at which point Playwright fails a test that had already
     * passed. That is #32. From the worker-tagged log of run 31466811433,
     * where every gap sits between `hook.afterEach.end` and the next
     * `test.start` and every gap is the timeout to the second:
     *
     *   06:55:50  hook.afterEach.end
     *   06:57:20  test.start ...          <- 90s
     *   06:57:21  hook.afterEach.end
     *   06:58:51  test.start ...          <- 90s
     *   06:58:51  hook.afterEach.end
     *   07:00:22  test.start ...          <- 91s
     *
     * The failures carry no stack and no locator, and their sole attachment
     * is `test-finished-1.png` — this screenshot. Test bodies pass in tens of
     * milliseconds throughout.
     *
     * The visual-diff pipeline does not read these: its `-diff/-actual/
     * -expected.png` come from visual-snapshot.ts and its baselines from
     * `e2e/*-snapshots`, so nothing downstream loses an image. */
    screenshot: 'only-on-failure',
    trace: { mode: 'on', screenshots: true, snapshots: true, sources: true },
    // Emulate prefers-reduced-motion: reduce so all CSS transitions and
    // animations resolve instantly. This prevents boot/connecting overlays
    // from being mid-fade when a screenshot fires, and skips JS-driven exit
    // choreography in components that check matchMedia (onboarding, connecting
    // overlay, DecodeText). Without this, screenshots capture the loading bar
    // or overlay at a transient opacity because the text-content check fires
    // before the visual transition finishes.
    contextOptions: {
      reducedMotion: 'reduce',
    },
  },
  expect: {
    toHaveScreenshot: {
      // 1% of pixels may differ — absorbs sub-pixel font rendering variance
      // between local and CI environments.
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
      caret: 'hide',
      // Per-channel threshold for "close enough" — anti-aliasing differences.
      threshold: 0.2,
    },
  },
})
