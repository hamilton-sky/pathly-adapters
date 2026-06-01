import type { Transition, Gate, TransitionRule, FeedbackRoute } from './types'

export function generateYaml(
  flowName: string,
  storagePath: string,
  states: string[],
  agentMap: Record<string, string>,
  transitions: Transition[],
  gates: Record<string, Gate[]>,
  feedbackRoutes: FeedbackRoute[],
  transitionRules: Record<string, TransitionRule>,
  adapterMap: Record<string, string> = {}
): string {
  const transitionMap: Record<string, string[]> = {}
  for (const tr of transitions) {
    if (!transitionMap[tr.from]) transitionMap[tr.from] = []
    if (!transitionMap[tr.from].includes(tr.to)) {
      transitionMap[tr.from].push(tr.to)
    }
  }

  const lines: string[] = [
    `version: 1`,
    `flow: ${flowName}`,
    `storage_path: "${storagePath}"`,
    ``,
    `states:`
  ]
  for (const s of states) {
    lines.push(`  - ${s}`)
  }

  lines.push(``)
  lines.push(`agent_map:`)
  for (const s of states) {
    if (agentMap[s]) {
      lines.push(`  ${s}: ${agentMap[s]}`)
    }
  }

  // adapter_map — omit when trivially default (only { default: 'claude' }, no state overrides)
  const adapterKeys = Object.keys(adapterMap)
  if (adapterKeys.length > 0 && !(adapterKeys.length === 1 && adapterMap['default'] === 'claude')) {
    lines.push(``)
    lines.push(`adapter_map:`)
    if ('default' in adapterMap) {
      lines.push(`  default: ${adapterMap['default']}`)
    }
    for (const s of states) {
      if (adapterMap[s]) {
        lines.push(`  ${s}: ${adapterMap[s]}`)
      }
    }
  }

  lines.push(``)
  lines.push(`transitions:`)
  for (const s of states) {
    const targets = transitionMap[s]
    if (targets && targets.length > 0) {
      lines.push(`  ${s}:`)
      for (const target of targets) {
        lines.push(`    - ${target}`)
      }
    }
  }

  // feedback_routing
  const validRoutes = feedbackRoutes.filter((r) => r.tag.trim() && r.agent.trim())
  if (validRoutes.length > 0) {
    lines.push(``)
    lines.push(`feedback_routing:`)
    for (const r of validRoutes) {
      lines.push(`  ${r.tag}: ${r.agent}`)
    }
  }

  // transition_rules
  const ruleEntries = Object.entries(transitionRules).filter(
    ([, rule]) => rule.conditions.length > 0 || rule.default.trim()
  )
  if (ruleEntries.length > 0) {
    lines.push(``)
    lines.push(`transition_rules:`)
    for (const [state, rule] of ruleEntries) {
      lines.push(`  ${state}:`)
      const validConds = rule.conditions.filter((c) => c.artifact.trim() && c.target.trim())
      if (validConds.length > 0) {
        lines.push(`    on_artifact:`)
        for (const c of validConds) {
          lines.push(`      ${c.artifact}: ${c.target}`)
        }
      }
      if (rule.default.trim()) {
        lines.push(`    default: ${rule.default}`)
      }
    }
  }

  // gates
  const gateEntries = Object.entries(gates).filter(([, gs]) => gs.length > 0)
  if (gateEntries.length > 0) {
    lines.push(``)
    lines.push(`gates:`)
    for (const [key, gs] of gateEntries) {
      lines.push(`  ${key}:`)
      for (const g of gs) {
        lines.push(`    - type: ${g.type}`)
        if (g.type === 'verify_gate') {
          if (g.artifact) lines.push(`      artifact: ${g.artifact}`)
          if (g.pass_marker) lines.push(`      pass_marker: "${g.pass_marker}"`)
          if (g.on_fail) lines.push(`      on_fail: ${g.on_fail}`)
        } else if (g.type === 'scope_gate') {
          if (g.scope_file) lines.push(`      scope_file: ${g.scope_file}`)
          if (g.on_fail) lines.push(`      on_fail: ${g.on_fail}`)
        } else if (g.type === 'require_artifact') {
          if (g.artifact) lines.push(`      artifact: ${g.artifact}`)
          if (g.on_fail) lines.push(`      on_fail: ${g.on_fail}`)
        }
      }
    }
  }

  return lines.join('\n')
}
