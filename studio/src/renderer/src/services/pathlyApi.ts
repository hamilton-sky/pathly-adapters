import type { FlowYaml } from '../types'

export const readFile        = (path: string): Promise<string | null>                                         => window.pathly.fs.read(path)
export const writeFile       = (path: string, content: string): Promise<void>                                 => window.pathly.fs.write(path, content)
export const deleteFile      = (path: string): Promise<void>                                                  => window.pathly.fs.delete(path)
export const listDir         = (dir: string): Promise<string[]>                                               => window.pathly.fs.list(dir)
export const listDirs        = (dir: string): Promise<string[]>                                               => window.pathly.fs.listDirs(dir)
export const getAppRoot      = (): Promise<string>                                                            => window.pathly.fs.appRoot()
export const pickFolder      = (): Promise<string | null>                                                     => window.pathly.fs.pickFolder()
export const publish         = (cwd: string): Promise<number | null>                                         => window.pathly.shell.publish(cwd)
export const upgrade         = (): Promise<number | null>                                                    => window.pathly.shell.upgrade()
export const onPublishOutput = (cb: (line: string) => void): (() => void)                                    => window.pathly.shell.onOutput(cb)
export const openWindow      = (path: string): Promise<void>                                                  => window.pathly.shell.openWindow(path)
export const openSlide       = (filePath: string): Promise<void>                                             => window.pathly.shell.openSlide(filePath)
export const getDsPort       = (): Promise<number>                                                           => window.pathly.shell.dsPort()
export const fsmPing         = (): Promise<boolean>                                                           => window.pathly.fsm.ping()
export const watchStart      = (projectPath: string, topic: string): Promise<void>                           => window.pathly.watch.start(projectPath, topic)
export const onWatchEvent    = (cb: (data: { path: string; content: string }) => void): (() => void)         => window.pathly.watch.onEvent(cb)

/** Directories a fresh Pathly workspace ships with. `project` is the PROJECT-scope
 *  home (its board's artifacts land in pathly/project/artifacts/), so it's scaffolded
 *  up front like `features` rather than appearing only on first project artifact. */
const PATHLY_SCAFFOLD_DIRS = ['features', 'project', 'debugs', 'explorations', 'lessons']

/**
 * Ensure a picked folder is a Pathly workspace: if it has no pathly/ directory,
 * create pathly/ with its core sub-dirs so the workspace sidebar (and its pinned
 * pathly section) always has something to show. Best-effort — never blocks open.
 */
export async function scaffoldPathlyWorkspace(root: string): Promise<void> {
  try {
    const dirs = await window.pathly.fs.listDirs(root).catch(() => [] as string[])
    if (dirs.includes('pathly')) return
    for (const d of PATHLY_SCAFFOLD_DIRS) {
      await window.pathly.fs.write(`${root}/pathly/${d}/.gitkeep`, '')
    }
  } catch {
    /* ignore — scaffolding is best-effort */
  }
}

export { PATHLY_API_BASE, apiFetch } from '../lib/config'

export async function fetchFlow(name: string): Promise<{ name: string; flow_yaml: string; file_path: string } | null> {
  const { apiFetch } = await import('../lib/config')
  try {
    const r = await apiFetch(`/flows/${encodeURIComponent(name)}`)
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

export async function saveFlow(name: string, flow_yaml: string): Promise<void> {
  const { apiFetch } = await import('../lib/config')
  await apiFetch(`/flows/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flow_yaml }),
  })
}

export async function fetchFlowGraph(
  name: string
): Promise<{ name: string; graph: FlowYaml } | null> {
  const { apiFetch } = await import('../lib/config')
  try {
    const r = await apiFetch(`/flows/${encodeURIComponent(name)}/graph`)
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

export async function saveFlowGraph(name: string, graph: FlowYaml): Promise<void> {
  const { apiFetch } = await import('../lib/config')
  await apiFetch(`/flows/${encodeURIComponent(name)}/graph`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ graph }),
  })
}
