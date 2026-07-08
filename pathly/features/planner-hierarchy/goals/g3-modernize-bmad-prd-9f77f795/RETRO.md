# Retrospective — G3: Modernize BMAD PRD Import

_Feature: planner-hierarchy | Goal: g3-modernize-bmad-prd-9f77f795 | Date: 2026-07-08_

---

## What went well

1. **Board-native pattern adoption.** `prd-import` successfully moved from a legacy plan-file emitter to a board-native terminal emitter with full feature+goal hierarchy, idempotency guards, `message_id`-based `depends_on`, and a skip-if-down fallback. The migration followed the same pattern as `feature-decompose` and `project-decompose`, keeping the three decomposer skills consistent.

2. **Comprehensive test coverage.** 8 contract tests pass, covering composition registration, board POST contracts, legacy removal, idempotency guards, `message_id` dependency resolution, dependency levels, SPEC scaffolding, BMAD fixtures, and generic PRD handling. The test contracts are explicit and enforceable.

3. **Clean BMAD/generic PRD separation.** Classification logic is clear; the epic→feature / story→goal hierarchy mapping is explicit; Step 3 handles both patterns without coupling.

4. **Resilience by design.** Skip-if-down fallback (Steps 7–8) ensures local scaffolding + plan file even when the comms server is unreachable — no silent failures, no blocking loops.

5. **Composition registration discipline.** `no_defaults: true` + explicit fragment list (`code-query`, `comms-post`, `completion-report`) is now a firm pattern for board-native planning skills; `composition.yaml` is the contract, not ad-hoc curl calls in the skill body.

---

## What could be improved

1. **Doc-sync as an implementation gate, not a review catch.** The CLAUDE.md violation (prd-import not listed in the board-native exception list) was caught during review, not during implementation. Doc-sync should be a checklist item in the builder's definition-of-done, not a fallback for the reviewer to find.

2. **Post-upstream-first pattern visibility.** The rule that parent cards must be posted before child cards (to have a real `message_id` for `depends_on`) is critical and non-obvious. It should be highlighted more prominently — either in the skill body's step ordering or in a shared fragment comment.

3. **Non-blocking deferred work bundling.** The MIME-string duplicate (`WORKSPACE_TREE_DRAG_MIME` / `DRAG_MIME` in Studio sharing the same string literal in two unexported locals) was noted and deferred. Small studio nits like this could be bundled into a single clean-up goal rather than leaving them as floating deferred items.

---

## Lessons to promote

1. **Board-native skill checklist — CLAUDE.md exception list.** When implementing a board-native skill (any skill that posts to `/comms/*` as its primary job), verify that `src/pathly_data/CLAUDE.md`'s board-native exception list includes the new skill before marking the goal done. Add this to the skill implementation template's definition-of-done section.

2. **`message_id` is the only dependency currency.** Dependencies must always be stored as the returned `message_id` values from the board POST response, never slugs, titles, filenames, or labels. Post cards upstream first, record each response's `message_id`, then wire them into downstream card `depends_on` fields. Violating this order produces broken or unresolvable dependency chains.

3. **Idempotency guard pattern for import skills.** When a skill may be re-run (PRD re-import, re-decompose), check for 2+ existing items of a type before posting duplicates (e.g., query goals by feature, query features by project). This is especially critical in import skills where re-running must not multiply the hierarchy.

4. **Skip-if-down fallback for networked board skills.** Always provide a local-only fallback (scaffold files + plan file) when the comms server is unreachable. Never retry in a loop; report the block clearly in the completion report and continue locally. This keeps the skill usable in offline or server-down scenarios.

5. **Composition registration is a gate, not an afterthought.** Board-native skills require `no_defaults: true` + explicit fragment list in `composition.yaml`. Treat the composition entry as part of the feature contract — write it alongside the skill body, not as a follow-up step.
