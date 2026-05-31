import { useProjectStore } from '../store/projectStore'
import { useTerminalStore } from '../store/terminalStore'
import { useUiStore } from '../store/uiStore'

type FsmState = {
  current?: string
  stage?: string
  feature?: string
  rigor?: string
}

type ToolHandler = (params: unknown) => Promise<unknown>

async function safeRead(path: string, maxChars: number): Promise<string> {
  try {
    const content = await window.pathly.fs.read(path)
    return content.length > maxChars ? content.slice(0, maxChars) : content
  } catch {
    return ''
  }
}

async function getFsmState(): Promise<{ stage: string; feature: string; rigor: string }> {
  const { activeTopic } = useProjectStore.getState()
  if (!activeTopic) {
    return { stage: 'unknown', feature: '', rigor: 'lite' }
  }

  const state = (await window.pathly.fsm.state(activeTopic).catch(() => null)) as FsmState | null
  return {
    stage: state?.stage ?? state?.current ?? 'unknown',
    feature: state?.feature ?? activeTopic,
    rigor: state?.rigor ?? 'lite',
  }
}

async function getFeaturePlan(): Promise<{
  userStories: string
  implementationPlan: string
  progress: string
  success: boolean
}> {
  const { projectPath, activeTopic } = useProjectStore.getState()
  if (!projectPath || !activeTopic) {
    return { userStories: '', implementationPlan: '', progress: '', success: true }
  }

  const base = `${projectPath}/pathly/plans/${activeTopic}`
  const [userStories, implementationPlan, progress] = await Promise.all([
    safeRead(`${base}/USER_STORIES.md`, 2000),
    safeRead(`${base}/IMPLEMENTATION_PLAN.md`, 4000),
    safeRead(`${base}/PROGRESS.md`, 1000),
  ])

  return { userStories, implementationPlan, progress, success: true }
}

function getStudioSchema(): { openPanels: string[]; activeTab: string } {
  const ui = useUiStore.getState()
  const terminal = useTerminalStore.getState()
  const openPanels = [
    ui.activePanel,
    ui.chatOpen ? 'chat' : null,
    ui.skillsPanelOpen ? 'skills' : null,
    terminal.open ? 'terminal' : null,
  ].filter((value): value is string => Boolean(value))
  const activeTab = terminal.activeTabIdLeft ?? terminal.activeTabIdRight ?? ui.activePanel
  return { openPanels, activeTab }
}

async function automationExecuteStep(params: unknown): Promise<unknown> {
  return window.pathly.automation.executeStep(params as { type: 'click' | 'fill' | 'select' | 'navigate'; label: string; value?: string })
}

const studioTools: Record<string, ToolHandler> = {
  'get_fsm_state': async () => getFsmState(),
  'studio.get_fsm_state': async () => getFsmState(),
  'get_feature_plan': async () => getFeaturePlan(),
  'studio.get_feature_plan': async () => getFeaturePlan(),
  'get_studio_schema': async () => getStudioSchema(),
  'studio.get_studio_schema': async () => getStudioSchema(),
  'automation:executeStep': async (params) => automationExecuteStep(params),
  'studio.automation.executeStep': async (params) => automationExecuteStep(params),
}

export async function executeStudioTool(toolName: string, parameters: unknown): Promise<unknown> {
  const handler = studioTools[toolName]
  if (!handler) {
    throw new Error(`Unknown tool: ${toolName}`)
  }
  return handler(parameters)
}
