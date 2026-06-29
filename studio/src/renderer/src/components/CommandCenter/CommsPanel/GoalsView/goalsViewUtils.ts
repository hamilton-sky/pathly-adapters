import type { Message } from '../../types'

// Order tasks so a task always appears after the tasks it depends on (a stable
// DFS topological sort). Cycles are tolerated — the `visiting` guard prevents
// infinite recursion and the offending node is emitted once deps are walked.
export function orderByDeps(tasks: Message[]): Message[] {
  const byId = new Map(tasks.map((t) => [t.id, t]))
  const result: Message[] = []
  const done = new Set<string>()
  const visiting = new Set<string>()

  function visit(t: Message): void {
    if (done.has(t.id) || visiting.has(t.id)) return
    visiting.add(t.id)
    for (const dep of t.dependsOn ?? []) {
      const d = byId.get(dep)
      if (d) visit(d)
    }
    visiting.delete(t.id)
    done.add(t.id)
    result.push(t)
  }

  for (const t of tasks) visit(t)
  return result
}

// Serialize a goal + its tasks to one markdown block for the clipboard. Order follows the
// DAG (orderByDeps); each task is numbered with its status, artifact, and full text — so a
// human can paste the whole work list into a prompt or an issue.
export function serializeTasks(goalText: string, tasks: Message[]): string {
  const ordered = orderByDeps(tasks)
  const lines: string[] = [`# ${goalText.trim()}`, '']
  ordered.forEach((t, i) => {
    const status = t.taskStatus ?? 'pending'
    lines.push(`## Task ${i + 1} — ${status}`)
    if (t.artifactPath) lines.push(`_artifact: ${t.artifactPath}_`)
    lines.push('', t.text.trim(), '')
  })
  return lines.join('\n').trimEnd() + '\n'
}

export interface Rollup {
  total: number
  done: number
  ready: number
  running: number
  failed: number
}

// Client-side rollup for a goal's task list. "ready" = a pending task whose
// every dependency is done (mirrors the backend frontier rule).
export function computeRollup(tasks: Message[]): Rollup {
  const doneIds = new Set(tasks.filter((t) => t.taskStatus === 'done').map((t) => t.id))
  let done = 0
  let ready = 0
  let running = 0
  let failed = 0
  for (const t of tasks) {
    const st = t.taskStatus ?? 'pending'
    if (st === 'done') done++
    else if (st === 'in_progress') running++
    else if (st === 'failed' || st === 'blocked') failed++
    else if ((t.dependsOn ?? []).every((d) => doneIds.has(d))) ready++
  }
  return { total: tasks.length, done, ready, running, failed }
}
