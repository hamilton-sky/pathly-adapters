import { useProjectStore } from '../store/projectStore'

type FsmState = {
  stage?: string
  conversationIndex?: number
  totalConversations?: number
  feature?: string
  current?: string
  current_conversation?: number
  conv?: number
  current_state?: string
}

export type AppContext = {
  source: 'pathly-studio'
  projectPath: string
  appContext?: {
    activeFeature?: string
    fsmStage?: string
    activeConversation?: number
    totalConversations?: number
    nextUncompletedStory?: string
    userStoriesSummary?: string
  }
}

function getPlanPath(projectPath: string, topic: string): string {
  return `${projectPath}/pathly/plans/${topic}`
}

export async function safeRead(path: string, maxChars: number): Promise<string> {
  try {
    const content = await window.pathly.fs.read(path)
    const text = content ?? ''
    return text.length > maxChars ? text.slice(0, maxChars) : text
  } catch {
    return ''
  }
}

export function parseNextTodo(progressMd: string): string {
  const lines = progressMd.split(/\r?\n/)
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('|') && trimmed.includes('TODO')) return trimmed
  }
  return ''
}

export async function collectPathlyContext(): Promise<AppContext> {
  const { projectPath, activeTopic } = useProjectStore.getState()
  const base: AppContext = { source: 'pathly-studio', projectPath }

  if (!activeTopic) return base

  const fsmState = (await window.pathly.fsm.state(activeTopic).catch(() => null)) as FsmState | null
  if (!fsmState) return base

  const planPath = getPlanPath(projectPath, activeTopic)
  const [progressMd, userStoriesMd] = await Promise.all([
    safeRead(`${planPath}/PROGRESS.md`, 500),
    safeRead(`${planPath}/USER_STORIES.md`, 2000),
  ])

  return {
    ...base,
    appContext: {
      activeFeature: activeTopic,
      fsmStage: fsmState.stage ?? fsmState.current_state ?? fsmState.current,
      activeConversation: fsmState.conversationIndex ?? fsmState.current_conversation ?? fsmState.conv,
      totalConversations: fsmState.totalConversations,
      nextUncompletedStory: parseNextTodo(progressMd),
      userStoriesSummary: userStoriesMd,
    },
  }
}
