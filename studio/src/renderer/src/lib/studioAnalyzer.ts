import { useProjectStore } from '../store/projectStore'
import { useRunnerStore } from '../store/runnerStore'
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
    const text = content ?? ''
    return text.length > maxChars ? text.slice(0, maxChars) : text
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

  const base = `${projectPath}/pathly/features/${activeTopic}`
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

async function listPlans(): Promise<{ plans: Array<{ name: string; fsmStage: string; status: string }>; success: boolean }> {
  const { projectPath } = useProjectStore.getState()
  if (!projectPath) return { plans: [], success: true }
  const plansDir = `${projectPath}/pathly/features`
  const folders = await window.pathly.fs.listDirs(plansDir).catch(() => [] as string[])
  const plans = await Promise.all(
    folders
      .filter((f) => f !== '.archive')
      .map(async (name) => {
        const raw = await safeRead(`${plansDir}/${name}/STATE.json`, 2000)
        let fsmStage = 'unknown'
        if (raw) {
          try {
            const parsed = JSON.parse(raw) as { current?: string; stage?: string }
            fsmStage = parsed.current ?? parsed.stage ?? 'unknown'
          } catch {
            // ignore
          }
        }
        return { name, fsmStage, status: fsmStage }
      })
  )
  return { plans, success: true }
}

async function getEvents(params: unknown): Promise<{ events: string; success: boolean }> {
  const p = params as { feature?: string; limit?: number } | null
  const limit = Math.min(p?.limit ?? 20, 50)
  const { projectPath, activeTopic } = useProjectStore.getState()
  if (!projectPath) return { events: '', success: true }
  const topic = p?.feature ?? activeTopic
  if (!topic) return { events: '', success: true }
  const raw = await safeRead(`${projectPath}/pathly/features/${topic}/EVENTS.jsonl`, 50000)
  if (!raw) return { events: '', success: true }
  const lines = raw.split('\n').filter(Boolean)
  return { events: lines.slice(-limit).join('\n'), success: true }
}

async function getFailures(params: unknown): Promise<{ review: string; test: string; success: boolean }> {
  const p = params as { feature?: string; type?: 'review' | 'test' | 'all' } | null
  const type = p?.type ?? 'all'
  const { projectPath, activeTopic } = useProjectStore.getState()
  if (!projectPath) return { review: '', test: '', success: true }
  const topic = p?.feature ?? activeTopic
  if (!topic) return { review: '', test: '', success: true }
  const base = `${projectPath}/pathly/features/${topic}/feedback`
  const [review, test] = await Promise.all([
    type === 'test' ? Promise.resolve('') : safeRead(`${base}/REVIEW_FAILURES.md`, 3000),
    type === 'review' ? Promise.resolve('') : safeRead(`${base}/TEST_FAILURES.md`, 3000),
  ])
  return { review, test, success: true }
}

async function createPlan(params: unknown): Promise<{ path?: string; success: boolean; error?: string }> {
  const p = params as { featureName?: string; description?: string } | null
  const featureName = p?.featureName?.trim()
  if (!featureName) return { success: false, error: 'featureName is required' }
  const { projectPath } = useProjectStore.getState()
  if (!projectPath) return { success: false, error: 'No project path' }
  const plansDir = `${projectPath}/pathly/features`
  const existing = await window.pathly.fs.listDirs(plansDir).catch(() => [] as string[])
  if (existing.includes(featureName)) return { success: false, error: 'Plan already exists' }
  const planDir = `${plansDir}/${featureName}`
  const stateJson = JSON.stringify({ state: 'PLAN', feature: featureName, rigor: 'standard' }, null, 2)
  const desc = p?.description ? `\n${p.description}\n` : '\n'
  const storiesTemplate = `# ${featureName} — User Stories\n${desc}\n## Stories\n\n| ID | Title | Acceptance Criteria |\n|---|---|---|\n| S-01 | | |\n`
  await Promise.all([
    window.pathly.fs.write(`${planDir}/STATE.json`, stateJson),
    window.pathly.fs.write(`${planDir}/USER_STORIES.md`, storiesTemplate),
  ])
  return { path: `pathly/features/${featureName}`, success: true }
}

