import type { FlowExportTarget } from '../../../types'

export interface FlowExportContext {
  projectPath: string
  flowName: string
}

export function resolveExportPath(target: FlowExportTarget, ctx: FlowExportContext): string {
  switch (target) {
    case 'pathly-package': return `${ctx.projectPath}/src/pathly_data/core/flows/${ctx.flowName}.flow.yaml`
    case 'claude-code':    return `${ctx.projectPath}/.claude/pathly-flows/${ctx.flowName}.flow.yaml`
    case 'codex':          return `${ctx.projectPath}/.codex/pathly-flows/${ctx.flowName}.flow.yaml`
  }
}
