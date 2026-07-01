# studio-home-redesign — Implementation Plan

_Rigor: lite | 2 conversations_

---

## Pre-flight (before Conversation 1)

Run the TypeScript compiler check and note any pre-existing errors as baseline:
```
cd studio && npm run typecheck 2>&1 | head -30
```
Record failures as known baseline — do not attribute them to this feature.

---

## Conversation 1 — Layout, Header Controls, Grid View   ← Conversation: 1

**Stories:** S1 (dark mode toggle), S2 (grid + view toggle), S3 (welcome subtitle)

### Phase 1 — Extend ProjectEntry type

**File:** `studio/src/renderer/src/types/index.ts`
**Done when:** `ProjectEntry` has `pinned?: boolean` field and TypeScript compiles without new errors.

Add `pinned?: boolean` after `fsmState?` in the `ProjectEntry` interface. No other type changes needed — `updateProject` already accepts `Partial<ProjectEntry>`.

### Phase 2 — Dark mode toggle and view toggle in drag strip

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** Home page drag strip shows sun/moon icon (right-aligned, no-drag zone) and grid/list toggle icons; clicking each works as expected.

- Import `{ Sun, Moon, LayoutGrid, List }` from `lucide-react` (already a dependency)
- Pull `theme` and `setTheme` from `useStore()` (already available via merged store)
- Add local state: `const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => (localStorage.getItem('pathly-home-view') as 'grid' | 'list') ?? 'grid')`
- Wrap `setViewMode` to also persist: `(m) => { setViewMode(m); localStorage.setItem('pathly-home-view', m) }`
- In the fixed drag strip `div`, add a right-side controls area with `pointer-events: all` and `WebkitAppRegion: no-drag`:
  - Dark mode button: `onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}` — render `<Sun size={14} />` when dark, `<Moon size={14} />` when light
  - View toggle: two buttons — `<LayoutGrid size={14} />` (active when `viewMode === 'grid'`) and `<List size={14} />` (active when `viewMode === 'list'`)
  - Active icon: `color: t.accent`; inactive: `color: t.textMuted`
  - Each button: `width: 28px`, `height: 28px`, `borderRadius: 6px`, hover `backgroundColor: t.bgSurface0`, `transition: all 150ms`

### Phase 3 — Welcome subtitle and wider container

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** Subtitle "Welcome back. Pick up where you left off." appears below the h1; content area is 1100px wide; grid layout is applied when `viewMode === 'grid'`.

- Add a `<p>` subtitle below the `<h1>`: 14px, `t.textMuted`, weight 400, `fadeIn 400ms ease-out 100ms both`, margin-bottom `8px`
- Change `marginBottom` on h1 from `36px` to `8px` (subtitle takes over spacing)
- Add `marginBottom: '32px'` to the subtitle (total header-to-content gap)
- Change `maxWidth` of content div from `'820px'` to `'1100px'`
- Change content div's `display` from `flexDirection: 'column'` to a conditional grid:
  - When `viewMode === 'grid'`: `display: 'grid'`, `gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))'`, `gap: '14px'`
  - When `viewMode === 'list'`: `display: 'flex'`, `flexDirection: 'column'`, `gap: '12px'`
- Move the "Recent Projects" label + "Show all/Hide done" button outside the grid div (above it, same as today) so they span full width

---

## Conversation 2 — Richer Cards, Pinning, Empty State   ← Conversation: 2

**Stories:** S4 (richer cards), S5 (pin/star), S6 (empty state)

### Phase 4 — Top accent border and hover glow on cards

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** Each project card has a 3px top border whose color reflects the project's activity state; hovering a card shows a subtle accent border glow.

Add `hoveredCard` state: `const [hoveredCard, setHoveredCard] = useState<string | null>(null)`.

Compute accent color per project:
```tsx
function getCardAccent(plans: PlanRow[], t: Theme): string {
  const blocked = plans.some((p) => p.state.toUpperCase() === 'BLOCKED')
  if (blocked) return t.red
  const active = plans.some((p) => p.state && p.state.toUpperCase() !== 'DONE' && p.state.toUpperCase() !== 'IDLE' && p.state !== '')
  if (active) return t.accent
  return t.bgSurface1
}
```

