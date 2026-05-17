export {}

declare global {
  interface Window {
    pathly: {
      fs: {
        read: (path: string) => Promise<string>
        write: (path: string, content: string) => Promise<void>
        list: (dir: string) => Promise<string[]>
        pickFolder: () => Promise<string | null>
      }
      shell: {
        openWindow: (path: string) => Promise<void>
      }
    }
  }
}
