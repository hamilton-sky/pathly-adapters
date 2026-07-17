// Static option lists for the single-agent form (extracted to keep AgentForm lean).

// The CLI adapters Pathly can spawn. claude/codex have the fullest headless support;
// copilot + antigravity (Gemini) are offered too (antigravity has no stdin path, so large
// composed prompts can overflow on Windows — fine for small board tasks).
export const ENGINES: { value: string; label: string }[] = [
  { value: 'claude', label: 'Claude' },
  { value: 'codex', label: 'Codex' },
  { value: 'copilot', label: 'Copilot' },
  { value: 'antigravity', label: 'Gemini' },
]

// How chatty a headless run is on the board. Headless-only: in interactive mode
// the human watches the live terminal, so board narration is redundant.
export const PROGRESS_LEVELS: { value: string; label: string }[] = [
  { value: 'quiet', label: 'Quiet — start + result only' },
  { value: 'normal', label: 'Normal — key steps' },
  { value: 'verbose', label: 'Verbose — every step' },
]

// Fixed starter system-prompt presets (user-editable presets are a follow-up).
export const SYSTEM_PROMPTS: { name: string; prompt: string }[] = [
  { name: 'Summarizer', prompt: 'Summarize the request concisely. Be terse and factual.' },
  { name: 'Code reviewer', prompt: 'Review the referenced code for bugs, security issues, and edge cases. Report findings only — do not edit files.' },
  { name: 'Researcher', prompt: 'Research the topic, cite sources, and report what you found and what is uncertain.' },
  { name: 'Explainer', prompt: 'Explain clearly and simply, with a short concrete example.' },
  { name: 'Planner', prompt: 'Break the request into a short ordered list of concrete steps.' },
]

// Evaluation lenses for the Evaluate button — these shape HOW the board evaluator
// reads the board, not which worker runs (agents/skills live in "Run on this board").
// The default ('' / "Propose tasks") runs the plain evaluator; every other lens is
// passed as the evaluator's system prompt. `name: ''` is the no-lens default row.
export interface EvalLens { name: string; label: string; hint: string; prompt: string; skillRef?: string }
export const EVAL_LENSES: EvalLens[] = [
  { name: '', label: 'Propose tasks', hint: 'default · analyze board → task list', prompt: '', skillRef: 'planning/evaluate' },
  { name: 'risks', label: 'Find risks', hint: 'surface bugs, blockers, regressions', prompt: 'Evaluate this board with a risk lens. Surface the bugs, blockers, regressions, and unsafe assumptions hiding in the work, and propose concrete tasks to de-risk them. Prioritize the highest-impact risks first.' },
  { name: 'gaps', label: 'Find gaps', hint: 'what is missing or unspecified', prompt: 'Evaluate this board for gaps. Identify what is missing, under-specified, or contradictory across the goals, decisions, and artifacts, and propose concrete tasks to close each gap.' },
  { name: 'summary', label: 'Summarize state', hint: 'where things stand right now', prompt: 'Evaluate this board and summarize the current state: what is decided, what is in flight, what is blocked, and what is done. Be terse and factual. Only propose tasks for clear, unambiguous next steps.' },
  { name: 'prioritize', label: 'Prioritize', hint: 'order the open work by impact', prompt: 'Evaluate this board and prioritize the open work. Order the outstanding tasks and goals by impact and dependency, call out what should happen next and why, and propose any missing tasks needed to unblock the top items.' },
]
