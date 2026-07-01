# Architecture Proposal — studio-sidebar-redesign

---

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Zustand Store Layer                                    │
│                                                         │
│  uiStore                                                │
│    activePanel: 'monitor' | 'flow' | string             │
│    (no libraryOpen, no switchTab — both removed)        │
└─────────────────────┬───────────────────────────────────┘
                      │ useStore(uiStore)
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Shell Layer                                            │
│                                                         │
│  Sidebar.tsx                                            │
│    Derives sidebarContext from activePanel              │
│    Context-switch logic lives HERE — single authority   │
│    Owns transition class toggle                         │
│    Renders: <SidebarHeader> + conditional panel         │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐      ┌───────────────────────────────┐
│  SidebarHeader   │      │  Panel Layer                  │
│  .tsx            │      │                               │
│  (shell/)        │      │  WorkspacePanel.tsx           │
│                  │      │    Renders when context=      │
│  Props:          │      │    'workspace'                │
│    context:      │      │    Lists: Debugs, Explora-    │
│    'workspace'   │      │    tions, Lessons, Pipeline   │
│    | 'library'   │      │    walkthrough                │
│                  │      │    No PlanSection (removed)   │
│  Renders:        │      │                               │
│  plain <h2>      │      │  LibraryPanel.tsx             │
│  label only      │      │    Renders when context=      │
│  No toggle       │      │    'library'                  │
│  No tabs         │      │    Pill filter row            │
└──────────────────┘      │    Card grid                  │
                          │    My Library chips           │
                          └────────────────┬──────────────┘
                                           │
                          ┌────────────────▼──────────────┐
                          │  Item Layer                   │
                          │                               │
                          │  LibraryCard.tsx (items/)     │
                          │  MyLibraryChips.tsx (items/)  │
                          └───────────────────────────────┘
                                           │
                          ┌────────────────▼──────────────┐
                          │  CSS Module Layer             │
                          │                               │
                          │  Sidebar.module.css           │
                          │    --accent-global            │
                          │    --accent-mine              │
                          │    --type-flow/skill/agent    │
                          │      /template                │
                          │    sidebar width, background  │
                          │    transition classes         │
                          │    card-grid layout           │
                          │    pill + chip classes        │
                          └───────────────────────────────┘
```

---

## Dependency Direction

Import rules flow strictly downward. No layer may import from a layer above it.

```
uiStore
  ← Sidebar.tsx (reads activePanel)

Sidebar.tsx
  ← SidebarHeader.tsx
  ← WorkspacePanel.tsx
  ← LibraryPanel.tsx
  ← Sidebar.module.css

LibraryPanel.tsx
  ← LibraryCard.tsx
  ← MyLibraryChips.tsx
  ← Sidebar.module.css (shared tokens via CSS custom properties)

LibraryCard.tsx
  ← types/index.ts (PathlyCanvasDragItem, PATHLY_DRAG_MIME)
  ← Sidebar.module.css

MyLibraryChips.tsx
  ← types/index.ts (PathlyCanvasDragItem, PATHLY_DRAG_MIME)
  ← Sidebar.module.css

Monitor/index.tsx
  ← Monitor/PlanProgress.tsx
  ← usePlanFiles() hook (or PlanSection data source)
```

**What does NOT import what:**
- `LibraryCard.tsx` does not import from `LibraryPanel.tsx` (items do not know their container).
- `SidebarHeader.tsx` does not import from any panel component (it is purely presentational).
- `Sidebar.module.css` does not import from any component (CSS modules are not circular).
- Monitor layer does not import from sidebar layer.

---

## Context-Switch Logic Ownership

The derivation from `activePanel` to `sidebarContext` is owned exclusively by `Sidebar.tsx`. No other component reads `activePanel` for this purpose.

```typescript
// Sidebar.tsx — single authority for context derivation
const activePanel = useStore(uiStore, s => s.activePanel)

