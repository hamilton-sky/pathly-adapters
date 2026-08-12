// Rough PRE-RUN estimate of what a prompt will cost to SEND — the input side only.
//
// Two honest limits, both surfaced in the UI copy/tooltip:
//   1. Tokens are char-estimated (~4 chars/token), not tokenizer-exact — hence the "≈".
//   2. Cost is INPUT-only. Output tokens (usually the larger share of a run's cost) cannot be
//      known before the run, so this is a floor on prompt cost, not a run-cost prediction.
//
// Rates mirror db/pricing.py PRICING + the agent-role→model table in the root CLAUDE.md.
// The engine picks the provider FAMILY (codex → gpt-5, agy → gemini); within claude the role
// picks the model tier (architect/po → opus, quick/scout/orchestrator → haiku, else sonnet).

const OPUS_IN = 5 // claude-opus-4.5+ input $/MTok
const SONNET_IN = 3 // claude-sonnet input $/MTok — the pipeline default
const HAIKU_IN = 1 // claude-haiku input $/MTok
const CODEX_IN = 1.25 // gpt-5 / gpt-5-codex input $/MTok
const GEMINI_IN = 1.25 // gemini-2.5-pro input $/MTok (agy / antigravity)

// Only the claude roles that DIVERGE from the sonnet default are listed; everything else → sonnet.
const ROLE_INPUT_RATE: Record<string, number> = {
  architect: OPUS_IN,
  po: OPUS_IN,
  quick: HAIKU_IN,
  scout: HAIKU_IN,
  orchestrator: HAIKU_IN,
}

/** Pricing context: the engine sets the provider family; role tiers the model within claude. */
export interface PriceCtx {
  /** CLI engine the prompt is dispatched to — 'claude' (default) | 'codex' | 'agy' | … */
  engine?: string
  /** Pipeline role — only consulted for the claude family. */
  role?: string
}

/** ~4 chars/token heuristic. Returns 0 for empty/undefined. */
export function estimateTokens(text: string | undefined | null): number {
  return Math.ceil((text?.length ?? 0) / 4)
}

/** Input $/MTok for an (engine, role) context, defaulting to the claude sonnet rate. */
function inputRate(ctx?: PriceCtx): number {
  const engine = (ctx?.engine ?? '').toLowerCase()
  if (engine === 'codex') return CODEX_IN
  if (engine === 'agy' || engine === 'antigravity' || engine === 'gemini') return GEMINI_IN
  // claude family (or unspecified engine) → per-role model tier
  return ROLE_INPUT_RATE[(ctx?.role ?? '').toLowerCase()] ?? SONNET_IN
}

/** Estimated INPUT cost (USD) of sending `text` under `ctx`. Output not included. */
export function estimateInputCost(text: string | undefined | null, ctx?: PriceCtx): number {
  return (estimateTokens(text) / 1_000_000) * inputRate(ctx)
}

/** Compact token count: `820`, `4.2k`, `42k`. */
export function formatTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 10_000) return `${(n / 1000).toFixed(1)}k`
  return `${Math.round(n / 1000)}k`
}

/** Compact USD: `<$0.01`, `$0.04`, `$1.25`. */
export function formatUsd(n: number): string {
  if (n <= 0) return '$0.00'
  if (n < 0.01) return '<$0.01'
  return `$${n.toFixed(2)}`
}
