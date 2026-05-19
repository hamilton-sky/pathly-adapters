import type { FlowYaml } from '../../../types'

export type FlowValidationScope = 'flow' | 'node' | 'edge' | 'export'

export interface FlowValidationIssue {
  target: FlowValidationScope
  /** State id for node issues; "SOURCE->TARGET" for edge issues */
  id: string
  message: string
  level: 'error' | 'warning'
}

interface StateRule {
  default?: string
  on_artifact?: Record<string, string>
  on_content?: Array<{ file?: string; contains?: string; regex?: string; next: string }>
  decide?: { question?: string; options?: Record<string, string>; default?: string }
}

export function validateFlow(data: FlowYaml, knownBehaviors: string[] = []): FlowValidationIssue[] {
  const issues: FlowValidationIssue[] = []
  const stateSet = new Set(data.states ?? [])
  const behaviorSet = new Set(knownBehaviors)

  // Check every transition source/target exists in states
  for (const [source, targets] of Object.entries(data.transitions ?? {})) {
    if (!stateSet.has(source)) {
      issues.push({ target: 'node', id: source, message: `Source state ${source} missing from states list`, level: 'error' })
    }
    for (const tgt of targets) {
      if (!stateSet.has(tgt)) {
        issues.push({
          target: 'edge',
          id: `${source}->${tgt}`,
          message: `Target state ${tgt} missing`,
          level: 'error'
        })
      }
    }
  }

  // Non-terminal states must have at least one outgoing transition
  for (const state of data.states ?? []) {
    const outs = data.transitions[state] ?? []
    if (outs.length === 0) {
      // Only a warning — terminal states are valid
      issues.push({ target: 'node', id: state, message: `State ${state} has no outgoing transitions`, level: 'warning' })
    }
  }

  // Validate transition_rules are state-keyed and targets are in transitions
  const rules = (data.transition_rules as Record<string, unknown> | undefined) ?? {}
  for (const [sourceKey, ruleUnknown] of Object.entries(rules)) {
    if (!stateSet.has(sourceKey)) {
      issues.push({ target: 'node', id: sourceKey, message: `transition_rules key ${sourceKey} not in states`, level: 'error' })
      continue
    }
    const rule = ruleUnknown as StateRule
    const declaredTargets = new Set(data.transitions[sourceKey] ?? [])

    if (rule.default !== undefined && rule.default !== '' && !declaredTargets.has(rule.default)) {
      issues.push({
        target: 'edge',
        id: `${sourceKey}->${rule.default}`,
        message: `Default target ${rule.default} not in transitions for ${sourceKey}`,
        level: 'error'
      })
    }

    if (rule.on_artifact) {
      for (const [, tgt] of Object.entries(rule.on_artifact)) {
        if (tgt && !declaredTargets.has(tgt)) {
          issues.push({
            target: 'edge',
            id: `${sourceKey}->${tgt}`,
            message: `on_artifact target ${tgt} not in transitions for ${sourceKey}`,
            level: 'error'
          })
        }
      }
    }

    if (rule.on_content) {
      for (const entry of rule.on_content) {
        if (entry.next && !declaredTargets.has(entry.next)) {
          issues.push({
            target: 'edge',
            id: `${sourceKey}->${entry.next}`,
            message: `on_content target ${entry.next} not in transitions for ${sourceKey}`,
            level: 'error'
          })
        }
      }
    }

    if (rule.decide?.options) {
      for (const [, tgt] of Object.entries(rule.decide.options)) {
        if (tgt && !declaredTargets.has(tgt)) {
          issues.push({
            target: 'edge',
            id: `${sourceKey}->${tgt}`,
            message: `decide target ${tgt} not in transitions for ${sourceKey}`,
            level: 'error'
          })
        }
      }
    }
  }

  // Validate transition_actions keys use SOURCE->TARGET format pointing to known transitions
  const actions = (data.transition_actions as Record<string, unknown> | undefined) ?? {}
  for (const key of Object.keys(actions)) {
    const arrowIdx = key.indexOf('->')
    if (arrowIdx === -1) {
      issues.push({ target: 'edge', id: key, message: `transition_actions key "${key}" must use SOURCE->TARGET format`, level: 'error' })
      continue
    }
    const src = key.slice(0, arrowIdx)
    const tgt = key.slice(arrowIdx + 2)
    if (src && !stateSet.has(src)) {
      issues.push({ target: 'edge', id: key, message: `transition_actions source ${src} not in states`, level: 'error' })
    }
    if (tgt && !stateSet.has(tgt)) {
      issues.push({ target: 'edge', id: key, message: `transition_actions target ${tgt} not in states`, level: 'error' })
    }
  }

  // Validate referenced behaviors exist
  if (behaviorSet.size > 0) {
    for (const [state, behavior] of Object.entries(data.agent_map ?? {})) {
      if (behavior && !behaviorSet.has(behavior)) {
        issues.push({ target: 'node', id: state, message: `Behavior ${behavior} not in library`, level: 'warning' })
      }
    }
  }

  return issues
}