const sidebarContext: 'workspace' | 'library' = useMemo(() => {
  if (activePanel === 'flow') return 'library'
  if (activePanel === 'monitor') return 'workspace'
  if (process.env.NODE_ENV === 'development') {
    console.warn(`[Sidebar] Unknown activePanel value: "${activePanel}", falling back to workspace`)
  }
  return 'workspace'
}, [activePanel])
```

`SidebarHeader` receives `context` as a prop — it does not derive it. `WorkspacePanel` and `LibraryPanel` receive no `context` prop — they are conditionally rendered by `Sidebar.tsx` which already knows the context.

---

## State Ownership

| State | Owner | Lifecycle | Notes |
|---|---|---|---|
| `activePanel` | `uiStore` (Zustand) | app session | Source of truth for sidebar content switching |
| `sidebarContext` | `Sidebar.tsx` local memo | re-derived each render | Derived from `activePanel`, not stored |
| `libraryOpen` | REMOVED | — | Was local state in `Sidebar.tsx`; deleted in Conv 1 |
| `switchTab` | REMOVED | — | Was local handler in `Sidebar.tsx`; deleted in Conv 1 |
| Pill filter selection | `LibraryPanel.tsx` local state | component mount | `useState<FilterType>('all')` — local, not global |
| My Library items | `MyLibraryChips.tsx` props | passed from LibraryPanel | Source TBD (static data or future hook) |
| Plan progress rows | `Monitor/PlanProgress.tsx` | via `usePlanFiles()` | Hook already used by `PlanSection` |
| Transition class | `Sidebar.tsx` local class toggle | per context switch | Single class applied; no `setTimeout` chains |

**No new Zustand store fields are introduced.** The pill filter selection is deliberately kept local — it resets when the user switches away from Canvas, which is the correct UX behavior (fresh filter state when returning).

---

## DnD Layer

The drag-and-drop architecture is additive. The canvas drop handler is not modified.

```
types/index.ts
  Defines: PathlyCanvasDragItem { dragType: 'canvas', name, section, path }
  Defines: PATHLY_DRAG_MIME = 'application/pathly-drag-item'
  ↑ read-only reference for both drag sources and drop target

LibraryCard.tsx (drag source — Conv 3)
  onDragStart → event.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
  Nested items inside Flow cards: individual onDragStart + event.stopPropagation()

MyLibraryChips.tsx (drag source — Conv 3)
  onDragStart → event.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))

FlowCanvas (drop target — UNCHANGED)
  onDrop → event.dataTransfer.getData(PATHLY_DRAG_MIME)
  Validates dragType === 'canvas'
  Calls useCanvasDnD handler with parsed payload
```

**Payload mapping — library card data to PathlyCanvasDragItem:**

| Card field | PathlyCanvasDragItem field |
|---|---|
| `type` ('flow' / 'skill' / 'agent' / 'template') | `section` (maps to PathlySection enum/value) |
| `name` | `name` |
| `id` or slug | `path[0]` |
| fixed: `'canvas'` | `dragType` |

The exact mapping from card `type` to `PathlySection` is confirmed in Conv 3 Phase 3.1 audit. The canvas drop handler and `useCanvasDnD` hook are untouched throughout all three conversations.

---

## Monitor Integration

`Monitor/index.tsx` gains a `PlanProgress` sub-component without any structural changes to the Monitor panel itself.

```
Monitor/index.tsx
  Renders (top to bottom):
    <PlanProgress />          ← NEW — Conv 1 Phase 1.5
    <EventLog />              ← unchanged
    <FsmView />               ← unchanged
    <HealthCheck />           ← unchanged

Monitor/PlanProgress.tsx      ← NEW FILE
  Imports: usePlanFiles() hook (same source as PlanSection)
  Renders: plan rows with max-height + overflow-y: auto
  Empty state: "No active plans"
  Loading/error states: graceful degradation (no crash)
```

`PlanSection.tsx` component file is retained but its import is removed from `WorkspacePanel.tsx`. `PlanProgress.tsx` either reuses `PlanSection.tsx` directly or duplicates only the data wiring via `usePlanFiles()`. The builder chooses whichever produces less coupling — this is an implementation detail.

---

## Risk: FilterRow Prop Removal

`FilterRow` currently receives `libraryOpen` as a prop (confirmed by scout). This prop drives behavior that is no longer needed once `libraryOpen` state is removed from `Sidebar.tsx`.

**Resolution options (builder decides in Conv 1 Phase 1.1):**

1. **Remove the prop from `FilterRow`:** If `libraryOpen` only controls sidebar-level visibility that `Sidebar.tsx` now owns via `activePanel`, delete the prop and its consumer logic in `FilterRow`. Preferred if `FilterRow` has no other use for it.

2. **Delete `FilterRow` entirely:** If `FilterRow` was a tab-switching helper component that has no role in the new architecture, remove it and its import from `Sidebar.tsx`. The new pill filter row (Conv 2) replaces it.

Either path must leave `FilterRow` with no reference to `libraryOpen`. If `FilterRow` provides functionality not covered by the new pill row, retain it with the prop removed and a comment noting its narrowed purpose.

The builder must audit `FilterRow`'s full implementation before choosing. This is not an architectural decision — it is a code cleanup judgment call within the builder's authority.
