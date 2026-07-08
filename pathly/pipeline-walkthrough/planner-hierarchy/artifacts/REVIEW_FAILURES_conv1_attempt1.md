# Review Failures — G3 Modernize PRD Import (conv 1)

Reviewed files: `src/pathly_data/core/skills/planning/prd-import.md`,
`src/pathly_data/core/skills/composition.yaml`, `src/pathly_data/CLAUDE.md`,
`tests/test_prd_import_new.py`, `tests/conftest.py`, `pyproject.toml`,
`studio/src/renderer/src/components/CommandCenter/CommsPanel/ArtifactsView/ArtifactsView.tsx`,
`studio/src/renderer/src/components/sidebar/workspace-tree/useWorkspaceTree.ts`.

---

## MAJOR

### M1 — `src/pathly_data/CLAUDE.md` — doc-sync: board-native exception list missing `planning/prd-import`

**Rule:** CLAUDE.md doc-sync rule; agnosticism principle in `src/pathly_data/CLAUDE.md`.

**Detail:** The agnosticism principle section lists the deliberate board-native exceptions as:
`development/drain-dag`, `planning/evaluate`, `planning/consolidate`,
`planning/feature-decompose`, `planning/project-decompose`. `planning/prd-import` is not
in this list. The skill body contains embedded `/comms/*` curl calls in Steps 2, 5a, 5c,
5d, 6a, and 6b — the same pattern as `planning/project-decompose`, which IS listed. The
CLAUDE.md was modified in this diff (it now lists `planning/prd-import` in the
`no_defaults` list and "Skills currently in manifest" list) but the board-native exception
paragraph was not updated. A future agent reading CLAUDE.md will conclude `prd-import`
violates the agnosticism rule and attempt to strip its board calls.

**Fix required:** Add `planning/prd-import` to the board-native exception list in the
agnosticism principle paragraph alongside `planning/project-decompose`.

---

## MINOR

### N1 — `tests/test_prd_import_new.py` — SPEC requires 9 test cases; file has 8 functions

**Rule:** SPEC.md §Tests Expected for G3 (lines 297–319).

**Detail:** The SPEC lists 9 required cases. Cases 8 and 9 ("A BMAD PRD fixture maps epics
to features and stories to goals" and "A generic non-BMAD PRD fixture still maps to 2-5
project-board feature cards") are merged into `test_prd_import_bmad_and_generic_mapping_contracts`.
The SPEC permits this when "the import remains prompt-only" (`assert the contract text
deterministically`) — so this is within spec. Flagged as MINOR because the SPEC's own
guidance allows it but the count mismatch may confuse future maintainers.

**Fix required:** None required to advance; optionally split into two functions for clarity.

---

## Warnings (non-blocking)

### W1 — `ArtifactsView.tsx:18` / `useWorkspaceTree.ts:10` — pre-existing MIME constant duplication

**Rule:** CLAUDE.md §5 shared helpers rule.

`WORKSPACE_TREE_DRAG_MIME = 'application/x-pathly-ws-move'` (ArtifactsView.tsx line 18)
duplicates `DRAG_MIME = 'application/x-pathly-ws-move'` (useWorkspaceTree.ts line 10).
Both constants were present before this diff (confirmed by pre-review scout). The diff did
not introduce the duplication. Noted so the string stays in sync if either file is edited
in future.

---

## Pass

- `planning/prd-import.md` — all SPEC contracts present; argument contract correct; idempotency
  guards at both feature and goal levels; `depends_on` stored by `message_id` at all levels;
  SPEC.md scaffolding step present; BMAD/generic branch correct; `completion-report` is the
  final step; no legacy artifacts (`CONVERSATION_PROMPTS.md`, `USER_STORIES.md`,
  `IMPLEMENTATION_PLAN.md` absent).
- `composition.yaml` — `planning/prd-import` entry has `no_defaults: true` and fragments
  `[code-query, comms-post, completion-report]`; matches SPEC exactly.
- `tests/test_prd_import_new.py` — `from pathly_orchestrator import compose` is valid
  (`src/pathly_orchestrator/compose.py` is a confirmed shim); all 8 test assertions match
  skill body content; `pytestmark = pytest.mark.no_pathly_autouse` correctly skips DB fixtures.
- `tests/conftest.py` — `no_pathly_autouse` marker skip applied correctly in all three
  autouse fixtures (`_no_async_embed`, `_isolate_db`, `_reset_rate_limiter`).
- `pyproject.toml` — `no_pathly_autouse` marker registered in `[tool.pytest.ini_options]`;
  no layer violations.
- `studio/ArtifactsView.tsx` — no inline styles; 118 lines (under limits); folder structure
  correct; dual-MIME drop handler logic sound.
- `studio/useWorkspaceTree.ts` — 262 lines (under 400-line Python limit; hook file, not
  component); no inline styles; no layer violations.
- `src/pathly_data/CLAUDE.md` — `planning/prd-import` correctly appears in the `no_defaults`
  twelve-skill list and "Skills currently in manifest" list.
