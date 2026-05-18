import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('pathly', {
  fs: {
    read: (path: string): Promise<string> => ipcRenderer.invoke('fs:read', path),
    write: (path: string, content: string): Promise<void> =>
      ipcRenderer.invoke('fs:write', path, content),
    list: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:list', dir),
    listDirs: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:listDirs', dir),
    delete: (path: string): Promise<void> => ipcRenderer.invoke('fs:delete', path),
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke('fs:pickFolder')
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
    spawn: (tabId: string, cwd: string): Promise<void> =>
      ipcRenderer.invoke('terminal:spawn', tabId, cwd),
    write: (tabId: string, data: string): void =>
      ipcRenderer.send('terminal:write', tabId, data),
    resize: (tabId: string, cols: number, rows: number): Promise<void> =>
      ipcRenderer.invoke('terminal:resize', tabId, cols, rows),
    kill: (tabId: string): Promise<void> =>
      ipcRenderer.invoke('terminal:kill', tabId),
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
  }
})
