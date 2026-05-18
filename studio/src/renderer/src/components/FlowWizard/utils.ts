import type { Transition } from './types'

export function generateYaml(
  flowName: string,
  storagePath: string,
  states: string[],
  agentMap: Record<string, string>,
  transitions: Transition[]
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

  return lines.join('\n')
}
