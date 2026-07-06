import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PathlyItem, ProjectEntry, FsmState, FsmEvent } from '../types'

export interface ProjectState {
  projectPath: string
  pathlyRoot: string
  pathlyUserHome: string
  projects: ProjectEntry[]
  activeTopic: string | null
  selectedItem: PathlyItem | null
  fsmState: FsmState | null
  events: FsmEvent[]
  pipelineStates: string[]
  monitorSource: 'chokidar' | 'sse' | null
  publishing: boolean
  publishLog: string[]
  setProjectPath: (p: string) => void
  setPathlyRoot: (p: string) => void
  setPathlyUserHome: (p: string) => void
  setActiveTopic: (t: string | null) => void
  setSelectedItem: (item: PathlyItem | null) => void
  addProject: (p: ProjectEntry) => void
  removeProject: (path: string) => void
  updateProject: (path: string, patch: Partial<ProjectEntry>) => void
  setFsmState: (s: FsmState | null) => void
  setEvents: (e: FsmEvent[]) => void
  setPipelineStates: (s: string[]) => void
  setMonitorSource: (s: 'chokidar' | 'sse' | null) => void
  setPublishing: (v: boolean) => void
  appendPublishLog: (line: string) => void
  clearPublishLog: () => void
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set) => ({
      projectPath: '',
      pathlyRoot: '',
      pathlyUserHome: '',
      projects: [],
      activeTopic: null,
      selectedItem: null,
      fsmState: null,
      events: [],
      pipelineStates: [],
      monitorSource: null,
      publishing: false,
      publishLog: [],
      setProjectPath: (p) => set({ projectPath: p }),
      setPathlyRoot: (p) => set({ pathlyRoot: p }),
      setPathlyUserHome: (p) => set({ pathlyUserHome: p }),
      setActiveTopic: (t) => set({ activeTopic: t }),
      setSelectedItem: (item) => set({ selectedItem: item }),
      addProject: (p) => set((s) => ({
        projects: s.projects.some((x) => x.path === p.path)
          ? s.projects.map((x) => (x.path === p.path ? { ...x, ...p } : x))
          : [...s.projects, p],
      })),
      removeProject: (path) => set((s) => ({ projects: s.projects.filter((p) => p.path !== path) })),
      updateProject: (path, patch) =>
        set((s) => ({
          projects: s.projects.map((p) => (p.path === path ? { ...p, ...patch } : p)),
        })),
      setFsmState: (s) => set({ fsmState: s }),
      setEvents: (e) => set({ events: e }),
      setPipelineStates: (s) => set({ pipelineStates: s }),
      setMonitorSource: (s) => set({ monitorSource: s }),
      setPublishing: (v) => set({ publishing: v }),
      appendPublishLog: (line) => set((s) => ({ publishLog: [...s.publishLog, line] })),
      clearPublishLog: () => set({ publishLog: [] }),
    }),
    {
      name: 'pathly-studio-project',
      partialize: (s) => ({ projects: s.projects, pathlyRoot: s.pathlyRoot }),
    }
  )
)
