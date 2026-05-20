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
    userHome: (): Promise<string> => ipcRenderer.invoke('fs:userHome')
  },
  shell: {
    openWindow: (path: string): Promise<void> => ipcRenderer.invoke('shell:openWindow', path),
    publish: (cwd: string): Promise<number | null> => ipcRenderer.invoke('shell:publish', cwd),
    onOutput: (cb: (line: string) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, line: string): void => cb(line)
      ipcRenderer.on('shell:output', listener)
      return () => ipcRenderer.removeListener('shell:output', listener)
    }
  },
  mcp: {
    ping: (): Promise<boolean> => ipcRenderer.invoke('mcp:ping'),
    state: (topic: string): Promise<unknown> => ipcRenderer.invoke('mcp:state', topic)
  },
  watch: {
    start: (projectPath: string, topic: string): Promise<void> =>
      ipcRenderer.invoke('watch:start', projectPath, topic),
    onEvent: (cb: (data: { path: string; content: string }) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, d: { path: string; content: string }): void => cb(d)
      ipcRenderer.on('watch:event', listener)
      return () => ipcRenderer.removeListener('watch:event', listener)
    }
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
    }
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
  }
})

declare global {
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
      }
      shell: {
        openWindow: (path: string) => Promise<void>
        publish: (cwd: string) => Promise<number | null>
        onOutput: (cb: (line: string) => void) => () => void
      }
      mcp: {
        ping: () => Promise<boolean>
        state: (topic: string) => Promise<unknown>
      }
      watch: {
        start: (projectPath: string, topic: string) => Promise<void>
        onEvent: (cb: (data: { path: string; content: string }) => void) => () => void
      }
      terminal: {
        spawn: (tabId: string, cwd: string, command?: string) => Promise<void>
        write: (tabId: string, data: string) => void
        resize: (tabId: string, cols: number, rows: number) => Promise<void>
        kill: (tabId: string) => Promise<void>
        popout: (tabId: string, label: string) => Promise<void>
        onData: (tabId: string, cb: (data: string) => void) => () => void
        onExit: (cb: (tabId: string) => void) => () => void
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
    }
  }
}
