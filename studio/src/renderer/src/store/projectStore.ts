import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PathlyItem, ProjectEntry, FsmState, FsmEvent } from '../types'

interface ProjectState {
  projectPath: string
  projects: ProjectEntry[]
  activeTopic: string | null
  selectedItem: PathlyItem | null
  fsmState: FsmState | null
  events: FsmEvent[]
  monitorSource: 'mcp' | 'chokidar' | null
  publishing: boolean
  publishLog: string[]
  mcpCommand: string
  routingEngine: 'python-mcp' | 'llm'
  setProjectPath: (p: string) => void
  setActiveTopic: (t: string | null) => void
  setSelectedItem: (item: PathlyItem | null) => void
  addProject: (p: ProjectEntry) => void
  removeProject: (path: string) => void
  updateProject: (path: string, patch: Partial<ProjectEntry>) => void
  setFsmState: (s: FsmState | null) => void
  setEvents: (e: FsmEvent[]) => void
  setMonitorSource: (s: 'mcp' | 'chokidar' | null) => void
  setPublishing: (v: boolean) => void
  appendPublishLog: (line: string) => void
  clearPublishLog: () => void
  setMcpCommand: (s: string) => void
  setRoutingEngine: (e: 'python-mcp' | 'llm') => void
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set) => ({
      projectPath: '',
      projects: [],
      activeTopic: null,
      selectedItem: null,
      fsmState: null,
      events: [],
      monitorSource: null,
      publishing: false,
      publishLog: [],
      mcpCommand: 'pathly-mcp-server',
      routingEngine: 'llm',
      setProjectPath: (p) => set({ projectPath: p }),
      setActiveTopic: (t) => set({ activeTopic: t }),
      setSelectedItem: (item) => set({ selectedItem: item }),
      addProject: (p) => set((s) => ({ projects: [...s.projects, p] })),
      removeProject: (path) => set((s) => ({ projects: s.projects.filter((p) => p.path !== path) })),
      updateProject: (path, patch) =>
        set((s) => ({
          projects: s.projects.map((p) => (p.path === path ? { ...p, ...patch } : p)),
        })),
      setFsmState: (s) => set({ fsmState: s }),
      setEvents: (e) => set({ events: e }),
      setMonitorSource: (s) => set({ monitorSource: s }),
      setPublishing: (v) => set({ publishing: v }),
      appendPublishLog: (line) => set((s) => ({ publishLog: [...s.publishLog, line] })),
      clearPublishLog: () => set({ publishLog: [] }),
      setMcpCommand: (s) => set({ mcpCommand: s }),
      setRoutingEngine: (e) => set({ routingEngine: e }),
    }),
    {
      name: 'pathly-studio-project',
      partialize: (s) => ({ projects: s.projects, mcpCommand: s.mcpCommand, routingEngine: s.routingEngine }),
    }
  )
)
