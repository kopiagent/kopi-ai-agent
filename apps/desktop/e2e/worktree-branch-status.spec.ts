import { execFileSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as path from 'node:path'

import { test, expect } from './test'

import {
  buildAppEnv,
  createSandbox,
  launchDesktop,
  writeEnvFile,
  writeMockProviderConfig,
  type MockBackendFixture,
  waitForAppReady,
} from './fixtures'
import { startMockServer } from './mock-server'

const BRANCH_NAME = 'e2e-composer-branch'

function createGitRepo(root: string): string {
  const repo = path.join(root, 'repo')

  fs.mkdirSync(repo, { recursive: true })
  execFileSync('git', ['init', '--initial-branch=main'], { cwd: repo })
  execFileSync('git', ['config', 'user.email', 'e2e@example.com'], { cwd: repo })
  execFileSync('git', ['config', 'user.name', 'Kopi E2E'], { cwd: repo })
  fs.writeFileSync(path.join(repo, 'README.md'), '# E2E repo\n', 'utf8')
  execFileSync('git', ['add', 'README.md'], { cwd: repo })
  execFileSync('git', ['commit', '-m', 'initial'], { cwd: repo })

  return repo
}

function configureRepoCwd(kopiHome: string, mockUrl: string, repo: string): void {
  writeMockProviderConfig(kopiHome, mockUrl)
  fs.appendFileSync(path.join(kopiHome, 'config.yaml'), `\nterminal:\n  cwd: ${repo}\n`, 'utf8')
  writeEnvFile(kopiHome)
}

let fixture: MockBackendFixture | null = null

test.beforeAll(async () => {
  const sandbox = createSandbox('worktree-branch-status')
  const repo = createGitRepo(sandbox.root)
  const mock = await startMockServer()

  configureRepoCwd(sandbox.kopiHome, mock.url, repo)

  const { app, page } = await launchDesktop(buildAppEnv(sandbox))
  fixture = {
    app,
    page,
    mock,
    mockUrl: mock.url,
    sandbox,
    cleanup: async () => {
      await app.close().catch(() => undefined)
      await mock.close()
      sandbox.cleanup()
    },
  }

  await waitForAppReady(fixture, 120_000)
})

test.afterAll(async () => {
  await fixture?.cleanup()
  fixture = null
})

test('creating a branch with ctrl-shift-b updates the composer git-status branch', async ({}, testInfo) => {
  const page = fixture!.page
  const codingRow = page.locator('.coding-status-bar')
  const composer = page.locator('[contenteditable="true"]').first()

  await composer.click()
  await composer.type('create a repo-backed e2e session', { delay: 2 })
  await page.keyboard.press('Enter')
  await page.waitForFunction(
    prompt => (document.querySelector('[data-slot="aui_thread-viewport"]')?.textContent ?? '').includes(prompt),
    'create a repo-backed e2e session',
    { timeout: 15_000 },
  )
  await expect(codingRow).toContainText('main')
  // The `mod+shift+b` keybind resolves `mod` to Cmd on macOS and Control
  // elsewhere (src/lib/keybinds/combo.ts: `metaKey || (ctrlKey && !IS_MAC)`),
  // so a hardcoded Control+Shift+B never fired the worktree dialog on a macOS
  // dev machine — the test was red locally while passing on the Linux runner.
  // Match the platform, as warm-resume-jitter.spec.ts already does for mod+N.
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+Shift+B' : 'Control+Shift+B')

  const branchInput = page.locator('input[placeholder="e.g. my-feature"]').first()
  await expect(branchInput).toBeVisible()
  await branchInput.fill(BRANCH_NAME)
  await page.getByRole('button', { name: 'New worktree' }).click()

  await expect(codingRow).toContainText(BRANCH_NAME, { timeout: 15_000 })
  await page.screenshot({ path: testInfo.outputPath('composer-branch-after-create.png') })
})
