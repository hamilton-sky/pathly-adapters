export interface Transition {
  from: string
  to: string
  label: string
}

export interface Gate {
  type: 'verify_gate' | 'scope_gate' | 'require_artifact'
  artifact?: string
  pass_marker?: string
  scope_file?: string
  on_fail?: string
}

export interface ArtifactCondition {
  artifact: string
  target: string
}

export interface TransitionRule {
  conditions: ArtifactCondition[]
  default: string
}

export interface FeedbackRoute {
  tag: string
  agent: string
}

export interface Props {
  onClose: () => void
  onCreated: (filePath: string) => void
}

export type BlockMap = Record<string, string>
