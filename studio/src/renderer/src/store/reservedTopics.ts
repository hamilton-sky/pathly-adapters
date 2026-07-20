// Names a feature slug may NOT use: loadFeatures filters them out of feature discovery and
// the create form blocks them up front. Two origins:
//   1. Structural containers under pathly/ — mirrors _RESERVED_TOPICS in
//      src/pathly_orchestrator/storage_paths.py (a feature named "goals"/"plans"/… would
//      collide with a structural dir, and the FSM's _safe_topic() rejects it as a run topic).
//   2. Reserved board-SCOPE names ('project', 'global') — a feature slug equal to either
//      mints a board section whose id collides with the literal project/global board section
//      (two sections, one React key → the board flickers). A stray pathly/features/global/
//      (e.g. an evaluate run that leaked the board scope into an unsubstituted <feature>) must
//      never surface as a feature card.
// NOTE the intentional divergence from the Python set: it lists 'project' but NOT 'global'.
// 'global' is a valid storage SCOPE there — a global board run resolves its storage through
// _safe_topic('global') (fsm_ops.py), so reserving it Python-side would raise and crash the
// run. 'project' is safe there only because fsm_ops early-returns pathly/project/ before the
// _safe_topic call; 'global' has no such early return. So 'global' is UI-reserved only.
export const RESERVED_TOPICS: ReadonlySet<string> = new Set([
  'features', 'project', 'global', 'plans', 'debugs', 'explorations', 'fixes',
  'goals', 'lessons', 'board-artifacts', 'pipeline-walkthrough', '.archive',
])
