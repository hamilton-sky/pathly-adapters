// ── Command Center · domain & UI types ──────────────────────────────
// Mirrors the comms-board SPEC §5 message schema (trimmed to what the UI reads).

export type BoardScope = 'feature' | 'project' | 'global';

export type MessageType =
  | 'nudge' | 'decision' | 'question' | 'answer' | 'status'
  | 'discovery' | 'warning' | 'escalation' | 'task' | 'artifact';

export type Stage =
  | 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE';

export type AgentId =
  | 'you' | 'builder' | 'reviewer' | 'architect' | 'tester' | 'retro';

export type FeatureStatus = 'running' | 'idle' | 'blocked' | 'done';

export interface QuestionOption {
  id: string;
  label: string;
  desc?: string;
}

export interface Message {
  id: string;
  type: MessageType;
  from: AgentId;
  text: string;
  stage?: Stage | null;
  time: string;
  pinned?: boolean;
  ack?: boolean;
  /** question lifecycle */
  status?: 'pending' | 'answered' | 'open' | 'resolved';
  options?: QuestionOption[];
  answer?: string;
  /** warning / escalation resolution note */
  resolution?: string;
  /** artifact fields */
  artifact?: string;
  atype?: 'md' | 'code' | 'pdf' | 'image' | 'json' | 'url' | 'snippet';
}

export interface Feature {
  id: string;
  stage: Stage;
  conv: number;
  status: FeatureStatus;
  agent: AgentId;
  last: string;
  /** which boards this feature's agents read at /next_action */
  scope: Record<BoardScope, boolean>;
}

/** A board is just the list of messages at one scope. Feature boards are keyed
 *  by feature id; project/global are keyed by the literal scope name. */
export type Boards = Record<string, Message[]>;

export type Direction = 'row' | 'column';
export type Preset = 'board' | 'pipeline' | 'focus' | 'custom';

export interface CommandCenterState {
  sections: BoardScope[];      // visible board sections, in click order
  direction: Direction;        // side-by-side (row) | stacked (column)
  preset: Preset;
  mainFeature: string;
  sidebarCollapsed: boolean;
  openFeature: string | null;  // accordion — one open at a time
  sizes: Partial<Record<BoardScope, number>>;
}
