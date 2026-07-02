import type { ItemKind, PlanState, TreeNode } from '../types'

/** Accent colour per item kind (Pathly CSS custom properties). */
export const KIND_COLOR: Record<ItemKind, string> = {
  flow: 'var(--blue)',
  skill: 'var(--green)',
  agent: 'var(--purple)',
  plan: 'var(--accent)',
  folder: 'var(--accent)',
  file: 'var(--text-muted)',
}

/** Colour per plan lifecycle state (drives the pill). */
export const STATE_COLOR: Record<PlanState, string> = {
  PLANNING: 'var(--text-muted)',
  BUILDING: 'var(--blue)',
  REVIEWING: 'var(--orange)',
  TESTING: 'var(--purple)',
  RETRO: 'var(--runtime)',
  DONE: 'var(--green)',
}

/** Extension appended when creating a typed artifact inside its section. */
export const EXT: Partial<Record<'flow' | 'skill' | 'agent', string>> = {
  flow: '.flow.yaml',
  skill: '.skill.md',
  agent: '.agent.md',
}

/** Classify a node for icon + context-menu purposes. */
export function kindOf(path: string, node: TreeNode): ItemKind {
  if (node.type === 'folder') {
    return /(^|\/)plans\/[^/]+$/.test(path) ? 'plan' : 'folder'
  }
  if (/\.flow\.yaml$/.test(node.name)) return 'flow'
  if (/\.skill\.md$/.test(node.name)) return 'skill'
  if (/\.agent\.md$/.test(node.name)) return 'agent'
  return 'file'
}

export const KIND_LABEL: Record<ItemKind, string> = {
  flow: 'Flow',
  skill: 'Skill',
  agent: 'Agent',
  plan: 'Plan',
  folder: 'Folder',
  file: 'File',
}
