// Static option lists for the single-agent form (extracted to keep AgentForm lean).

// Engines that can run a board agent (have a headless command on the backend).
export const ENGINES: { value: string; label: string }[] = [
  { value: 'claude', label: 'Claude' },
  { value: 'codex', label: 'Codex' },
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