Apply to the card outer div:
- `borderTop: `3px solid ${getCardAccent(allPlans, t)}``
- On hover (`isCardHovered`): `border: `1px solid ${t.accent}50``, `boxShadow: `0 0 0 1px ${t.accent}20``
- On hover-leave: restore original border

### Phase 5 — Footer row: topic count, timestamp, Open button

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** Each card has a footer row showing "N topics · X hr ago" on the left and "→ Open" on the right; the existing per-plan topic list is preserved above it.

Rearrange card internals:
- Header row (existing): project name + path
- Topic list (existing): plan rows with badges — keep
- **New footer row**: `display: flex`, `justifyContent: space-between`, `alignItems: center`, `padding: '8px 16px'`, `borderTop: `1px solid ${t.bgSurface0}``
  - Left: `"${allPlans.length} topic${allPlans.length !== 1 ? 's' : ''}"` + ` · ` + `timeAgo(project.lastOpened)` — 11px, `t.textMuted`
  - Right: move existing Open button here (remove it from the header row)
- Move remove (×) button to card header (top-right); show only on `hoveredCard === project.path` (`opacity: isCardHovered ? 1 : 0`, `transition: opacity 150ms`)

### Phase 6 — Pin/star functionality

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** Clicking the star icon on a card toggles `pinned`; pinned projects render above a divider; the star is filled yellow when pinned.

- Import `{ Star }` from `lucide-react`
- Add pin toggle button in the card header, between the project name and the remove button:
  - `<Star size={12} fill={project.pinned ? '#EAB308' : 'none'} color={project.pinned ? '#EAB308' : t.textMuted} />`
  - Show always when `project.pinned`, show only on `hoveredCard` otherwise
  - `onClick={(e) => { e.stopPropagation(); updateProject(project.path, { pinned: !project.pinned }) }}`
- Split `sorted` array into `pinned` and `unpinned`:
  ```tsx
  const pinnedProjects = sorted.filter((p) => p.pinned)
  const unpinnedProjects = sorted.filter((p) => !p.pinned)
  ```
- Render pinned section first (with "PINNED" label in the same muted uppercase style as "RECENT PROJECTS"), then a `<hr>` divider, then unpinned section — only render both sections + divider if `pinnedProjects.length > 0`
- If no pinned projects, render `unpinnedProjects` directly with "RECENT PROJECTS" label as today

### Phase 7 — Improved empty state

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** When `projects` is empty, the page shows a centred FolderOpen icon, "No projects yet" title, subtitle, and the Open folder CTA inline — the current bare text placeholder is replaced.

- Import `{ FolderOpen }` from `lucide-react`
- Replace the existing `No projects yet. Open a folder to get started.` plain div with a centered empty state:
  ```tsx
  <div style={{ padding: '48px 32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', animation: 'fadeSlideUp 300ms ease-out both' }}>
    <FolderOpen size={32} color={t.textMuted} />
    <span style={{ fontSize: '14px', fontWeight: 500, color: t.textPrimary, fontFamily: t.fontFamilyBase }}>No projects yet</span>
    <span style={{ fontSize: '12px', color: t.textMuted, fontFamily: t.fontFamilyBase }}>Open a folder to get started</span>
  </div>
  ```
- The existing "Open project folder" CTA button at the bottom remains and serves as the primary action

---

## Architecture notes

- No new dependencies — `lucide-react` already available
- `pinned` field on `ProjectEntry` persists automatically via zustand `persist` middleware (projects array is already in `partialize`)
- `theme`/`setTheme` from `useStore()` — already merged from `uiStore`; no new store changes needed
- View mode (`grid` | `list`) stored in `localStorage` directly, not in store — keeps store clean for a UI preference that doesn't need cross-component sharing
- The drag strip `WebkitAppRegion: drag` + controls with `WebkitAppRegion: no-drag` is the existing Electron pattern already used in the file
