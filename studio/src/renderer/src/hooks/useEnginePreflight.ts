import { useCallback, useEffect, useState } from 'react'

/**
 * Live install-status for the CLI engines, probed in the main process.
 *
 * Why this exists: ADAPTER_META (from adapters.yaml) describes which engines Pathly
 * KNOWS ABOUT, never which are installed on this machine — so every selector listed all
 * of them as usable and a missing binary only showed up as a failed spawn. This hook is
 * the missing signal: it lets a selector grey out what isn't there and name the command
 * that installs it.
 *
 * Fail-soft: an IPC error resolves to an empty map, which every consumer reads as
 * "no engine is known to be missing" — i.e. the pre-existing behavior, never a
 * selector that wrongly disables everything.
 */
export interface EnginePreflightState {
  /** Keyed by CliAdapter id ('claude' | 'codex' | 'antigravity'). */
  byAdapter: Record<string, EnginePreflight>
  loading: boolean
  /** Re-probe, bypassing the main-process TTL cache — call after installing something. */
  refresh: () => Promise<void>
}

export function useEnginePreflight(): EnginePreflightState {
  const [byAdapter, setByAdapter] = useState<Record<string, EnginePreflight>>({})
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (force: boolean): Promise<void> => {
    try {
      const rows = await window.pathly.terminal.preflight(force)
      const next: Record<string, EnginePreflight> = {}
      for (const r of rows) next[r.adapter] = r
      setByAdapter(next)
    } catch {
      setByAdapter({}) // fail-soft — never disable a selector because the probe broke
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(false)
  }, [load])

  const refresh = useCallback(async (): Promise<void> => {
    setLoading(true)
    await load(true)
  }, [load])

  return { byAdapter, loading, refresh }
}

/** The greyed-out reason for an adapter, or undefined when it is usable / unknown. */
function unavailableReason(
  byAdapter: Record<string, EnginePreflight>,
  adapter: string,
): string | undefined {
  const row = byAdapter[adapter]
  if (!row || row.available) return undefined
  return row.installHint ? `Not installed — ${row.installHint}` : 'Not installed'
}
