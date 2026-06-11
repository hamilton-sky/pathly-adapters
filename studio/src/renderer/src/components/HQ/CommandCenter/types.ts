// Command Center — domain & UI types
// Mirrors the comms-board SPEC §5 message schema (trimmed to what the UI reads).
// Field names align with GET /comms payload shape.

export type BoardScope = 'feature' | 'project' | 'global'

export type MessageType =
  | 'nudge' | 'decision' | 'question' | 'answer' | 'status'
  | 'discovery' | 'warning' | 'escalation' | 'task' | 'artifact'

export type Stage =
  | 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE'

export type AgentId =
  | 'you' | 'builder' | 'reviewer' | 'architect' | 'tester' | 'retro'

export type FeatureStatus = 'running' | 'idle' | 'blocked' | 'done'

export interface QuestionOption {
  id: string
  label: string
  desc?: string
}

export interface Message {
  id: string
  type: MessageType
  from: AgentId
  text: string
  stage?: Stage | null
  time: string
  pinned?: boolean
  ack?: boolean
  status?: 'pending' | 'answered' | 'open' | 'resolved'
  options?: QuestionOption[]
  answer?: string
  resolution?: string
  artifact?: string
  atype?: 'md' | 'code' | 'pdf' | 'image' | 'json' | 'url' | 'snippet'
  /** True once any agent has read this message. Maps to a non-empty read_by
   *  (SPEC §5). Your own messages can be retracted only while this is false. */
  readByAgent?: boolean
}

export interface Feature {
  id: string
  stage: Stage
  conv: number
  status: FeatureStatus
  agent: AgentId
  last: string
  scope: Record<BoardScope, boolean>
}

/** A board is the list of messages at one scope. Feature boards are keyed
 *  by feature id; project/global are keyed by the literal scope name. */
export type Boards = Record<string, Message[]>

export type Direction = 'row' | 'column'
export type Preset = 'board' | 'pipeline' | 'focus' | 'custom'

export interface CommandCenterState {
  sections: BoardScope[]
  direction: Direction
  preset: Preset
  mainFeature: string
  sidebarCollapsed: boolean
  openFeature: string | null
  sizes: Partial<Record<BoardScope, number>>
}
