/**
 * after-pack.mjs — electron-builder afterPack hook.
 *
 * Stamps the Kopi icon + identity onto the packed Windows Kopi.exe via
 * rcedit (delegated to set-exe-identity.mjs). This runs for EVERY packed build
 * — first install, `kopi desktop`, the installer's --update rebuild, and a
 * dev's manual `npm run pack` — so the branded exe can never silently revert
 * to the stock "Electron" icon/name (the bug when the stamp lived only in
 * install.ps1, which the update path doesn't use).
 *
 * Windows-only: rcedit edits PE resources, irrelevant on macOS/Linux where the
 * app identity comes from the bundle Info.plist / desktop entry. Best-effort:
 * a stamp failure must never fail an otherwise-good build (worst case is the
 * stock icon, not a broken app), so we log and resolve rather than throw.
 *
 * electron-builder passes a context with:
 *   - electronPlatformName: 'win32' | 'darwin' | 'linux'
 *   - appOutDir:            the unpacked app directory for this target
 *   - packager.appInfo.productFilename: the exe basename (e.g. 'Kopi')
 */

import { execFileSync } from 'node:child_process'
import path from 'node:path'

import { stampExeIdentity } from './set-exe-identity.mjs'

// Ad-hoc sign the packed .app when no real Developer ID is available.
// electron-builder SKIPS signing entirely without an identity — but an
// unsigned arm64 bundle will not launch on Apple Silicon at all, and a
// downloaded copy reports the misleading "Kopi is damaged" Gatekeeper error.
// `codesign --sign -` (ad-hoc) makes the bundle launchable once the user
// clears quarantine (right-click → Open, or `xattr -cr`). When CSC_LINK is
// set, electron-builder already did a real Developer ID signing, so skip.
function adhocSignMac(context) {
  if (process.env.CSC_LINK) {
    return // real signing happened; don't clobber it
  }
  const productName = context.packager?.appInfo?.productFilename || 'Kopi'
  const appPath = path.join(context.appOutDir, `${productName}.app`)
  try {
    execFileSync('codesign', ['--force', '--deep', '--sign', '-', appPath], {
      stdio: 'inherit',
    })
    console.log(`[after-pack] ad-hoc signed ${appPath}`)
  } catch (err) {
    console.warn(`[after-pack] ad-hoc codesign failed (${err.message})`)
  }
}

export default async function afterPack(context) {
  if (context.electronPlatformName === 'darwin') {
    adhocSignMac(context)
    return
  }

  if (context.electronPlatformName !== 'win32') {
    return
  }

  const productName = context.packager?.appInfo?.productFilename || 'Kopi'
  const exe = path.join(context.appOutDir, `${productName}.exe`)
  const desktopRoot = path.resolve(import.meta.dirname, '..')

  try {
    await stampExeIdentity(exe, desktopRoot)
  } catch (err) {
    // Never fail the build over a cosmetic stamp.
    console.warn(`[after-pack] exe identity stamp failed (${err.message}); Kopi.exe keeps the stock Electron icon`)
  }
}
