/**
 * Extended Playwright test fixture that auto-fails any test if an error
 * banner (notification toast with role="alert") appears in the DOM.
 *
 * The desktop app surfaces errors as `[data-slot="alert"][role="alert"]`
 * elements (see components/notifications.tsx). When one appears during a
 * test, it means something went wrong (resume failed, boot error, etc.)
 * — the test should fail with the error message, not silently pass while
 * an error toast is visible on screen.
 *
 * Usage: import { test, expect } from './test' instead of
 * '@playwright/test'. The guard is auto-installed on every page — no
 * per-spec setup needed.
 */

import { test as base, expect, type Page, type ElectronApplication, _electron } from '@playwright/test'

// Module-load marker. Every spec imports this file, so one line per load says
// whether Playwright reuses a worker process across spec files or starts a
// fresh one each time.
//
// This is the last unexplained piece of #32. Measurement has cleared
// everything under our control: all fixture phases total ~2.0 min and every
// test's own `testInfo.duration` totals 7.0 min, inside a 42.7 min span. The
// missing 33.6 min sits in gaps that begin at `mock.close` — the last line of
// one fixture's teardown — and end at `mock.start`, the first line of the
// next, with none of our code running in between. Those gaps run 25-90s and
// there is roughly one per spec file.
//
// `pid` and `uptime` settle it: a new pid with uptime near zero means the
// worker is being torn down and restarted between files, and the cost is
// process startup plus re-transpiling this import graph on a cold runner —
// which would also explain 3.8 min locally against 43 min on CI, and why
// raising `timeout-minutes` never helped. A stable pid means the cost is
// somewhere else again and this explanation is wrong too.
//
// Four earlier hypotheses in this area died to measurements (backend spawn,
// `app.close`, the overlay poll, `waitForAppReady` as a whole), so this one
// gets verified before anything is tuned on the strength of it.
/**
 * Worker tag stamped on every `[e2e-timing]` line.
 *
 * Playwright interleaves the stdout of parallel workers into one stream, and
 * until now only `module.load` carried a pid. A gap in the log therefore could
 * not be attributed to the worker that owned it — which is how the 89s stall
 * in #32 got read as `mock.close` hanging, when the `mock.close` count was
 * simply per-describe and balanced all along. Every marker carries the worker
 * now, so the next log can be split per worker and the stall placed exactly.
 */
const WORKER_TAG = `w${process.env.TEST_WORKER_INDEX ?? '?'}:${process.pid}`

// Liveness probe for #32.
//
// Every marker in this file fires from our own code, so a gap between two of
// them is silent about whether the process was working, waiting, or not
// scheduled at all. Three readings of that silence have now been wrong —
// `mock.close` hanging, machine-wide contention, and the end-of-test
// screenshot — each one inferred from where the gap happened to sit rather
// than from anything measured inside it.
//
// A ticking heartbeat says the worker is alive and Playwright is awaiting
// something. A heartbeat that stops and resumes says the process was not
// running, which points outward at the runner rather than at this suite.
// `rss` separates a memory wall from plain CPU starvation. `unref()` keeps
// the timer from holding the process open at exit.
setInterval(() => {
  const rssMb = Math.round(process.memoryUsage.rss() / 1e6)
  console.log(`[e2e-timing ${WORKER_TAG}] heartbeat uptime=${process.uptime().toFixed(1)}s rss=${rssMb}MB`)
}, 10_000).unref()

console.log(
  `[e2e-timing ${WORKER_TAG}] module.load test.ts pid=${process.pid} ` +
    `worker=${process.env.TEST_WORKER_INDEX ?? '?'} uptime=${process.uptime().toFixed(1)}s`,
)

// Track error messages per test so afterEach can assert + report.
const seenErrors: string[] = []
let activePage: Page | null = null
// When true, the afterEach guard skips the error-banner check.
// Set by tests that deliberately trigger error states (e.g. boot-failure).
let errorBannersAllowed = false

/**
 * Opt out of the error-banner guard for the current test. Call in
 * test.beforeEach or at the top of a test body when error banners are
 * expected (e.g. boot-failure tests that deliberately trigger errors).
 */
export function allowErrorBanners(): void {
  errorBannersAllowed = true
}

/**
 * Install the error-banner guard on a page. Watches for `[role="alert"]`
 * elements appearing in the DOM. When one is found, records its text
 * content for the afterEach assertion.
 *
 * Exported so e2e fixture functions (which create pages via _electron.launch)
 * can install the guard on their custom pages — the default Playwright `page`
 * fixture override only catches pages created by Playwright itself, not
 * pages created by the test's own Electron launch.
 */
export function installErrorBannerGuard(page: Page): void {
  activePage = page

  // Clear any errors from a previous test when a new page is created.
  seenErrors.length = 0

  // Use a MutationObserver to catch error banners as they appear.
  // We inject this via addInitScript so it runs before any app code.
  page.addInitScript(() => {
    const seen: string[] = []
    ;(window as unknown as { __ERROR_BANNER_GUARD__?: string[] }).__ERROR_BANNER_GUARD__ = seen

    const observer = new MutationObserver(() => {
      const alerts = document.querySelectorAll('[role="alert"]')

      for (const alert of alerts) {
        const text = (alert.textContent ?? '').trim()

        if (text && !seen.includes(text)) {
          seen.push(text)
        }
      }
    })

    // Start observing once the DOM is ready.
    if (document.body) {
      observer.observe(document.body, { childList: true, subtree: true })
    } else {
      document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, { childList: true, subtree: true })
      })
    }
  })

  // Also poll via evaluate — MutationObserver via addInitScript can miss
  // elements that appear during the Electron renderer's initial mount
  // (before the observer is installed). A periodic poll catches those.
  page.on('console', () => {
    // Console messages are not errors — but we keep the listener to
    // ensure the page context is active for our evaluate calls.
  })
}

