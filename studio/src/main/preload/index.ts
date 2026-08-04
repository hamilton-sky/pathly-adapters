import { contextBridge, ipcRenderer, webUtils } from 'electron'

// Mirrored in studio/src/renderer/src/types/global.d.ts — keep in sync
interface SpawnCaps { global: number; headless: number; interactive: number }
interface RunningEngine { tabId: string; adapter: string; label: string; startedAt: number }
interface SpawnState {
  running: number
  interactive: number
  total: number
  engines: RunningEngine[]
  queued: string[]
  paused: boolean
  rateLimitedUntil: number
  caps: SpawnCaps
}
interface QueueAction {
  type: 'pause' | 'resume' | 'cancel' | 'reorder' | 'set-caps'
  tabId?: string
  dir?: 'up' | 'down'
  caps?: Partial<SpawnCaps>
}
interface EnginePreflight {
  engine: string
  adapter: string
  available: boolean
  resolvedPath: string | null
  installHint: string
}

interface DbStats {
  features: number
  events: number
  invocations: number
  total_tokens: number
  total_cost_usd: number
}

interface DbFeature {
  project_root: string
  feature: string
  state: string
  events: number
  invocations: number
  total_tokens: number
  cost_usd: number
  updated_at: string
}

interface DbRollupTier {
  invocations: number
  cost_usd: number
  tokens_in: number
  tokens_out: number
}
interface DbRollupByTier {
  feature: DbRollupTier
  project: DbRollupTier
  global: DbRollupTier
}
interface DbRollupProject extends DbRollupTier {
  project_root: string
}
interface DbRollup {
  project: { root: string; by_tier: DbRollupByTier; totals: DbRollupTier }
  global: { by_tier: DbRollupByTier; totals: DbRollupTier; by_project: DbRollupProject[] }
  feature?: { feature: string; by_tier: DbRollupByTier; totals: DbRollupTier }
}

interface DbEvent {
  seq: number
  ts: string
  event_type: string
  payload: Record<string, unknown>
}

interface DbAgent {
  id: number
  run_id: string | null
  stage: string | null
  agent_role: string | null
  started_at: string | null
  finished_at: string | null
  tokens_in: number | null
  tokens_out: number | null
  cost_usd: number | null
  session_id: string | null
  summary: string | null
  scope_tier?: string | null
}

interface DbTrendPoint {
  day: string
  cost_usd: number
  tokens_in: number
  tokens_out: number
  span_count: number
}

interface DailyTrendBucket {
  bucket: string
  count: number
  total_tokens: number
  input_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  cost_usd_reported: number
  has_estimated_rows: number
}

interface TrendsResponse {
  trends: DailyTrendBucket[]
}

interface DbOtelSpan {
  id: number
  trace_id: string | null
  span_id: string | null
  parent_span_id: string | null
  name: string
  start_time: string
  end_time: string
  attributes: Record<string, unknown>
}

interface DbRun {
  id: number
  run_id: string
  status: string
  started_at: string | null
  finished_at: string | null
  stage_count: number
  total_tokens: number
  cost_usd: number
  adapter: string | null
}

interface BrightskyTokenPayload {
  access_token: string
  refresh_token: string
  user: { id: string; email: string; displayName: string }
}
interface BrightskyAuthError {
  error: string
}