async function runSkill(params: unknown): Promise<{ success: boolean; runId?: string; error?: string }> {
  const p = params as { feature?: string; skill?: string } | null
  const feature = p?.feature
  const skill = p?.skill
  if (!feature) return { success: false, error: 'feature is required' }
  if (!skill) return { success: false, error: 'skill is required' }
  const { projectPath } = useProjectStore.getState()
  if (!projectPath) return { success: false, error: 'No project path' }
  return window.pathly.fsm.runSkill(feature, skill, projectPath)
}

// Valid panels: 'chat' | 'terminal' | 'plan' | 'editor' | 'flow' | 'monitor' | 'settings'
async function navigateTo(params: unknown): Promise<{ success: boolean; error?: string }> {
  const p = params as { panel?: string } | null
  const panel = p?.panel
  if (!panel) return { success: false, error: 'panel is required' }
  if (typeof window.__pathlyNavigate === 'function') {
    window.__pathlyNavigate(panel)
    return { success: true }
  }
  return { success: false, error: 'navigate not available' }
}

async function getLayout(): Promise<{ layout: object; success: boolean }> {
  // FlowControlBar uses aria-label (not data-label); label serves as dataLabel
  const buttons = [
    { label: 'Start', dataLabel: 'Start', panel: null, action: 'POST /runner/start' },
    { label: 'Pause', dataLabel: 'Pause', panel: null, action: 'POST /runner/pause' },
    { label: 'Resume', dataLabel: 'Resume', panel: null, action: 'POST /runner/resume' },
    { label: 'Advance', dataLabel: 'Advance', panel: null, action: 'POST /runner/advance' },
    { label: 'Reroute', dataLabel: 'Reroute', panel: null, action: 'shows reroute popover' },
    { label: 'Retry', dataLabel: 'Retry', panel: null, action: 'POST /runner/retry' },
    { label: 'Abort', dataLabel: 'Abort', panel: null, action: 'shows abort confirm strip' },
    { label: 'Monitor', dataLabel: 'Monitor', panel: 'monitor', action: 'navigate' },
    { label: 'Chat', dataLabel: 'Chat', panel: 'chat', action: 'navigate' },
    { label: 'Terminal', dataLabel: 'Terminal', panel: 'terminal', action: 'navigate' },
  ]
  const { activePanel } = useUiStore.getState()
  const { activeTopic } = useProjectStore.getState()
  const runner = useRunnerStore.getState()
  const terminal = useTerminalStore.getState()
  const terminalTabs = terminal.tabs.map((t) => ({ id: t.id, label: t.label, kind: t.kind ?? null }))
  const layout = {
    panels: ['monitor', 'plan', 'chat', 'flow', 'terminal'],
    buttons,
    currentPanel: activePanel,
    activeFeature: activeTopic,
    fsmStage: runner.stage ?? 'unknown',
    runnerStatus: runner.status,
    terminalTabs,
  }
  return { layout, success: true }
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
  'studio.list_plans': async () => listPlans(),
  'list_plans': async () => listPlans(),
  'studio.get_events': async (params) => getEvents(params),
  'get_events': async (params) => getEvents(params),
  'studio.get_failures': async (params) => getFailures(params),
  'get_failures': async (params) => getFailures(params),
  'studio.create_plan': async (params) => createPlan(params),
  'create_plan': async (params) => createPlan(params),
  'studio.navigate_to': async (params) => navigateTo(params),
  'navigate_to': async (params) => navigateTo(params),
  'studio.run_skill': async (params) => runSkill(params),
  'run_skill': async (params) => runSkill(params),
  'studio.get_layout': async () => getLayout(),
  'get_layout': async () => getLayout(),
}

export async function executeStudioTool(toolName: string, parameters: unknown): Promise<unknown> {
  const handler = studioTools[toolName]
  if (!handler) {
    throw new Error(`Unknown tool: ${toolName}`)
  }
  return handler(parameters)
}