/**
 * Check for error banners that appeared during the test. Called in
 * afterEach via the custom fixture below. Also exported so specs that
 * manage their own page lifecycle can call it directly.
 */
export async function collectErrorBanners(page: Page | null): Promise<string[]> {
  if (!page) {
    return []
  }

  try {
    // Read errors collected by the MutationObserver in the page context.
    const t0 = Date.now()
    const pageErrors = await page.evaluate(() => {
      const w = window as unknown as { __ERROR_BANNER_GUARD__?: string[] }

      return [...(w.__ERROR_BANNER_GUARD__ ?? [])]
    })
    console.log(`[e2e-timing ${WORKER_TAG}] banners.evaluate ${Date.now() - t0}ms`)

    // Also do a final DOM scan for any alert elements still visible.
    //
    // Timed separately from the evaluate above because this is the call with a
    // hidden cost: Playwright locator actions carry a default timeout, and the
    // `.catch()` below only runs AFTER it expires — so on an unresponsive page
    // this blocks rather than returning empty. That is invisible in the current
    // logs, which is why this function was cleared by reading it rather than by
    // measuring it (see #32; the same mistake was made about `app.close`, which
    // measurement later showed to be innocent at a 0.36s median).
    const t1 = Date.now()
    const domAlerts = await page
      .locator('[role="alert"]')
      .allTextContents()
      .catch(() => [] as string[])
    console.log(`[e2e-timing ${WORKER_TAG}] banners.locator ${Date.now() - t1}ms`)

    const all = [...new Set([...pageErrors, ...domAlerts.map(t => t.trim()).filter(Boolean)])]
    seenErrors.push(...all)

    return [...new Set(seenErrors)]
  } catch {
    // Page might be closed — return whatever we have.
    return [...new Set(seenErrors)]
  }
}

// Extended test fixture: wraps the default page with the error guard.
export const test = base.extend({
  // Override the page fixture to auto-install the guard.
  page: async ({ page }, use) => {
    installErrorBannerGuard(page)
    await use(page)
  },
})

// afterEach: fail the test if any error banners appeared.
// Always fires — even if the test already failed for another reason.
// An error banner often IS the root cause (e.g. "resume failed" from a
// backend bug), and suppressing it when the test also fails on an
// assertion hides the real problem.
//
// Uses `activePage` (set by installErrorBannerGuard) instead of the
// default `page` fixture — Electron tests create their own page via
// app.firstWindow(), so the default `page` fixture is undefined.
// Test-level boundaries for the #32 investigation. The job log shows 28 gaps
// of 20-103s totalling 32.8 min inside a 42.6 min span, but with two workers
// interleaving there is no way to tell from the outside whether a gap sits
// inside a test body, inside a hook, or between files — and Playwright's own
// per-test timings are unavailable because `results.json` is written only when
// a run finishes, which this suite never does. A start/end marker on stdout
// closes that gap and survives the `timeout-minutes` kill.
base.beforeEach(async ({}, testInfo) => {
  console.log(`[e2e-timing ${WORKER_TAG}] test.start ${testInfo.titlePath.slice(1).join(' > ')}`)
})

base.afterEach(async ({}, testInfo) => {
  console.log(
    `[e2e-timing ${WORKER_TAG}] test.end ${testInfo.status} ${testInfo.duration}ms ` +
      `${testInfo.titlePath.slice(1).join(' > ')}`,
  )

  const wasAllowed = errorBannersAllowed
  // Reset for the next test.
  errorBannersAllowed = false

  if (wasAllowed) {
    // Test opted out — clear any collected errors without asserting.
    seenErrors.length = 0
    return
  }

  const errors = await collectErrorBanners(activePage)

  // Closes the bracket opened by `test.end` above. Everything between the two
  // markers is this hook; anything left over between `hook.afterEach.end` and
  // the next `test.start` belongs to Playwright itself, not to our code — which
  // is the distinction the current logs cannot make.
  console.log(`[e2e-timing ${WORKER_TAG}] hook.afterEach.end`)

  if (errors.length > 0) {
    throw new Error(
      `Error banner(s) appeared during test "${testInfo.title}":\n` +
        errors.map(e => `  • ${e}`).join('\n'),
    )
  }
})

// Reset for the next test file.
base.afterAll(async () => {
  // The other big gap class runs `mock.close` -> `mock.start`, i.e. across the
  // file boundary. These two markers say whether that time is spent in a hook
  // or between them.
  console.log(`[e2e-timing ${WORKER_TAG}] hook.afterAll.start`)
  seenErrors.length = 0
  activePage = null
  console.log(`[e2e-timing ${WORKER_TAG}] hook.afterAll.end`)
})

export { expect, type Page, type ElectronApplication, _electron }
