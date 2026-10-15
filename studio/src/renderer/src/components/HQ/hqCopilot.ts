// HQ copilot (pathly/features/hq-copilot): when a board is open, HQ's local
// model answers from a live, token-budgeted board packet that the SERVER
// assembles. POST /hq/prompt returns the exact system prompt + user turn to
// send (or a read-only redirect for an action request), plus the manifest of
// what that packet holds — so the manifest shown is what the model saw.
import { apiFetch } from '../../lib/config'
import type { HqContextManifest } from '../../store/chatStore'
import { useCommandCenterStore } from '../../store/commandCenterStore'
import { useCommsStore } from '../../store/commsStore'
import { selectedHqSections } from '../../store/hqContextStore'

export interface LocalGeneration {
  maxTokens: number
  thoughtBudget: number
  showReasoning?: boolean
  contextSize?: number
}

/** The model picker's Fast/Deep switch as built-in (node-llama-cpp) settings.
 *  Deep: the model reasons (capped at 768 tokens so the answer keeps >= 1280 —
 *  Qwen3's reasoning counts against maxTokens; measured 552 + 469 = cut off at
 *  1024) and the reasoning streams into ThinkingBlock. Fast: no reasoning —
 *  measured 2.4s vs 18s for the same board question. `contextSize` is the
 *  board turn's context (POST /hq/prompt's context_tokens), if any. */
export function localGeneration(mode: 'fast' | 'deep', contextSize?: number): LocalGeneration {
  const base: LocalGeneration = mode === 'deep'
    ? { maxTokens: 2048, thoughtBudget: 768, showReasoning: true }
    : { maxTokens: 1024, thoughtBudget: 0 }
  return contextSize ? { ...base, contextSize } : base
}

/** A skill match at or above this always wins (it is also the auto-run bar). */
const SKILL_WINS_CONFIDENCE = 0.65
/** Below this there is no skill match at all (useHQ's own threshold). */
const SKILL_MATCH_CONFIDENCE = 0.4

const QUESTION_LEAD_RE = /^(what|what's|whats|why|how|when|where|who|which|is|are|was|were|do|does|did|has|have|any|anything|tell me|show me|summari[sz]e|list|explain|give me)\b/i

export interface HqTurn {
  /** Set: show this instead of calling the model (an action request). */
  redirect: string | null
  /** Null: the packet could not be fetched — answer with the Conductor prompt. */
  systemPrompt: string | null
  prompt: string | null
  manifest: HqContextManifest | null
  /** Context size to request from the runtime (Ollama num_ctx / llama context). */
  contextTokens: number
  /** Operator mode: the functions to offer the model (none: read-only). */
  tools: HqToolSpec[]
  /** Their names — what the server kept of the enabled actions. */
  actions: string[]
}

/** Board open → the copilot answers, unless the message is a skill request:
 *  a confident match (>= 0.65), or a plain match (>= 0.4) that isn't phrased
 *  as a question. "What needs my attention?" stays with the copilot even
 *  when it loosely matches the status skill. With operator actions enabled
 *  (`operator`), a plain match is the operator's too: "pause the builder" is
 *  an action to propose, not a skill to explain. */
export function shouldUseHqCopilot(hasBoard: boolean, text: string, skillConfidence: number | null, operator = false): boolean {
  if (!hasBoard) return false
  const conf = skillConfidence ?? 0
  if (conf < SKILL_MATCH_CONFIDENCE) return true
  if (conf >= SKILL_WINS_CONFIDENCE) return false
  if (operator) return true
  const t = text.trim()
  return t.endsWith('?') || QUESTION_LEAD_RE.test(t)
}

/** The feature boards open in the Command Center, and its main board tab. */
export interface OpenBoards {
  mainFeature: string | null
  openFeatures: string[]
  /** The project's feature boards, when loaded. The open-topic fallback must
   *  name one: activeTopic can hold a goal run's slug, which is no board. */
  knownFeatures?: string[]
}

function commandCenterBoards(): OpenBoards {
  const s = useCommandCenterStore.getState()
  const openFeatures = s.sections.flatMap((sec) => (sec.scope === 'feature' ? [sec.featureId] : []))
  const knownFeatures = useCommsStore.getState().features.map((f) => f.id)
  return { mainFeature: s.mainFeature || null, openFeatures, knownFeatures }
}

/** The board HQ answers about: the board the user is LOOKING AT in the Command
 *  Center — the main board tab when its section is open, else any open feature
 *  board — then the open topic, then the last main board. Never the runner's
 *  topic: that can be a goal run's slug (goal-…-6303b11e), not a board, which
 *  left the packet empty while the user had a real board open. */
export function resolveHqBoard(
  activeTopic: string | null,
  projectPath: string | null,
  boards: OpenBoards = commandCenterBoards(),
): { board: string; projectRoot: string | null } | null {
  const { mainFeature, openFeatures, knownFeatures } = boards
  const known = (b: string | null): string | null =>
    b && (!knownFeatures?.length || knownFeatures.includes(b)) ? b : null
  const board = (mainFeature && openFeatures.includes(mainFeature) ? mainFeature : null)
    ?? openFeatures[0]
    ?? known(activeTopic)
    ?? mainFeature
  return board ? { board, projectRoot: projectPath } : null
}

function unavailableManifest(model: string, board: string): HqContextManifest {
  return { board, tokens_est: 0, budget: 0, sections: [], model, eligible_model: true, unavailable: true }
}

interface HqPromptResponse {
  redirect: string | null
  system_prompt: string | null
  prompt: string | null
  manifest: HqContextManifest | null
  context_tokens: number
  tools?: HqToolSpec[]
  actions?: string[]
}

/** Fetch the model turn for *text* on *board*, carrying the board sections the
 *  user ticked (*sections*, default: the saved choice) and the operator actions
 *  the composer ticked (*enabledActions*: none = the read-only copilot). Never
 *  throws: a server failure returns an "unavailable" turn (Conductor prompt +
 *  the amber note) with no tools. */
export async function fetchHqTurn(
  text: string,
  board: string,
  projectRoot: string | null,
  modelId: string,
  sections: string[] = selectedHqSections(),
  enabledActions: string[] = [],
): Promise<HqTurn> {
  try {
    const res = await apiFetch('/hq/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text, board, project_root: projectRoot ?? undefined, model: modelId, sections,
        ...(enabledActions.length ? { enabled_actions: enabledActions } : {}),
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json() as HqPromptResponse
    return {
      redirect: d.redirect,
      systemPrompt: d.system_prompt,
      prompt: d.prompt,
      manifest: d.manifest,
      contextTokens: d.context_tokens || 0,
      tools: d.tools ?? [],
      actions: d.actions ?? [],
    }
  } catch {
    return { redirect: null, systemPrompt: null, prompt: null, manifest: unavailableManifest(modelId, board), contextTokens: 0, tools: [], actions: [] }
  }
}
