export type PathlyItemType = 'flow' | 'skill' | 'agent' | 'template' | 'debug' | 'explore'

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