contextBridge.exposeInMainWorld('pathly', {
  window: {
    setTitleBarOverlay: (color: string, symbolColor: string): Promise<void> =>
      ipcRenderer.invoke('window:setTitleBarOverlay', { color, symbolColor }),
  },
  board: {
    popout: (opts: { scope: string; feature: string; project: string; name: string }): Promise<void> =>
      ipcRenderer.invoke('board:popout', opts),
  },
  git: {
    commitBoard: (
      projectPath: string,
      boardRelPath: string,
      message: string,
    ): Promise<{ ok: boolean; committed: boolean; hash?: string; error?: string }> =>
      ipcRenderer.invoke('git:commit-board', projectPath, boardRelPath, message),
  },
  fs: {
    read: (path: string): Promise<string | null> => ipcRenderer.invoke('fs:read', path),
    write: (path: string, content: string): Promise<void> =>
      ipcRenderer.invoke('fs:write', path, content),
    list: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:list', dir),
    listDirs: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:listDirs', dir),
    delete: (path: string): Promise<void> => ipcRenderer.invoke('fs:delete', path),
    moveToParent: (filePath: string): Promise<string> => ipcRenderer.invoke('fs:moveToParent', filePath),
    move: (src: string, dest: string): Promise<void> => ipcRenderer.invoke('fs:move', src, dest),
    copy: (src: string, dest: string): Promise<void> => ipcRenderer.invoke('fs:copy', src, dest),
    // Resolve a dropped File's absolute path (File.path was removed in modern
    // Electron). Synchronous — webUtils runs in the preload.
    pathForFile: (file: File): string => webUtils.getPathForFile(file),
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke('fs:pickFolder'),
    saveDialog: (defaultPath: string, content: string, intoDownloads?: boolean): Promise<string | null> =>
      ipcRenderer.invoke('fs:saveDialog', defaultPath, content, intoDownloads),
    userHome: (): Promise<string> => ipcRenderer.invoke('fs:userHome'),
    appRoot: (): Promise<string> => ipcRenderer.invoke('fs:appRoot')
  },
  shell: {
    openWindow: (path: string): Promise<void> => ipcRenderer.invoke('shell:openWindow', path),
    openVsCode: (path: string): Promise<void> => ipcRenderer.invoke('shell:openVsCode', path),
    openInApp: (path: string, appType: string): Promise<void> => ipcRenderer.invoke('shell:openInApp', path, appType),
    publish: (cwd: string): Promise<number | null> => ipcRenderer.invoke('shell:publish', cwd),
    upgrade: (): Promise<number | null> => ipcRenderer.invoke('shell:upgrade'),
    onOutput: (cb: (line: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, line: string): void => cb(line)
      ipcRenderer.on('shell:output', listener)
      return () => ipcRenderer.removeListener('shell:output', listener)
    },
    openSlide: (filePath: string): Promise<void> => ipcRenderer.invoke('shell:openSlide', filePath),
    dsPort: (): Promise<number> => ipcRenderer.invoke('shell:dsPort'),
    apiConfig: (): Promise<{ base: string; secret: string }> => ipcRenderer.invoke('shell:apiConfig'),
  },
  fsm: {
    ping: (): Promise<boolean> => ipcRenderer.invoke('fsm:ping'),
    state: (topic: string): Promise<unknown> => ipcRenderer.invoke('fsm:state', topic),
    runSkill: (topic: string, skill: string, projectPath: string): Promise<{ success: boolean; runId?: string; error?: string }> =>
      ipcRenderer.invoke('fsm:runSkill', topic, skill, projectPath),
  },
  watch: {
    start: (projectPath: string, topic: string): Promise<void> =>
      ipcRenderer.invoke('watch:start', projectPath, topic),
    onEvent: (cb: (data: { path: string; content: string }) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, d: { path: string; content: string }): void => cb(d)
      ipcRenderer.on('watch:event', listener)
      return () => ipcRenderer.removeListener('watch:event', listener)
    },
    stopFeature: (topic: string): Promise<void> =>
      ipcRenderer.invoke('watch:stopFeature', topic),
    watchWorkspace: (projectPath: string): Promise<void> =>
      ipcRenderer.invoke('watch:workspace', projectPath),
    pauseWorkspace: (): Promise<void> =>
      ipcRenderer.invoke('watch:pauseWorkspace'),
    resumeWorkspace: (projectPath?: string): Promise<void> =>
      ipcRenderer.invoke('watch:resumeWorkspace', projectPath),
    onWorkspaceChanged: (cb: () => void): (() => void) => {
      const listener = (): void => cb()
      ipcRenderer.on('workspace:changed', listener)
      return () => ipcRenderer.removeListener('workspace:changed', listener)
    },
  },
  terminal: {
    spawn: (tabId: string, cwd: string, command?: string, argv?: string[], initialInput?: string, meta?: { telemetry?: { scopeTier: string; label: string; feature?: string; role?: string } }): Promise<void> =>
      ipcRenderer.invoke('terminal:spawn', tabId, cwd, command, argv, initialInput, meta),
    write: (tabId: string, data: string): void =>
      ipcRenderer.send('terminal:write', tabId, data),
    resize: (tabId: string, cols: number, rows: number): Promise<void> =>
      ipcRenderer.invoke('terminal:resize', tabId, cols, rows),
    kill: (tabId: string): Promise<void> =>
      ipcRenderer.invoke('terminal:kill', tabId),
    popout: (tabId: string, label: string): Promise<void> =>
      ipcRenderer.invoke('terminal:popout', tabId, label),
    onData: (tabId: string, cb: (data: string) => void): (() => void) => {
      const channel = `terminal:data:${tabId}`
      const listener = (_e: Electron.IpcRendererEvent, data: string): void => cb(data)
      ipcRenderer.on(channel, listener)
      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (cb: (tabId: string, exitCode?: number, tail?: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, tabId: string, exitCode?: number, tail?: string): void => cb(tabId, exitCode, tail)
      ipcRenderer.on('terminal:exit', listener)
      return () => ipcRenderer.removeListener('terminal:exit', listener)
    },
    onSpawnState: (cb: (s: SpawnState) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, s: SpawnState): void => cb(s)
      ipcRenderer.on('spawn:state', listener)
      return () => ipcRenderer.removeListener('spawn:state', listener)
    },
    queueControl: (action: QueueAction): Promise<void> =>
      ipcRenderer.invoke('terminal:queue-control', action),
    preflight: (force?: boolean): Promise<EnginePreflight[]> =>
      ipcRenderer.invoke('terminal:preflight', force),
    registerRunner: (tabId: string, topic: string, runId: string, label?: string, category?: 'flow' | 'loop' | 'single'): Promise<void> =>
      ipcRenderer.invoke('terminal:register-runner', tabId, topic, runId, label, category),
    onStageResult: (cb: (tabId: string, data: Record<string, unknown>) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, tabId: string, data: Record<string, unknown>): void => cb(tabId, data)
      ipcRenderer.on('terminal:stage-result', listener)
      return () => ipcRenderer.removeListener('terminal:stage-result', listener)
    },
  },
  clipboard: {
    read: (): Promise<string> => ipcRenderer.invoke('clipboard:read'),
    write: (text: string): Promise<void> => ipcRenderer.invoke('clipboard:write', text),
    readImagePath: (): Promise<string | null> => ipcRenderer.invoke('clipboard:readImagePath'),
  },
  setup: {
    isNeeded: (): Promise<boolean> => ipcRenderer.invoke('setup:isNeeded'),
    info: (): Promise<{ isNeeded: boolean; isUpgrade: boolean; fromVersion: string | null; toVersion: string }> =>
      ipcRenderer.invoke('setup:info'),
    run: (): Promise<{ ok: boolean; error?: string }> => ipcRenderer.invoke('setup:run'),
    onProgress: (cb: (msg: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, msg: string): void => cb(msg)
      ipcRenderer.on('setup:progress', listener)
      return () => ipcRenderer.removeListener('setup:progress', listener)
    }
  },
  automation: {
    executeStep: (step: { type: string; label: string; value?: string }): Promise<unknown> =>
      ipcRenderer.invoke('automation:executeStep', step),
  },
  llm: {
    isAvailable: (): Promise<boolean> =>
      ipcRenderer.invoke('llm:isAvailable'),
    listCached: (): Promise<string[]> =>
      ipcRenderer.invoke('llm:listCached'),
    download: (modelId: string): Promise<void> =>
      ipcRenderer.invoke('llm:download', modelId),
    delete: (modelId: string): Promise<void> =>
      ipcRenderer.invoke('llm:delete', modelId),
    load: (modelId: string): Promise<void> =>
      ipcRenderer.invoke('llm:load', modelId),
    chat: (prompt: string, systemPrompt: string, modelId: string): Promise<void> =>
      ipcRenderer.invoke('llm:chat', { prompt, systemPrompt, modelId }),
    abort: (): Promise<void> =>
      ipcRenderer.invoke('llm:abort'),
    onToken: (cb: (token: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, token: string): void => cb(token)
      ipcRenderer.on('llm:token', listener)
      return () => ipcRenderer.removeListener('llm:token', listener)
    },
    onDone: (cb: (fullText: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, text: string): void => cb(text)
      ipcRenderer.on('llm:done', listener)
      return () => ipcRenderer.removeListener('llm:done', listener)
    },
    onError: (cb: (message: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, msg: string): void => cb(msg)
      ipcRenderer.on('llm:error', listener)
      return () => ipcRenderer.removeListener('llm:error', listener)
    },
    onLoadProgress: (cb: (data: { pct: number; text: string }) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, data: { pct: number; text: string }): void => cb(data)
      ipcRenderer.on('llm:load-progress', listener)
      return () => ipcRenderer.removeListener('llm:load-progress', listener)
    },
    onDownloadProgress: (cb: (data: { modelId: string; pct: number; downloaded: number; total: number }) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, data: { modelId: string; pct: number; downloaded: number; total: number }): void => cb(data)
      ipcRenderer.on('llm:dl-progress', listener)
      return () => ipcRenderer.removeListener('llm:dl-progress', listener)
    },
    // Ollama backend — works on any Electron version
    ollamaAvailable: (): Promise<{ available: boolean; models: string[] }> =>
      ipcRenderer.invoke('llm:ollamaAvailable'),
    ollamaPull: (ollamaId: string): Promise<void> =>
      ipcRenderer.invoke('llm:ollamaPull', ollamaId),
    ollamaDelete: (ollamaId: string): Promise<void> =>
      ipcRenderer.invoke('llm:ollamaDelete', ollamaId),
    ollamaChat: (prompt: string, systemPrompt: string, modelId: string, think?: boolean): Promise<void> =>
      ipcRenderer.invoke('llm:ollamaChat', { prompt, systemPrompt, modelId, think }),
  },
  brightsky: {
    login: (baseUrl: string): Promise<void> => ipcRenderer.invoke('brightsky:login', baseUrl),
    onToken: (cb: (payload: BrightskyTokenPayload | BrightskyAuthError) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, payload: BrightskyTokenPayload | BrightskyAuthError): void => cb(payload)
      ipcRenderer.on('brightsky:token', listener)
      return () => ipcRenderer.removeListener('brightsky:token', listener)
    },
  },
  db: {
    stats: (projectRoot?: string): Promise<DbStats | null> => ipcRenderer.invoke('db:stats', projectRoot),
    features: (projectRoot?: string): Promise<DbFeature[]> => ipcRenderer.invoke('db:features', projectRoot),
    rollup: (projectRoot?: string, feature?: string): Promise<DbRollup | null> => ipcRenderer.invoke('db:rollup', projectRoot, feature),
    events: (feature: string, projectRoot?: string): Promise<DbEvent[]> =>
      ipcRenderer.invoke('db:events', feature, projectRoot),
    agents: (feature: string, projectRoot?: string): Promise<DbAgent[]> =>
      ipcRenderer.invoke('db:agents', feature, projectRoot),
    otel: (feature: string, projectRoot?: string): Promise<DbOtelSpan[]> =>
      ipcRenderer.invoke('db:otel', feature, projectRoot),
    trends: (feature: string, days?: number, projectRoot?: string): Promise<TrendsResponse | null> =>
      ipcRenderer.invoke('db:trends', feature, days, projectRoot),
    runs: (feature: string, projectRoot?: string): Promise<DbRun[]> =>
      ipcRenderer.invoke('db:runs', feature, projectRoot),
    query: (sql: string): Promise<{ rows: Record<string, unknown>[]; error?: string }> =>
      ipcRenderer.invoke('db:query', sql),
    settings: (): Promise<Record<string, string>> => ipcRenderer.invoke('db:settings'),
    setSetting: (key: string, value: string): Promise<void> =>
      ipcRenderer.invoke('db:setSetting', key, value),
  },
})
