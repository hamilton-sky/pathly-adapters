import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('pathly', {
  window: {
    setTitleBarOverlay: (color: string, symbolColor: string): Promise<void> =>
      ipcRenderer.invoke('window:setTitleBarOverlay', { color, symbolColor }),
  },
  fs: {
    read: (path: string): Promise<string> => ipcRenderer.invoke('fs:read', path),
    write: (path: string, content: string): Promise<void> =>
      ipcRenderer.invoke('fs:write', path, content),
    list: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:list', dir),
    listDirs: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:listDirs', dir),
    delete: (path: string): Promise<void> => ipcRenderer.invoke('fs:delete', path),
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke('fs:pickFolder'),
    userHome: (): Promise<string> => ipcRenderer.invoke('fs:userHome'),
    appRoot: (): Promise<string> => ipcRenderer.invoke('fs:appRoot')
  },
  shell: {
    openWindow: (path: string): Promise<void> => ipcRenderer.invoke('shell:openWindow', path),
    openVsCode: (path: string): Promise<void> => ipcRenderer.invoke('shell:openVsCode', path),
    openInApp: (path: string, appType: string): Promise<void> => ipcRenderer.invoke('shell:openInApp', path, appType),
    publish: (cwd: string): Promise<number | null> => ipcRenderer.invoke('shell:publish', cwd),
    onOutput: (cb: (line: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, line: string): void => cb(line)
      ipcRenderer.on('shell:output', listener)
      return () => ipcRenderer.removeListener('shell:output', listener)
    }
  },
  fsm: {
    ping: (): Promise<boolean> => ipcRenderer.invoke('fsm:ping'),
    state: (topic: string): Promise<unknown> => ipcRenderer.invoke('fsm:state', topic)
  },
  watch: {
    start: (projectPath: string, topic: string): Promise<void> =>
      ipcRenderer.invoke('watch:start', projectPath, topic),
    onEvent: (cb: (data: { path: string; content: string }) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, d: { path: string; content: string }): void => cb(d)
      ipcRenderer.on('watch:event', listener)
      return () => ipcRenderer.removeListener('watch:event', listener)
    },
    watchWorkspace: (projectPath: string): Promise<void> =>
      ipcRenderer.invoke('watch:workspace', projectPath),
    onWorkspaceChanged: (cb: () => void): (() => void) => {
      const listener = (): void => cb()
      ipcRenderer.on('workspace:changed', listener)
      return () => ipcRenderer.removeListener('workspace:changed', listener)
    },
  },
  terminal: {
    spawn: (tabId: string, cwd: string, command?: string): Promise<void> =>
      ipcRenderer.invoke('terminal:spawn', tabId, cwd, command),
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
    onExit: (cb: (tabId: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, tabId: string): void => cb(tabId)
      ipcRenderer.on('terminal:exit', listener)
      return () => ipcRenderer.removeListener('terminal:exit', listener)
    },
    registerRunner: (tabId: string, topic: string, runId: string): Promise<void> =>
      ipcRenderer.invoke('terminal:register-runner', tabId, topic, runId),
  },
  clipboard: {
    read: (): Promise<string> => ipcRenderer.invoke('clipboard:read'),
    write: (text: string): Promise<void> => ipcRenderer.invoke('clipboard:write', text),
    readImagePath: (): Promise<string | null> => ipcRenderer.invoke('clipboard:readImagePath'),
  },
  setup: {
    isNeeded: (): Promise<boolean> => ipcRenderer.invoke('setup:isNeeded'),
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
})

declare global {
  interface BrightskyTokenPayload {
    access_token: string
    refresh_token: string
    user: { id: string; email: string; displayName: string }
  }
  interface BrightskyAuthError {
    error: string
  }

  interface Window {
    pathly: {
      fs: {
        read: (path: string) => Promise<string>
        write: (path: string, content: string) => Promise<void>
        list: (dir: string) => Promise<string[]>
        listDirs: (dir: string) => Promise<string[]>
        delete: (path: string) => Promise<void>
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
        write: (tabId: string, data: string) => void
        resize: (tabId: string, cols: number, rows: number) => Promise<void>
        kill: (tabId: string) => Promise<void>
        popout: (tabId: string, label: string) => Promise<void>
        onData: (tabId: string, cb: (data: string) => void) => () => void
        onExit: (cb: (tabId: string) => void) => () => void
        registerRunner: (tabId: string, topic: string, runId: string) => Promise<void>
      }
      clipboard: {
        read: () => Promise<string>
        write: (text: string) => Promise<void>
        readImagePath: () => Promise<string | null>
      }
      setup: {
        isNeeded: () => Promise<boolean>
        run: () => Promise<{ ok: boolean; error?: string }>
        onProgress: (cb: (msg: string) => void) => () => void
      }
      automation: {
        executeStep: (step: { type: string; label: string; value?: string }) => Promise<unknown>
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
    }
  }
}
