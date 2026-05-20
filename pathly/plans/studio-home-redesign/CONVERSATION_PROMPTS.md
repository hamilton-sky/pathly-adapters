# studio-home-redesign — Conversation Guide

Split into 2 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Layout, Header Controls, Grid View (Phases 1–3)

**Stories delivered:** S1 (dark mode toggle), S2 (grid + view toggle), S3 (welcome subtitle)

**Prompt to paste:**
```
Read pathly/plans/studio-home-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-home-redesign Conversation 1 (Phases 1–3) from pathly/plans/studio-home-redesign/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Before editing anything, run `cd studio && npm run typecheck 2>&1 | head -20` and note any pre-existing errors as baseline.

**Before editing anything:** Glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/types/index.ts` — add `pinned?: boolean` to ProjectEntry
- `studio/src/renderer/src/components/HomeScreen.tsx` — dark mode toggle + view toggle in drag strip, welcome subtitle, grid layout

Scope:
- Phase 1: Add `pinned?: boolean` after `fsmState?` in the `ProjectEntry` interface in `types/index.ts`. No other type changes.
- Phase 2: In `HomeScreen.tsx`, import `{ Sun, Moon, LayoutGrid, List }` from `lucide-react`. Pull `theme` and `setTheme` from `useStore()`. Add `viewMode` state initialized from `localStorage.getItem('pathly-home-view') ?? 'grid'` with a setter that also persists to localStorage. Add right-aligned controls to the existing fixed drag strip div: dark mode toggle (sun/moon icon, switches theme) and grid/list view toggle (two icon buttons, active one gets `t.accent` color). Both controls must have `WebkitAppRegion: no-drag` and `pointerEvents: 'all'` so they're clickable. Each button: 28×28px, borderRadius 6px, hover backgroundColor t.bgSurface0.
- Phase 3: Add a subtitle `<p>` below the `<h1>`: text "Welcome back. Pick up where you left off.", 14px, t.textMuted, fontWeight 400, fadeIn animation. Reduce h1 marginBottom to 8px. Change content container maxWidth from 820px to 1100px. Apply grid layout when viewMode === 'grid': `display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px'`. Fall back to existing column layout when viewMode === 'list'. Move the "RECENT PROJECTS" label + "Show all/Hide done" button row to sit outside/above the grid container so it always spans full width.

Architectural rules:
- Do not change store shape — all new state uses useState or localStorage directly
- Do not change TopBar.tsx or any component other than HomeScreen.tsx and types/index.ts
- Do not modify the existing drag-strip background color or height

Do NOT touch Phases 4–7, card internals, pinning logic, or any component outside HomeScreen.tsx.

Verify: `cd studio && npm run typecheck`

After done, update pathly/plans/studio-home-redesign/PROGRESS.md phases 1–3 to DONE and Conv 1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Home screen shows dark/light toggle and grid/list toggle in the top-right of the drag strip; subtitle visible below title; projects render in a 3-column auto-fill grid; TypeScript compiles clean.

**Files touched:** `types/index.ts`, `HomeScreen.tsx`

---

## Conversation 2: Richer Cards, Pinning, Empty State (Phases 4–7)

**Stories delivered:** S4 (richer cards), S5 (pin/star), S6 (empty state)

**Prompt to paste:**
```
Read pathly/plans/studio-home-redesign/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Also read pathly/plans/studio-home-redesign/DESIGN.md for the full visual spec before implementing.

Implement studio-home-redesign Conversation 2 (Phases 4–7) from pathly/plans/studio-home-redesign/IMPLEMENTATION_PLAN.md.

Conversation 1 is complete — `pinned?: boolean` is on ProjectEntry, dark mode + view toggle are in the drag strip, grid layout is applied.

**Before editing anything:** Glob/read the live repo to confirm HomeScreen.tsx exists and was updated in Conv 1.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/HomeScreen.tsx` — card redesign, pin/star, empty state

Scope:
- Phase 4: Add `hoveredCard` state. Add a `getCardAccent(plans, t)` helper inside the component (not exported): returns `t.red` if any plan is BLOCKED, `t.accent` if any plan is non-DONE non-IDLE, else `t.bgSurface1`. Apply `borderTop: '3px solid <accent>'` to each card outer div. On card hover: `border: '1px solid ${t.accent}50'`, `boxShadow: '0 0 0 1px ${t.accent}20'`. Wire card `onMouseEnter`/`onMouseLeave` to `hoveredCard`.
- Phase 5: Add a footer row to each card below the topic list: `display: flex, justifyContent: space-between, padding: '8px 16px', borderTop: '1px solid ${t.bgSurface0}'`. Left side: `"${allPlans.length} topic${allPlans.length !== 1 ? 's' : ''} · ${timeAgo(project.lastOpened)}"` at 11px, t.textMuted. Right side: move the existing "Open" button here from the header row. In the card header, keep only project name, path, pin button (Phase 6), and remove button. Remove button: set `opacity: hoveredCard === project.path ? 1 : 0` with `transition: opacity 150ms`.
- Phase 6: Import `{ Star }` from lucide-react. Add a pin button in the card header between the project name/path block and the remove button. Star is `fill='#EAB308'` and `color='#EAB308'` when pinned, else `fill='none'` and `color={t.textMuted}`. Show the star always when `project.pinned === true`; show only on `hoveredCard` when not pinned. `onClick` calls `updateProject(project.path, { pinned: !project.pinned })` with `e.stopPropagation()`. Split `sorted` into `pinnedProjects` and `unpinnedProjects`. Render "PINNED" section + divider + "RECENT PROJECTS" section only when `pinnedProjects.length > 0`. When no pinned projects, render `unpinnedProjects` with "RECENT PROJECTS" label as before.
- Phase 7: Import `{ FolderOpen }` from lucide-react. Replace the existing bare "No projects yet" text div with a centered empty state: FolderOpen icon (32px, t.textMuted), "No projects yet" title (14px, t.textPrimary, weight 500), "Open a folder to get started" subtitle (12px, t.textMuted). Keep the existing "Open project folder" CTA button below this.

Architectural rules:
- Do not change store shape or add new actions — `updateProject` with `Partial<ProjectEntry>` is sufficient for pinning
- The `getCardAccent` helper must live inside the HomeScreen component file, not exported
- Do not touch TopBar.tsx or any other component

Do NOT re-implement the view toggle, dark mode toggle, grid layout, or subtitle from Conversation 1.

Verify: `cd studio && npm run typecheck`

After done, update pathly/plans/studio-home-redesign/PROGRESS.md phases 4–7 to DONE and Conv 2 to DONE, and update Status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Cards have color-coded top borders, a footer row with topic count and Open button, pin/star toggle that floats projects to a Pinned section; empty state shows FolderOpen icon + labels. TypeScript compiles clean.

**Files touched:** `HomeScreen.tsx`
