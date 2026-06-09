import { ipcMain } from 'electron'
import { cwd } from 'process'

const FSM_BASE = `http://127.0.0.1:${process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765'}`
const _PR = encodeURIComponent(process.env['PATHLY_PROJECT_ROOT'] ?? cwd())

async function fsmGet(path: string): Promise<unknown> {
  const res = await fetch(`${FSM_BASE}${path}`, { signal: AbortSignal.timeout(3000) })
  if (!res.ok) throw new Error(`FSM ${res.status}: ${path}`)
  return res.json()
}

async function fsmPost(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${FSM_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(3000),
  })
  if (!res.ok) throw new Error(`FSM ${res.status}: ${path}`)
  return res.json()
}

async function fsmPut(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${FSM_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(3000),
  })
  if (!res.ok) throw new Error(`FSM ${res.status}: ${path}`)
  return res.json()
}

export function registerDbHandlers(): void {
  ipcMain.handle('db:stats', async () => {
    try { return await fsmGet(`/db/stats?project_root=${_PR}`) } catch { return null }
  })

  ipcMain.handle('db:features', async () => {
    try { return await fsmGet(`/db/features?project_root=${_PR}`) } catch { return [] }
  })

  ipcMain.handle('db:events', async (_e, feature: string, projectRoot?: string) => {
    const qs = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    try { return await fsmGet(`/db/features/${encodeURIComponent(feature)}/events${qs}`) } catch { return [] }
  })

  ipcMain.handle('db:agents', async (_e, feature: string, projectRoot?: string) => {
    const qs = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    try { return await fsmGet(`/db/features/${encodeURIComponent(feature)}/agents${qs}`) } catch { return [] }
  })

  ipcMain.handle('db:otel', async (_e, feature: string, projectRoot?: string) => {
    const qs = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    try { return await fsmGet(`/db/features/${encodeURIComponent(feature)}/otel${qs}`) } catch { return [] }
  })

  ipcMain.handle('db:runs', async (_e, feature: string, projectRoot?: string) => {
    const qs = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    try { return await fsmGet(`/db/features/${encodeURIComponent(feature)}/runs${qs}`) } catch { return [] }
  })

  ipcMain.handle('db:trends', async (_e, days?: number) => {
    const qs = days ? `?days=${days}` : ''
    try { return await fsmGet(`/db/stats/trends${qs}`) } catch { return [] }
  })

  ipcMain.handle('db:query', async (_e, sql: string) => {
    try { return await fsmPost('/db/query', { sql }) } catch (err) { return { error: String(err) } }
  })

  ipcMain.handle('db:settings', async () => {
    try { return await fsmGet('/db/settings') } catch { return {} }
  })

  ipcMain.handle('db:setSetting', async (_e, key: string, value: string) => {
    try { return await fsmPut(`/db/settings/${encodeURIComponent(key)}`, { value }) } catch { return null }
  })
}
