export type PathlyItemType = 'flow' | 'skill' | 'agent' | 'template' | 'debug' | 'explore' | 'plan'

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
  sourcePath: string
}

// Drag payload for moving an entire folder between workspace sections
export interface PathlyFolderDragItem {
  dragType: 'reorg-folder'
  name: string
  sourcePath: string  // absolute path of the folder
  sectionDir: string  // absolute path of the source section dir
}

export type PathlyDragItem = PathlyCanvasDragItem | PathlyReorgDragItem | PathlyFolderDragItem

// MIME key used for both drag types — differentiated by dragType field in payload
export const PATHLY_DRAG_MIME = 'application/pathly-drag-item'

export type CommentColor = 'yellow' | 'teal' | 'red' | 'purple' | 'grey'
export type CommentShape = 'sticky' | 'bubble'

export interface CommentEntry {
  id: string
  text: string
  color: CommentColor
  shape: CommentShape
  x: number
  y: number
  attachedTo?: string
}

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
  phases?: string
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
  pinned?: boolean
}

export interface FlowYaml {
  version: number
  flow: string
  states: string[]
  transitions: Record<string, string[]>
  agent_map: Record<string, string>
  adapter_map?: Record<string, string>   // CLI adapter per state: 'claude' | 'codex' | 'antigravity'
  skill_map?: Record<string, string>     // skill filename per state, e.g. 'build.md'
  transition_rules?: Record<string, unknown>
  transition_actions?: Record<string, unknown>
  storage_path?: string
  feedback_routing?: Record<string, unknown>
  role_map?: Record<string, string>
  _comments?: CommentEntry[]
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
  stage?: string
  next?: string
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

export interface FlowSession {
  flowKey: string
  topic: string
  isRunning: boolean
  isPaused: boolean
  isCli: false
}

export type FlowExportTarget = 'pathly-package' | 'claude-code' | 'codex'

export interface FlowExportRecord {
  target: FlowExportTarget
  path: string
  at: Date
}
