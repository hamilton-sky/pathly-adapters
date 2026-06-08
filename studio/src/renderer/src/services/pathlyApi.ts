export const readFile        = (path: string): Promise<string | null>                                         => window.pathly.fs.read(path)
export const writeFile       = (path: string, content: string): Promise<void>                                 => window.pathly.fs.write(path, content)
export const listDir         = (dir: string): Promise<string[]>                                               => window.pathly.fs.list(dir)
export const listDirs        = (dir: string): Promise<string[]>                                               => window.pathly.fs.listDirs(dir)
export const getAppRoot      = (): Promise<string>                                                            => window.pathly.fs.appRoot()
export const pickFolder      = (): Promise<string | null>                                                     => window.pathly.fs.pickFolder()
export const publish         = (cwd: string): Promise<number | null>                                         => window.pathly.shell.publish(cwd)
export const onPublishOutput = (cb: (line: string) => void): (() => void)                                    => window.pathly.shell.onOutput(cb)
export const openWindow      = (path: string): Promise<void>                                                  => window.pathly.shell.openWindow(path)
export const fsmPing         = (): Promise<boolean>                                                           => window.pathly.fsm.ping()
export const watchStart      = (projectPath: string, topic: string): Promise<void>                           => window.pathly.watch.start(projectPath, topic)
export const onWatchEvent    = (cb: (data: { path: string; content: string }) => void): (() => void)         => window.pathly.watch.onEvent(cb)

export const FSM_BASE = 'http://localhost:8765'

export async function fetchFlow(name: string): Promise<{ name: string; flow_yaml: string; file_path: string } | null> {
  try {
    const r = await fetch(`${FSM_BASE}/flows/${encodeURIComponent(name)}`)
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

export async function saveFlow(name: string, flow_yaml: string): Promise<void> {
  await fetch(`${FSM_BASE}/flows/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flow_yaml }),
  })
}
