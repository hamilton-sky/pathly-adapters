// Direct children of pathly/ that are structural containers, not features. Mirrors
// _RESERVED_TOPICS in src/pathly_orchestrator/storage_paths.py. A feature slug may not
// equal one of these: loadFeatures filters them out of feature discovery, and the FSM's
// _safe_topic() rejects them as run topics — so a feature named e.g. "goals" could be
// created but never run. The create form validates against this to block it up front.
export const RESERVED_TOPICS: ReadonlySet<string> = new Set([
  'features', 'project', 'plans', 'debugs', 'explorations', 'fixes',
  'goals', 'lessons', 'board-artifacts', 'pipeline-walkthrough', '.archive',
])
