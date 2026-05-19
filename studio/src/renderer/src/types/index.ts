export type PathlyItemType = 'flow' | 'skill' | 'agent' | 'template' | 'debug' | 'explore'

// Sidebar section domains — the four managed directories
export type PathlySection = 'skills' | 'agents' | 'flows' | 'templates'

// A node in the filesystem tree (file or category folder)
export interface PathlyTreeNode {
  name: string
  type: 'file' | 'folder'
  path: string[]
  section: PathlySection
  children?: PathlyTreeNode[]
  handle?: FileSystemHandle
}

// Drag payload for canvas assignment (from ⠿ grip — skills and agents only)
export interface PathlyCanvasDragItem {
  dragType: 'canvas'
  name: string
  section: PathlySection
  path: string[]
}

// Drag payload for tree reorg (from row body — all file/folder items)
export interface PathlyReorgDragItem {
  dragType: 'reorg'
  name: string
  section: PathlySection
  path: string[]
  type: 'file' | 'folder'
}

export type PathlyDragItem = PathlyCanvasDragItem | PathlyReorgDragItem

// MIME key used for both drag types — differentiated by dragType field in payload
export const PATHLY_DRAG_MIME = 'application/pathly-drag-item'

export interface TemplateSubdir {
  name: string
  open: boolean
  files: PathlyItem[]
}

export interface SectionState {
  items: PathlyItem[]
  open: boolean
  subdirs?: TemplateSubdir[] | null
}

export interface ConvRow {
  num: number
  title: string
  status: string
}

export interface PathlyItem {
  name: string
  path: string
  type: PathlyItemType
}

export interface ProjectEntry {
  path: string
  name: string
  lastOpened: number
  activeTopic?: string
  fsmState?: string
}

export interface FlowYaml {
  version: number
  flow: string
  states: string[]
  transitions: Record<string, string[]>
  agent_map: Record<string, string>
  transition_rules?: Record<string, unknown>
  transition_actions?: Record<string, unknown>
  storage_path?: string
  feedback_routing?: Record<string, unknown>
}

export interface FsmState {
  current: string
  flow?: string
  feature?: string
  rigor?: string
  conv?: number
  current_conversation?: number
  updated_at?: string
  [key: string]: unknown
}

export interface FsmEvent {
  type: string
  ts?: string
  timestamp?: string      // some runners use this instead of ts
  detail?: string
  from?: string
  to?: string
  reason?: string
  agent?: string
  model?: string
  result?: 'PASS' | 'DONE' | string
  conversation?: number
  tool_uses?: number
  wall_seconds?: number
  cost_usd?: number
  tokens_in?: number
  tokens_out?: number
  file?: string
  key?: string
  value?: string
  note?: string
  [key: string]: unknown
}

export interface SkillFrontmatter {
  type: 'skill'
  name?: string
  description?: string
  adapters?: string[]
  tools?: string[]
}

export interface AgentFrontmatter {
  type: 'agent'
  name?: string
  description?: string
  adapters?: string[]
  model?: string
}

export interface TemplateFrontmatter {
  type: 'template'
  name?: string
  category?: string
}

export type FrontmatterValues = SkillFrontmatter | AgentFrontmatter | TemplateFrontmatter
