import type { EngineAdapter } from '../Monitor/EngineBoard'

// Provider/adapter string (run_history.adapter — a model id, a CLI slug, OR a flow name like
// 'team') → the badge's display adapter, or null when it is a flow name so NO engine badge shows
// (a flow run isn't "a Claude"). Copied from Monitor/hooks/useRecentEngines, where it is
// module-private, and made null-returning per HANDOFF §E's reuse map.
export function adapterFromProvider(p: string | null): EngineAdapter | null {
  const k = (p || '').toLowerCase()
  if (!k) return null
  if (k.startsWith('gpt') || k.startsWith('o1') || k.startsWith('o3') || k.startsWith('codex')) return 'Codex'
  if (k.startsWith('gemini') || k === 'agy' || k.startsWith('antigravity')) return 'Gemini'
  if (k === 'claude' || k.startsWith('claude')) return 'Claude'
  return null // flow names (team, consultation, …) carry no engine badge
}
