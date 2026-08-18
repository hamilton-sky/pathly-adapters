// Engine preflight — does this CLI actually exist on this machine?
//
// Split from the spawn path because it answers a different question: the spawn path needs a
// launcher to RUN, this needs an availability report to RENDER (grey out a missing engine and
// show the command that installs it).

import { slog } from './log'
import {
  RESOLVABLE_ENGINES_LIST,
  ENGINE_INSTALL_HINTS,
  resolveEnginePath,
  isOnPath,
  adapterIdFromLauncher,
} from './shells'

// ── Engine preflight ─────────────────────────────────────────────────────────
// Nothing used to check that an engine was actually INSTALLED. ADAPTER_META is derived
// statically from adapters.yaml, so every engine always rendered as available and a
// missing binary surfaced only as a `pty.spawn FAILED` line in the main-process console
// — no UI signal, no remedy. This probes the real filesystem/PATH so the renderer can
// grey out what isn't there and show the command that installs it.

/** Mirrored in preload/index.ts and renderer types/global.d.ts — keep in sync. */
export interface EnginePreflight {
  engine: string
  /** CliAdapter id the UI keys off ('claude' | 'codex' | 'antigravity'). */
  adapter: string
  available: boolean
  /** Absolute launcher, the bare name if only PATH resolved it, else null. */
  resolvedPath: string | null
  /** Shell command that installs it — shown verbatim in the UI. */
  installHint: string
}


async function preflightEngine(engine: string): Promise<EnginePreflight> {
  const abs = resolveEnginePath(engine)
  // resolveEnginePath returns the bare name when no known location matched — fall back to
  // an actual PATH probe rather than reporting "missing" for an install we don't enumerate.
  const found = abs !== engine ? abs : (await isOnPath(engine)) ? engine : null
  return {
    engine,
    adapter: adapterIdFromLauncher(engine),
    available: found !== null,
    resolvedPath: found,
    installHint: ENGINE_INSTALL_HINTS[engine] ?? '',
  }
}

// Probing hits the filesystem + spawns `which`, so cache briefly — the selectors that
// consume this re-render often. `force` bypasses it after the user installs something.
let preflightCache: { at: number; data: EnginePreflight[] } | null = null
const PREFLIGHT_TTL_MS = 30000

export async function preflightEngines(force: boolean): Promise<EnginePreflight[]> {
  if (!force && preflightCache && Date.now() - preflightCache.at < PREFLIGHT_TTL_MS) {
    return preflightCache.data
  }
  const data = await Promise.all(RESOLVABLE_ENGINES_LIST.map(preflightEngine))
  preflightCache = { at: Date.now(), data }
  slog('preflight', data.map((d) => `${d.engine}=${d.available ? d.resolvedPath : 'MISSING'}`).join(' '))
  return data
}
