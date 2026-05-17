export {}

declare global {
  interface Window {
    pathly: {
      fs: {
        read: (path: string) => Promise<string>
        write: (path: string, content: string) => Promise<void>
        list: (dir: string) => Promise<string[]>
        listDirs: (dir: string) => Promise<string[]>
        pickFolder: () => Promise<string | null>
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
    }
  }
}
