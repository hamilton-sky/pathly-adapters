import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Message } from './chatStore'
import { adoptInto, migrateHqHistory, UNASSIGNED, upsertSession, type HqSession, type ProjectHistory } from './hqHistory'

/** HQ chat history, saved in this browser profile (localStorage), one history
 *  per project (keyed by project path): switching projects switches the chat on
 *  screen and the history list. `currentId` is that project's open chat. */
interface HqHistoryState {
  byProject: Record<string, ProjectHistory>
  /** The project's history, created (with a fresh current chat) on first use. */
  ensure: (project: string) => ProjectHistory
  saveCurrent: (project: string, messages: Message[]) => void
  startNew: (project: string) => void
  /** Make *id* the project's open chat; returns it, or null when it no longer exists. */
  open: (project: string, id: string) => HqSession | null
  /** Move chats saved before history was per-project into *project*. */
  adoptUnassigned: (project: string) => void
}

const fresh = (): ProjectHistory => ({ currentId: crypto.randomUUID(), sessions: [] })

export const useHqHistoryStore = create<HqHistoryState>()(
  persist(
    (set, get) => ({
      byProject: {},
      ensure: (project) => {
        const existing = get().byProject[project]
        if (existing) return existing
        const created = fresh()
        set((s) => ({ byProject: { ...s.byProject, [project]: created } }))
        return created
      },
      saveCurrent: (project, messages) => {
        const h = get().ensure(project)
        const sessions = upsertSession(h.sessions, h.currentId, messages, Date.now())
        if (sessions === h.sessions) return
        set((s) => ({ byProject: { ...s.byProject, [project]: { ...h, sessions } } }))
      },
      startNew: (project) => {
        const h = get().ensure(project)
        set((s) => ({ byProject: { ...s.byProject, [project]: { ...h, currentId: crypto.randomUUID() } } }))
      },
      open: (project, id) => {
        const h = get().ensure(project)
        const found = h.sessions.find((x) => x.id === id) ?? null
        if (found) set((s) => ({ byProject: { ...s.byProject, [project]: { ...h, currentId: id } } }))
        return found
      },
      adoptUnassigned: (project) => {
        const { [UNASSIGNED]: unassigned, ...rest } = get().byProject
        if (!unassigned || project === UNASSIGNED) return
        set({ byProject: { ...rest, [project]: adoptInto(rest[project], unassigned) } })
      },
    }),
    {
      name: 'pathly-hq-history',
      version: 2,
      partialize: (s) => ({ byProject: s.byProject }),
      migrate: (persisted, version) => migrateHqHistory(persisted, version) as unknown as HqHistoryState,
    },
  ),
)
