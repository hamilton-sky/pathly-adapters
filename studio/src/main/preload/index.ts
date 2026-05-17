import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('pathly', {
  fs: {
    read: (path: string): Promise<string> => ipcRenderer.invoke('fs:read', path),
    write: (path: string, content: string): Promise<void> =>
      ipcRenderer.invoke('fs:write', path, content),
    list: (dir: string): Promise<string[]> => ipcRenderer.invoke('fs:list', dir),
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke('fs:pickFolder')
  },
  shell: {
    openWindow: (path: string): Promise<void> => ipcRenderer.invoke('shell:openWindow', path)
  }
})
