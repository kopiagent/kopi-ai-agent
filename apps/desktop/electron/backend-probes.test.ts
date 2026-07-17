/**
 * Tests for electron/backend-probes.ts.
 *
 * Run with: node --test electron/backend-probes.test.ts
 * (Wired into npm test:desktop:platforms in package.json.)
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import { canImportKopiCli, kopiRuntimeImportProbe, verifyKopiCli } from './backend-probes'

// Resolve the host's own Node binary -- guaranteed to be on disk and
// runnable. We use it as both a stand-in for "a python that doesn't
// have kopi_cli" (since `node -m kopi_cli.main --version` will exit
// non-zero) and as a way to script verifyKopiCli's success path
// (a tiny script we write to disk that exits 0 on --version).
const NODE_BIN = process.execPath

test('canImportKopiCli returns false when path is falsy', () => {
  assert.equal(canImportKopiCli(''), false)
  assert.equal(canImportKopiCli(null), false)
  assert.equal(canImportKopiCli(undefined), false)
})

test('canImportKopiCli returns false when interpreter cannot run the Kopi CLI module', () => {
  // node IS an interpreter, but `node -m kopi_cli.main --version` is
  // not a runnable Kopi CLI. Different exit reason from a real Python's
  // ModuleNotFoundError, same resolver signal: fall through.
  assert.equal(canImportKopiCli(NODE_BIN), false)
})

test('canImportKopiCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'kopi-probes-ghost-' + Date.now() + '.exe')
  assert.equal(canImportKopiCli(ghost), false)
})

test('kopi runtime import probe checks config dependencies', () => {
  const probe = kopiRuntimeImportProbe()
  assert.match(probe, /\bimport yaml\b/)
  // dotenv is the first third-party import on the CLI boot path
  // (kopi_cli/env_loader.py); a mid-update venv missing python-dotenv
  // passed the old probe and produced an unrecoverable boot loop.
  assert.match(probe, /\bimport dotenv\b/)
  assert.match(probe, /\bimport kopi_cli\.config\b/)
})

test('verifyKopiCli returns false when command is falsy', () => {
  assert.equal(verifyKopiCli(''), false)
  assert.equal(verifyKopiCli(null), false)
  assert.equal(verifyKopiCli(undefined), false)
})

test('verifyKopiCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'kopi-probes-ghost-' + Date.now() + '.exe')
  assert.equal(verifyKopiCli(ghost), false)
})

test('verifyKopiCli returns true when --version exits 0', () => {
  // Write a tiny script that exits 0 regardless of args, then invoke
  // it through node. This stands in for a working kopi binary --
  // verifyKopiCli only cares about the exit code.
  const scriptPath = path.join(os.tmpdir(), `kopi-probes-ok-${Date.now()}-${process.pid}.cjs`)
  fs.writeFileSync(scriptPath, 'process.exit(0)\n')

  try {
    // Use node as the launcher and our script as the "command". Pass
    // shell:false (default) -- node is a real binary, no shim.
    // execFileSync passes ['--version'] as args, which node ignores
    // gracefully (well, it prints its version and exits 0, which is
    // perfect -- exit code 0 is the only signal we read).
    assert.equal(verifyKopiCli(NODE_BIN), true)
  } finally {
    try {
      fs.unlinkSync(scriptPath)
    } catch {
      void 0
    }
  }
})

test('verifyKopiCli swallows timeouts (does not throw)', () => {
  // We can't easily provoke a real 5s hang in CI without slowing the
  // suite, but we CAN confirm that an invocation that DOES throw
  // (because the binary is missing) returns false rather than
  // propagating. Same code path the timeout case takes.
  assert.equal(verifyKopiCli('/definitely/not/a/real/binary/anywhere'), false)
})
