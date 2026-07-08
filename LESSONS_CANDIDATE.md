# Lessons Candidate

_Extracted from retrospectives. Review and promote to pathly/lessons/ when confirmed._

---

## From planner-hierarchy / G3 (2026-07-08)

### L1 — Board-native skill checklist: CLAUDE.md exception list

When implementing a board-native skill (any skill whose primary job is posting to `/comms/*`), verify that `src/pathly_data/CLAUDE.md`'s board-native exception list includes the new skill **before** marking the goal done. The violation was caught by the reviewer, not the builder — this should be a builder definition-of-done item.

### L2 — `message_id` is the only dependency currency

Dependencies in `depends_on` must always be stored as the returned `message_id` values from board POST responses, never slugs, titles, filenames, or labels. Post parent cards first, record each `message_id`, then wire into downstream `depends_on` fields. Out-of-order posting produces unresolvable dependency chains.

### L3 — Idempotency guard pattern for import skills

Skills that may be re-run (PRD re-import, re-decompose) must check for 2+ existing items of the same type before posting duplicates (query board for existing goals/features by scope). Critical in import skills where re-runs must not multiply the hierarchy.

### L4 — Skip-if-down fallback for networked board skills

Always provide a local-only fallback (scaffold files + plan file) when the comms server is unreachable. Never retry in a loop — report the block clearly in the completion report and continue locally.

### L5 — Composition registration is a gate, not an afterthought

Board-native skills require `no_defaults: true` + explicit fragment list (`code-query`, `comms-post`, `completion-report`) in `composition.yaml`. Write the composition entry alongside the skill body — treat it as part of the feature contract, not a follow-up step.
