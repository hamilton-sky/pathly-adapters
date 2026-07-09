// Command Center — domain & UI types
// Mirrors the comms-board SPEC §5 message schema (trimmed to what the UI reads).
// Field names align with GET /comms payload shape.

export type BoardScope = 'feature' | 'project' | 'global'

export type MessageType =
  | 'nudge' | 'decision' | 'question' | 'answer' | 'status'
  | 'discovery' | 'warning' | 'escalation' | 'task' | 'artifact' | 'goal'
  | 'phase' | 'note'

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
  /** Raw agent role from the server — 'you' for the human, or any agent name
   *  (builder, explorer, evaluator, system, …). Not limited to AgentId. */
  from: string
  text: string
  stage?: Stage | null
  /** Raw ISO timestamp (maps to comms_messages.ts). The single time source: cards
   *  render it through the shared `<Timestamp>` util, and it orders messages —
   *  e.g. supersede only by a newer one. */
  ts?: string
  pinned?: boolean
  ack?: boolean
  status?: 'pending' | 'answered' | 'open' | 'resolved'
  options?: QuestionOption[]
  answer?: string
  resolution?: string
  artifact?: string
  /** Full path of the attached artifact (maps to comms_messages.artifact_path) —
   *  used to open it in the editor. `artifact` is just the basename for display. */
  artifactPath?: string
  atype?: 'md' | 'code' | 'pdf' | 'image' | 'json' | 'url' | 'snippet'
  /** Set when this message has been superseded by a newer one (maps to
   *  comms_messages.superseded_by; surfaced as a struck-through card). */
  supersededBy?: string
  /** True once any agent has read this message. Maps to a non-empty read_by
   *  (SPEC §5). Your own messages can be retracted only while this is false. */
  readByAgent?: boolean
  /** Goal id — set on task messages to link them to their parent goal. */
  goal_id?: string
  /** Executor type — set on goal messages (single | loop | team). */
  executor?: 'single' | 'loop' | 'team'
  /** Task lifecycle status — set on task messages (maps to comms_messages.task_status). */
  taskStatus?: 'pending' | 'in_progress' | 'done' | 'blocked' | 'failed'
  /** Dependency task ids — set on task messages (maps to comms_messages.depends_on JSON). */
  dependsOn?: string[]
}

export interface Feature {
  id: string
  stage: Stage
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

export type SectionDef =
  | { id: string; scope: 'feature'; featureId: string }
  | { id: 'project'; scope: 'project' }
  | { id: 'global'; scope: 'global' }

export const MAX_SECTIONS = 3

export interface CommandCenterState {
  sections: SectionDef[]
  featureTabs: string[]
  direction: Direction
  preset: Preset
  mainFeature: string
  sidebarCollapsed: boolean
  openFeature: string | null
  sizes: Partial<Record<string, number>>
}
