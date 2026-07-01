# PO Notes — differ-sections-fature-what-style-what-actions-w-2c50679e

_Last updated: 2026-07-01_

## Who Is This For

The human supervisor (developer / tech lead) using the Pathly **Command Center** to oversee
multi-agent runs. They open an artifact card on the board and need to understand:
(1) exactly what the agent changed at hunk level, and
(2) which callers / execution flows each hunk touches before they accept it.

This is not for agents — it is the human review surface on top of the same code-knowledge
graph that agents already query.

## Definition of Success

1. **Diff sections are clearly structured**: hunks are visually separated (unified or split view);
   each hunk can be expanded/collapsed independently.
2. **Style is consistent with Studio/Command Center** UI conventions — no bespoke widget
   library; reuses existing `CodeDiffView` / `DraftDiffViewer` patterns with the new `ImpactPanel`
   styled per Studio rules (own folder, CSS module).
3. **Per-hunk actions are explicit**: for surface (a) — read-only; the only action is "view
   impact" which opens the `ImpactPanel` blade for that hunk's changed symbol.  For surface (b)
   — accept / reject per hunk.  Surface (c) — no per-hunk actions, comparison only.
4. **Impact badge is surfaced at hunk level**: `⚠ N callers` badge appears on any hunk that
   touches an indexed symbol; clicking opens the ImpactPanel blade.
5. **Graceful degradation**: when the code graph (codebase-memory-mcp) is off or the file is
   non-code (markdown, JSON), sections still render as plain text diff with no badge / panel.

The single most important outcome: a supervisor can look at a hunk, see the impact badge, and
decide "accepting this touches these 3 callers — do I want that?" — without leaving the board.

## Out of Scope

- Full draft-triage (hunk-level accept/reject write-back) — this is **surface (b)**, second in
  rollout; do not build the apply path in this scope.
- Two-artifact compare (**surface (c)**) — third in rollout.
- Any new code-analysis engine — everything routes through the existing `code/` blueprint and
  `codebase-memory-mcp`; no second backend.
- Per-hunk commenting or annotation — future feature.
- Diff sections for non-code artifacts (plans, markdown) — text diff only, no ImpactPanel,
  no hunk actions beyond expand/collapse.

## Constraints

- **Depends on code-intel-foundation branch being merged**: `detect_changes` must be accessible
  via `POST /code/query { op: "impact" }` before the ImpactPanel can render data.
- **Graceful degradation is mandatory**: graph off → Impact panel simply absent; no error state
  shown to the user.
- **Studio rules apply**: `ImpactPanel/` gets its own folder + CSS module; file size ≤ 400 lines;
  single responsibility per file.
- **Reuse-first**: the diff view must build on `DraftDiffViewer` / `CodeDiffView`; no new diff
  parsing library.
- **Baseline for surface (a)**: artifact file vs last **committed git HEAD** of that path.
  Revisit if runs span multiple commits — default to committed HEAD for now.

## Open Questions

1. **`detect_changes` contract**: does it read the working-tree diff itself, or accept a
   diff/paths argument? Verify the tool contract before wiring the backend `op:"impact"` path.
   _Working assumption: it accepts `{"repo_path": <root>, "paths": [<file>]}` and diffs vs HEAD
   internally — confirm against codebase-memory-mcp docs._

2. **Hunk-level impact granularity**: does `detect_changes` return per-symbol or per-file results?
   If per-file, badge appears at the file level not per hunk; per-symbol is preferred for the
   hunk badge UX.
   _Working assumption: per-symbol (the APPROACH.md shows `build_block changed → 3 callers`
   at symbol level); if per-file only, fall back to file-level badge._

3. **Expand/collapse state**: should the differ remember which hunks are expanded across a session,
   or reset on each "See changes" open?
   _Working assumption: reset on each open — stateless is simpler and the context is ephemeral._
