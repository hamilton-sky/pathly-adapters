import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ── Run registry — the run_id spine for the board's RunPills ───────────
// A single, PERSISTED source of truth mapping a run TARGET (the goal / board /
// flow a human started) to the `run_id` its spawn minted and the state needed to
// re-verify it. commsStore's pill maps (boardRunState / goalRunState) are ephemeral
// in-memory state keyed by goal_id / board key — so a full renderer reload wipes them
// and a still-running run's pill vanishes even though the run is alive server-side.
//
// This store closes that gap WITHOUT re-keying the working watcher machinery: it is
// written at run-start (the run_id the response already carries, today discarded) and
// read on mount by commsStore.rehydrateActiveRuns, which re-verifies each entry against
// the authoritative backend (board-lock holder / FSM runner status) before repopulating
// the pill — so a run that finished while the app was closed is cleared, never falsely
// shown. It also makes the run_id first-class for every pill surface (e.g. an
// "Open run →" jump to RunDetailPage).
//
// Target kinds — EVERY agent-spawn surface routes its run-state through this one store so
// they behave identically (same RunPill, same run_id spine, same reload-survival):
//   'goal:<goalId>'   → commsStore.goalRunState  (board-lock verified)
//   'board:<key>'     → commsStore.boardRunState  (single-agent / evaluate / decompose; board-lock)
//   'flow:<key>'      → commsStore.boardRunState  (board-scoped FSM flow / consultation; no lock →
//                        verified via the runner status of the board's topic)
//   'editor:<file>:<action>' → uiStore.mdEditorActions (MD-editor Analyze / Split / Diagram
//                        one-shots; verified via GET /runs/<run_id> — a renderer one-shot that
//                        posts to /db/invocation and appears in the unified run record)
//   'summary:<msgId>' → commsStore.summaryStatus  (offline artifact summarizer one-shot)
// Board TASK pills are NOT tracked here: they derive from the server-authoritative task_status
// on the board message, so they already survive a reload (only their elapsed timer resets).
//
// board/goal/flow are backend-run-loop spawns (board-lock / runner status re-verifies them);
// editor/summary are renderer ONE-SHOTS (short-lived, run_id = the spawn's tab id, re-verified
// via the run record). The one registry + one RunPill is what makes them consistent.

export type RunKind = 'board' | 'goal' | 'flow' | 'editor' | 'summary'

export interface ActiveRunEntry {
  /** Stable target key — see the kind→map table above. */
  target: string
  /** The spawn's run_id. '' when the backend minted/returned none (e.g. a decompose). */
  runId: string
  kind: RunKind
  /** Epoch ms the run started — persisted so the pill's elapsed clock survives a reload. */
  startedAt: number
  /** The project this run belongs to — rehydration only touches the current project's runs. */
  projectRoot: string
  /** Board + scope the run holds, for backend liveness re-verification on mount. */
  board: string
  scope: string
}

export const goalTarget = (goalId: string): string => `goal:${goalId}`
export const boardTarget = (key: string): string => `board:${key}`
export const flowTarget = (key: string): string => `flow:${key}`

interface RunRegistryState {
  activeRuns: Record<string, ActiveRunEntry>
  /** Record (or overwrite) an active run at spawn time. */
  registerRun: (entry: ActiveRunEntry) => void
  /** Forget a run once it completes / stops / fails to verify. */
  clearRun: (target: string) => void
  /** The registered runs belonging to one project (rehydration scope). */
  entriesForProject: (projectRoot: string) => ActiveRunEntry[]
}

export const useRunRegistryStore = create<RunRegistryState>()(
  persist(
    (set, get) => ({
      activeRuns: {},

      registerRun: (entry) =>
        set((s) => ({ activeRuns: { ...s.activeRuns, [entry.target]: entry } })),

      clearRun: (target) =>
        set((s) => {
          if (!s.activeRuns[target]) return s
          const next = { ...s.activeRuns }
          delete next[target]
          return { activeRuns: next }
        }),

      entriesForProject: (projectRoot) =>
        Object.values(get().activeRuns).filter((e) => e.projectRoot === projectRoot),
    }),
    { name: 'pathly:active-runs' },
  ),
)
