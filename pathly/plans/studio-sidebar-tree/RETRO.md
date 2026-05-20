# Retrospective — studio-sidebar-tree

_Date: 2026-05-20_

## What went well

- **Tight scope decomposition.** Splitting the sidebar into 5 discrete conversations (system lock, user lock, context menu, create buttons, drag-and-drop) kept each builder conversation focused and reviewable. No conversation had to undo another's work.
- **Scout-first CSS audit saved a build cycle.** The CSS variable mismatch (`--surface`/`--border` in DESIGN.md vs `--bg-surface1`/`--bg-surface0` in the actual codebase) was caught by scout before the builder used wrong variables. Without that check the builder would have shipped visually broken styles and the reviewer would have filed failures.
- **React portal pattern for context menu solved z-index cleanly.** Using `createPortal(menu, document.body)` with a drag handle removed all stacking-context fights with the sidebar tree. The pattern is reusable.
- **HTML5 native drag-and-drop was sufficient.** No external DnD library was needed for the file reorg feature; native drag events with cross-section guard and protected-file checks covered the full acceptance criteria.

## What was hard

- **FSM STATE.json needed manual intervention twice.** After Conv 3 review and Conv 4 review the orchestrator's own STATE_TRANSITION write overwrote manual PASS+advance events, putting the FSM in an unexpected state. Required direct file edits to restore correct state before the next conversation could proceed.
- **window.pathly.fs API gaps required workarounds.** The IPC bridge exposes no `mkdir` — folder creation had to be inferred by writing a `.gitkeep` sentinel file. Discovered mid-build, not during planning.
- **TemplateSubdir has no path field.** Paths for subdirectories had to be derived at render time as `${projectPath}/${section.dir}/${subdir.name}` rather than reading a canonical field. This pattern needed to be documented explicitly or it would have been re-discovered in every conversation touching subdirs.
- **localStorage key collision risk.** The `pathly:userLockedFolders` key was chosen ad-hoc. No central registry of localStorage keys exists; future features could silently overwrite it.

## Lessons extracted

1. **Scout must audit API surface (window.pathly.fs) before build conversations that need file system ops.** Missing methods (mkdir, rename, etc.) require workarounds that, if discovered mid-build, can derail scope.
2. **Derived-path patterns must be documented in ARCHITECTURE_PROPOSAL** when no canonical `path` field exists on a model. Otherwise every conversation that touches that model re-derives the pattern independently and risks inconsistency.
3. **FSM state files should be written atomically by the orchestrator, not appended piecemeal.** When an orchestrator transition write races with manual event appends, the manual entries are silently overwritten. The orchestrator should read the current EVENTS.jsonl before writing its transition.
4. **Maintain a localStorage key registry** (a single constant file or ARCHITECTURE doc section) so keys don't collide across features.
