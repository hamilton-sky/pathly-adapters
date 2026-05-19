import type { FlowYaml } from '../../../types'

export type FlowValidationScope = 'node' | 'edge' | 'field'

export interface FlowValidationIssue {
  scope: FlowValidationScope
  /** State id for node issues; "SOURCE->TARGET" for edge issues */
  key: string
  message: string
  severity: 'error' | 'warning'
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
      issues.push({ scope: 'node', key: source, message: `Source state ${source} missing from states list`, severity: 'error' })
    }
    for (const target of targets) {
      if (!stateSet.has(target)) {
        issues.push({
          scope: 'edge',
          key: `${source}->${target}`,
          message: `Target state ${target} missing`,
          severity: 'error'
        })
      }
    }
  }

  // Non-terminal states must have at least one outgoing transition
  for (const state of data.states ?? []) {
    const outs = data.transitions[state] ?? []
    if (outs.length === 0) {
      // Only a warning — terminal states are valid
      issues.push({ scope: 'node', key: state, message: `State ${state} has no outgoing transitions`, severity: 'warning' })
    }
  }

  // Validate transition_rules are state-keyed and targets are in transitions
  const rules = (data.transition_rules as Record<string, unknown> | undefined) ?? {}
  for (const [sourceKey, ruleUnknown] of Object.entries(rules)) {
    if (!stateSet.has(sourceKey)) {
      issues.push({ scope: 'node', key: sourceKey, message: `transition_rules key ${sourceKey} not in states`, severity: 'error' })
      continue
    }
    const rule = ruleUnknown as StateRule
    const declaredTargets = new Set(data.transitions[sourceKey] ?? [])

    if (rule.default !== undefined && rule.default !== '' && !declaredTargets.has(rule.default)) {
      issues.push({
        scope: 'edge',
        key: `${sourceKey}->${rule.default}`,
        message: `Default target ${rule.default} not in transitions for ${sourceKey}`,
        severity: 'error'
      })
    }

    if (rule.on_artifact) {
      for (const [, target] of Object.entries(rule.on_artifact)) {
        if (target && !declaredTargets.has(target)) {
          issues.push({
            scope: 'edge',
            key: `${sourceKey}->${target}`,
            message: `on_artifact target ${target} not in transitions for ${sourceKey}`,
            severity: 'error'
          })
        }
      }
    }

    if (rule.on_content) {
      for (const entry of rule.on_content) {
        if (entry.next && !declaredTargets.has(entry.next)) {
          issues.push({
            scope: 'edge',
            key: `${sourceKey}->${entry.next}`,
            message: `on_content target ${entry.next} not in transitions for ${sourceKey}`,
            severity: 'error'
          })
        }
      }
    }

    if (rule.decide?.options) {
      for (const [, target] of Object.entries(rule.decide.options)) {
        if (target && !declaredTargets.has(target)) {
          issues.push({
            scope: 'edge',
            key: `${sourceKey}->${target}`,
            message: `decide target ${target} not in transitions for ${sourceKey}`,
            severity: 'error'
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
      issues.push({ scope: 'edge', key, message: `transition_actions key "${key}" must use SOURCE->TARGET format`, severity: 'error' })
      continue
    }
    const src = key.slice(0, arrowIdx)
    const tgt = key.slice(arrowIdx + 2)
    if (src && !stateSet.has(src)) {
      issues.push({ scope: 'edge', key, message: `transition_actions source ${src} not in states`, severity: 'error' })
    }
    if (tgt && !stateSet.has(tgt)) {
      issues.push({ scope: 'edge', key, message: `transition_actions target ${tgt} not in states`, severity: 'error' })
    }
  }

  // Validate referenced behaviors exist
  if (behaviorSet.size > 0) {
    for (const [state, behavior] of Object.entries(data.agent_map ?? {})) {
      if (behavior && !behaviorSet.has(behavior)) {
        issues.push({ scope: 'node', key: state, message: `Behavior ${behavior} not in library`, severity: 'warning' })
      }
    }
  }

  return issues
}
