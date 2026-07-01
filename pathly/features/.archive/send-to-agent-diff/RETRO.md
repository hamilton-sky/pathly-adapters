# Retro — send-to-agent-diff

**Date:** 2026-06-10
**Feature:** send-to-agent-diff
**Rigor:** standard
**Result:** DONE

---

## What went well

- **Planning accuracy**: Planner's 3-conversation breakdown (wiring, component build, mount+handlers) matched execution exactly — no scope creep or stage merging.
- **Review-first bug catch**: Reviewer caught critical path normalization and subscription leak issues in Conv 1 before proceeding; prevented downstream rework.
- **Component modularity**: DraftDiffViewer's 11-file structure (hook + 5 components + 5 CSS) stayed clean through two review cycles; CSS variant pattern enforcement caught visual inconsistencies early.
- **Typecheck discipline**: Both builder conversations passed typecheck zero-error; caught IPC triangle wiring issues before tester.
- **Tester's fix precision**: Found 5 concrete failures (border rendering, zero-diff suppression, reconstruct logic, draft-disappear timing, copy wording) with clear root causes — all fixed in one cycle.

## What was hard

- **IPC state coordination**: CommentsPanel → buildSendPrompt → .draft → DraftDiffViewer required careful draftPath state threading; took reviewer scrutiny to avoid race conditions.
- **Reconstruct() logic bug**: Section rebuild from diff hunks had rejection-handling bug that silently produced empty sections — only caught in user-facing acceptance test, not in builder review.
- **Timing-dependent behavior**: Draft-disappear watch needed 3s polling fallback; suggests event-driven model could be cleaner for future watch patterns.
- **CSS variant strictness**: role=dialog / role=tab ARIA violations required reviewer + builder iteration; pattern wasn't caught by initial linter.

## Improvements for next time

- **Add reconstruct-logic unit tests**: Diff reconstruction touched real state shape changes (rejections, section erasure) — standalone unit tests earlier would have caught the bug in Conv 2, not in the test stage.
- **IPC wiring template**: Codify CommentsPanel → draftPath → mounted-component pattern as a reusable checklist (observer setup, cleanup, race condition guards) for future draft/modal flows.
- **Timing budget upfront**: When design calls for "watch disappears on tab close," explicitly spec event vs. polling in DESIGN phase — avoid tester discovering timing surprises.
- **ARIA + CSS linter rule strengthening**: role= attributes on interactive components should be pre-committed linting; don't wait for reviewer to flag.

## Key metrics

| Stage | Conversations | Fix cycles |
|---|---|---|
| BUILD | 3 | 3 review fixes |
| REVIEW | 3 | — |
| TEST | 1 | 1 (5 criteria fixed) |
