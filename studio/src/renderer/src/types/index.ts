export type PathlyItemType = 'flow' | 'skill' | 'agent' | 'template'

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
  state: string
  flow: string
  engine: string
  conv_count: number
}

export interface FsmEvent {
  ts: string
  type: string
  detail: string
}
