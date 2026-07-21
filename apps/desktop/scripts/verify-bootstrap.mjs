// Headless driver for the REAL desktop bootstrap (bootstrap-runner.ts) against
// the local branch install.sh, into a throwaway KOPI_HOME. This exercises the
// exact wiring the packaged app uses at first launch — fetchManifest
// (install.sh --manifest) → parse → per-stage runStage (--stage --json
// --non-interactive) → marker — without launching the Electron GUI.
//
//   KOPI_API_KEY=<key> npx tsx apps/desktop/scripts/verify-bootstrap.mjs
import os from 'node:os'
import path from 'node:path'
import fs from 'node:fs'

import { runBootstrap } from '../electron/bootstrap-runner.ts'

const repoRoot = path.resolve(import.meta.dirname, '..', '..', '..')
const home = fs.mkdtempSync(path.join(os.tmpdir(), 'kopi-boot-verify-'))
const kopiHome = path.join(home, '.kopi')
const activeRoot = path.join(kopiHome, 'kopi-ai-agent')
fs.mkdirSync(kopiHome, { recursive: true })

process.env.HOME = home
process.env.KOPI_HOME = kopiHome

const stages = []
let failed = null

const result = await runBootstrap({
  installStamp: null, // no stamp → local-checkout install.sh (dev shortcut)
  activeRoot,
  sourceRepoRoot: repoRoot,
  kopiHome,
  logRoot: path.join(kopiHome, 'logs'),
  onEvent: (ev) => {
    if (ev.type === 'manifest') {
      console.log(`[manifest] ${ev.stages.map((s) => s.name).join(' → ')}`)
    } else if (ev.type === 'stage') {
      if (ev.state === 'succeeded' || ev.state === 'skipped') {
        stages.push(`${ev.name}:${ev.state}`)
        console.log(`  ✓ ${ev.name} (${ev.state})`)
      } else if (ev.state === 'failed') {
        console.log(`  ✗ ${ev.name} FAILED: ${ev.error}`)
      }
    } else if (ev.type === 'failed') {
      failed = ev.error
      console.log(`[FAILED] ${ev.error}`)
    }
  },
  writeMarker: async (m) => {
    console.log(`[marker] would write bootstrap-complete: ${JSON.stringify(m).slice(0, 80)}`)
    return m
  }
})

console.log('\n=== 结果 ===')
console.log('stages:', stages.join(', '))
console.log('ok:', result && result.ok, '| kopiHome:', kopiHome)
if (failed || !(result && result.ok)) {
  console.error('BOOTSTRAP FAILED')
  process.exit(1)
}
// Prove the installed CLI actually runs.
const kopiBin = path.join(activeRoot, 'venv', 'bin', 'kopi')
if (fs.existsSync(kopiBin)) {
  const { execFileSync } = await import('node:child_process')
  const v = execFileSync(kopiBin, ['--version'], { encoding: 'utf-8' }).trim()
  console.log('kopi --version:', v)
}
console.log('BOOTSTRAP OK')
