export {}

declare global {
  interface SpawnCaps { global: number; headless: number; interactive: number }
  /** One identified live CLI engine (PTY spawned, not yet exited). Carries enough to render a
   *  monitor row without the renderer's terminalStore, which a window reload would wipe. */
  interface RunningEngine {
    tabId: string
    adapter: string
    label: string
    startedAt: number
    /** How the engine was spawned — the Monitor board's primary grouping. */
    category: 'flow' | 'loop' | 'single'
    /** Feature/topic this engine serves, when known (runner topic or spawn telemetry.feature). */
    feature?: string
    /** Agent role from spawn telemetry (single-shot editor/AI actions); absent for runner tabs. */
    role?: string
    /** Pipeline run id (runner tabs only) — keys the per-flow cost rollup (/db/runs/<run_id>/cost). */
    runId?: string
    /** When the engine finished — set only on RECENT/history entries. */
    finishedAt?: number
  }
  interface SpawnState {
    running: number
    interactive: number
    total: number
    /** Live engines (headless + interactive) — the CLI monitor's authoritative ACTIVE list. */
    engines: RunningEngine[]
    /** Engines accepted but still waiting for a slot (queued/paused) — rendered as queued rows. */
    queuedEngines: RunningEngine[]
    /** Recently-finished engines (newest first, bounded) — the RECENT/history list. */
    recentEngines: RunningEngine[]
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
    source?: string
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
    day: string        // "YYYY-MM-DD"
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
    scope_tier?: string | null
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

  interface Window {
    __pathlyNavigate?: (panelName: string) => void
    pathly: {
      fs: {
        read: (path: string) => Promise<string | null>
        write: (path: string, content: string) => Promise<void>
        list: (dir: string) => Promise<string[]>
        listDirs: (dir: string) => Promise<string[]>
        delete: (path: string) => Promise<void>
        moveToParent: (filePath: string) => Promise<string>
        move: (src: string, dest: string) => Promise<void>
        copy: (src: string, dest: string) => Promise<void>
        pathForFile: (file: File) => string
        pickFolder: () => Promise<string | null>
        saveDialog: (defaultPath: string, content: string, intoDownloads?: boolean) => Promise<string | null>
        userHome: () => Promise<string>
        appRoot: () => Promise<string>
      }
      shell: {
        openWindow: (path: string) => Promise<void>
        openVsCode: (path: string) => Promise<void>
        openInApp: (path: string, appType: string) => Promise<void>
        publish: (cwd: string) => Promise<number | null>
        upgrade: () => Promise<number | null>
        onOutput: (cb: (line: string) => void) => () => void
        openSlide: (filePath: string) => Promise<void>
        dsPort: () => Promise<number>
        apiConfig: () => Promise<{ base: string; secret: string }>
      }
      fsm: {
        ping: () => Promise<boolean>
        state: (topic: string) => Promise<unknown>
        runSkill: (topic: string, skill: string, projectPath: string) => Promise<{ success: boolean; runId?: string; error?: string }>
      }
      watch: {
        start: (projectPath: string, topic: string) => Promise<void>
        onEvent: (cb: (data: { path: string; content: string }) => void) => () => void
        watchWorkspace?: (projectPath: string) => Promise<void>
        onWorkspaceChanged?: (cb: () => void) => () => void
      }
      terminal: {
        spawn: (tabId: string, cwd: string, command?: string, argv?: string[], initialInput?: string, meta?: { telemetry?: { scopeTier: string; label: string; feature?: string; role?: string } }) => Promise<void>
        kill: (tabId: string) => Promise<void>
        popout: (tabId: string, label: string) => Promise<void>
        write: (tabId: string, data: string) => void
        resize: (tabId: string, cols: number, rows: number) => Promise<void>
        onData: (tabId: string, cb: (data: string) => void) => () => void
        onExit: (cb: (tabId: string, exitCode?: number, tail?: string) => void) => () => void
        onSpawnState: (cb: (s: SpawnState) => void) => () => void
        queueControl: (action: QueueAction) => Promise<void>
        registerRunner: (tabId: string, topic: string, runId: string, label?: string, category?: 'flow' | 'loop' | 'single') => Promise<void>
        onStageResult: (cb: (tabId: string, data: Record<string, unknown>) => void) => () => void
      }
      setup: {
        isNeeded: () => Promise<boolean>
        info: () => Promise<{ isNeeded: boolean; isUpgrade: boolean; fromVersion: string | null; toVersion: string }>
        run: () => Promise<{ ok: boolean; error?: string }>
        onProgress: (cb: (msg: string) => void) => () => void
      }
      clipboard: {
        read: () => Promise<string>
        write: (text: string) => Promise<void>
        readImagePath: () => Promise<string | null>
      }
      window?: {
        setTitleBarOverlay: (bgColor: string, symbolColor: string) => void
      }
      board: {
        popout: (opts: { scope: 'feature' | 'project' | 'global'; feature: string; project: string; name: string }) => Promise<void>
      }
      git: {
        commitBoard: (projectPath: string, boardRelPath: string, message: string) => Promise<{ ok: boolean; committed: boolean; hash?: string; error?: string }>
      }
      automation: {
        executeStep: (step: { type: 'click' | 'fill' | 'select' | 'navigate'; label: string; value?: string }) => Promise<{ success: boolean; tier: 1 | 2 | 3; error?: string; resolvedSelector?: string }>
      }
      llm: {
        isAvailable: () => Promise<boolean>
        listCached: () => Promise<string[]>
        download: (modelId: string) => Promise<void>
        delete: (modelId: string) => Promise<void>
        load: (modelId: string) => Promise<void>
        chat: (prompt: string, systemPrompt: string, modelId: string) => Promise<void>
        abort: () => Promise<void>
        onToken: (cb: (token: string) => void) => () => void
        onDone: (cb: (fullText: string) => void) => () => void
        onError: (cb: (message: string) => void) => () => void
        onLoadProgress: (cb: (data: { pct: number; text: string }) => void) => () => void
        onDownloadProgress: (cb: (data: { modelId: string; pct: number; downloaded: number; total: number }) => void) => () => void
        ollamaAvailable: () => Promise<{ available: boolean; models: string[] }>
        ollamaPull: (ollamaId: string) => Promise<void>
        ollamaDelete: (ollamaId: string) => Promise<void>
        ollamaChat: (prompt: string, systemPrompt: string, modelId: string, think?: boolean) => Promise<void>
      }
      brightsky: {
        login: (baseUrl: string) => Promise<void>
        onToken: (cb: (payload: BrightskyTokenPayload | BrightskyAuthError) => void) => () => void
      }
      db: {
        stats: (projectRoot?: string) => Promise<DbStats | null>
        features: (projectRoot?: string) => Promise<DbFeature[]>
        rollup: (projectRoot?: string, feature?: string) => Promise<DbRollup | null>
        events: (feature: string, projectRoot?: string) => Promise<DbEvent[]>
        agents: (feature: string, projectRoot?: string) => Promise<DbAgent[]>
        otel: (feature: string, projectRoot?: string) => Promise<DbOtelSpan[]>
        trends: (feature: string, days?: number) => Promise<TrendsResponse | null>
        runs: (feature: string, projectRoot?: string) => Promise<DbRun[]>
        query: (sql: string) => Promise<{ rows: Record<string, unknown>[]; error?: string }>
        settings: () => Promise<Record<string, string>>
        setSetting: (key: string, value: string) => Promise<void>
      }
    }
  }
}
