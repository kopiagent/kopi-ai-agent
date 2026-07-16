import { contextBridge, ipcRenderer, webUtils } from 'electron'

contextBridge.exposeInMainWorld('kopiDesktop', {
  getConnection: profile => ipcRenderer.invoke('kopi:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('kopi:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('kopi:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('kopi:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('kopi:window:openSession', sessionId, opts),
  openNewSessionWindow: () => ipcRenderer.invoke('kopi:window:openNewSession'),
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('kopi:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('kopi:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('kopi:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('kopi:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('kopi:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('kopi:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('kopi:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('kopi:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('kopi:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('kopi:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('kopi:pet-overlay:control', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('kopi:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('kopi:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('kopi:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('kopi:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('kopi:connection-config:test', payload),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('kopi:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('kopi:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('kopi:connection-config:oauth-logout', remoteUrl),
  // Kopi Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('kopi:cloud:status'),
    login: () => ipcRenderer.invoke('kopi:cloud:login'),
    logout: () => ipcRenderer.invoke('kopi:cloud:logout'),
    discover: org => ipcRenderer.invoke('kopi:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('kopi:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('kopi:profile:get'),
    set: name => ipcRenderer.invoke('kopi:profile:set', name)
  },
  api: request => ipcRenderer.invoke('kopi:api', request),
  notify: payload => ipcRenderer.invoke('kopi:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('kopi:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('kopi:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('kopi:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('kopi:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('kopi:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('kopi:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('kopi:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('kopi:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('kopi:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('kopi:watchPreviewFile', url),
  stopPreviewFileWatch: id => ipcRenderer.invoke('kopi:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('kopi:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('kopi:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('kopi:translucency', payload),
  setPreviewShortcutActive: active => ipcRenderer.send('kopi:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('kopi:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('kopi:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('kopi:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('kopi:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('kopi:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('kopi:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('kopi:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('kopi:zoom:get'),
    setPercent: percent => ipcRenderer.send('kopi:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('kopi:zoom:changed', listener)

      return () => ipcRenderer.removeListener('kopi:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('kopi:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('kopi:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('kopi:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('kopi:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('kopi:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('kopi:fs:openDir', dirPath),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('kopi:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('kopi:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('kopi:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('kopi:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('kopi:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('kopi:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('kopi:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('kopi:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('kopi:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('kopi:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('kopi:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('kopi:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('kopi:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('kopi:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('kopi:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('kopi:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('kopi:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('kopi:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('kopi:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('kopi:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('kopi:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('kopi:git:review:shipInfo', repoPath),
      createPr: repoPath => ipcRenderer.invoke('kopi:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('kopi:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('kopi:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('kopi:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('kopi:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('kopi:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `kopi:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `kopi:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('kopi:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('kopi:close-preview-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('kopi:open-updates', listener)

    return () => ipcRenderer.removeListener('kopi:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:deep-link', listener)

    return () => ipcRenderer.removeListener('kopi:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('kopi:deep-link-ready'),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:window-state-changed', listener)

    return () => ipcRenderer.removeListener('kopi:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('kopi:focus-session', listener)

    return () => ipcRenderer.removeListener('kopi:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:notification-action', listener)

    return () => ipcRenderer.removeListener('kopi:notification-action', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('kopi:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:backend-exit', listener)

    return () => ipcRenderer.removeListener('kopi:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('kopi:connection:applied', listener)

    return () => ipcRenderer.removeListener('kopi:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('kopi:power-resume', listener)

    return () => ipcRenderer.removeListener('kopi:power-resume', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:boot-progress', listener)

    return () => ipcRenderer.removeListener('kopi:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('kopi:bootstrap:get'),
  resetBootstrap: () => ipcRenderer.invoke('kopi:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('kopi:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('kopi:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('kopi:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('kopi:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('kopi:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('kopi:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('kopi:uninstall:summary'),
    run: mode => ipcRenderer.invoke('kopi:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('kopi:updates:check'),
    apply: opts => ipcRenderer.invoke('kopi:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('kopi:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('kopi:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('kopi:updates:progress', listener)

      return () => ipcRenderer.removeListener('kopi:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('kopi:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('kopi:vscode-theme:search', query)
  }
})
