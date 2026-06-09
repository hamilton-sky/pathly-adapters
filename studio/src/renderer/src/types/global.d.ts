export {}

declare global {
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
    convs_done?: number
    convs_total?: number
    source?: string
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

  interface Window {
    __pathlyNavigate?: (panelName: string) => void
    pathly: {
      fs: {
        read: (path: string) => Promise<string>
        write: (path: string, content: string) => Promise<void>
        list: (dir: string) => Promise<string[]>
        listDirs: (dir: string) => Promise<string[]>
        delete: (path: string) => Promise<void>
        moveToParent: (filePath: string) => Promise<string>
        pickFolder: () => Promise<string | null>
        userHome: () => Promise<string>
        appRoot: () => Promise<string>
      }
      shell: {
        openWindow: (path: string) => Promise<void>
        openVsCode: (path: string) => Promise<void>
        openInApp: (path: string, appType: string) => Promise<void>
        publish: (cwd: string) => Promise<number | null>
        onOutput: (cb: (line: string) => void) => () => void
        openSlide: (filePath: string) => Promise<void>
        dsPort: () => Promise<number>
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
        spawn: (tabId: string, cwd: string, command?: string, argv?: string[], initialInput?: string) => Promise<void>
        kill: (tabId: string) => Promise<void>
        popout: (tabId: string, label: string) => Promise<void>
        write: (tabId: string, data: string) => void
        resize: (tabId: string, cols: number, rows: number) => Promise<void>
        onData: (tabId: string, cb: (data: string) => void) => () => void
        onExit: (cb: (tabId: string) => void) => () => void
        registerRunner: (tabId: string, topic: string, runId: string, label?: string) => Promise<void>
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
        stats: () => Promise<DbStats | null>
        features: () => Promise<DbFeature[]>
        events: (feature: string, projectRoot?: string) => Promise<DbEvent[]>
        agents: (feature: string, projectRoot?: string) => Promise<DbAgent[]>
        otel: (feature: string, projectRoot?: string) => Promise<DbOtelSpan[]>
        runs: (feature: string, projectRoot?: string) => Promise<DbRun[]>
        query: (sql: string) => Promise<{ rows: Record<string, unknown>[]; error?: string }>
        settings: () => Promise<Record<string, string>>
        setSetting: (key: string, value: string) => Promise<void>
      }
    }
  }
}
