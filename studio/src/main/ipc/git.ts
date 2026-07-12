import { ipcMain } from 'electron'
import { execFile } from 'node:child_process'
import { existsSync } from 'node:fs'
import { promisify } from 'node:util'

const run = promisify(execFile)

export interface CommitBoardResult {
  ok: boolean
  /** True only when a NEW commit was actually created. */
  committed: boolean
  hash?: string
  error?: string
}

// Force-add + commit a SINGLE board mirror file, past the .gitignore rule that ignores
// pathly/**/BOARD.json — the opt-in "ship a finished board with the repo" action. It
// commits LOCALLY only (never pushes — the human pushes on their own review cadence) and
// only that one path (a partial commit, so the user's other staged changes are untouched).
// Best-effort: returns a structured result for a toast, never throws.
export function registerGitHandlers(): void {
  ipcMain.handle(
    'git:commit-board',
    async (
      _e,
      projectPath: string,
      boardRelPath: string,
      message: string,
    ): Promise<CommitBoardResult> => {
      try {
        const root = String(projectPath || '')
        const rel = String(boardRelPath || '').replace(/\\/g, '/')
        // Pathspec guard: exactly a BOARD.json under pathly/, no traversal.
        if (!root || rel.includes('..') || !/^pathly\/[^\0]+\/BOARD\.json$/.test(rel)) {
          return { ok: false, committed: false, error: 'invalid board path' }
        }
        if (!existsSync(`${root}/${rel}`)) {
          return { ok: true, committed: false, error: 'no board file on disk yet' }
        }
        await run('git', ['rev-parse', '--is-inside-work-tree'], { cwd: root })
        await run('git', ['add', '-f', '--', rel], { cwd: root })
        try {
          await run('git', ['commit', '-m', message || `board: snapshot ${rel}`, '--', rel], { cwd: root })
        } catch (e) {
          const out = `${(e as { stdout?: string }).stdout ?? ''}${(e as { stderr?: string }).stderr ?? ''}`
          if (/nothing to commit|no changes added|nothing added/i.test(out)) {
            return { ok: true, committed: false, error: 'board already committed and unchanged' }
          }
          throw e
        }
        const { stdout } = await run('git', ['rev-parse', '--short', 'HEAD'], { cwd: root })
        return { ok: true, committed: true, hash: stdout.trim() }
      } catch (e) {
        return { ok: false, committed: false, error: String((e as Error)?.message ?? e).slice(0, 300) }
      }
    },
  )
}
