export {}

declare global {
  interface Window {
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
      }
      shell: {
        openWindow: (path: string) => Promise<void>
        publish: (cwd: string) => Promise<number | null>
        onOutput: (cb: (line: string) => void) => () => void
      }
      fsm: {
        ping: () => Promise<boolean>
        state: (topic: string) => Promise<unknown>
      }
      watch: {
        start: (projectPath: string, topic: string) => Promise<void>
        onEvent: (cb: (data: { path: string; content: string }) => void) => () => void
        watchWorkspace?: (projectPath: string) => Promise<void>
        onWorkspaceChanged?: (cb: () => void) => () => void
      }
      terminal: {
        spawn: (tabId: string, cwd: string, command?: string) => Promise<void>
        kill: (tabId: string) => Promise<void>
        popout: (tabId: string, label: string) => Promise<void>
        write: (tabId: string, data: string) => void
        resize: (tabId: string, cols: number, rows: number) => Promise<void>
        onData: (tabId: string, cb: (data: string) => void) => () => void
        onExit: (cb: (tabId: string) => void) => () => void
      }
      setup: {
        isNeeded: () => Promise<boolean>
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
        ollamaChat: (prompt: string, systemPrompt: string, modelId: string) => Promise<void>
      }
    }
  }
}
