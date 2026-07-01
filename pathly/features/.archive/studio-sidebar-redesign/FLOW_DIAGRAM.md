# Flow Diagram — studio-sidebar-redesign

---

## Component Tree: Before

```
App.tsx
└── Studio layout
    ├── Sidebar.tsx
    │   ├── [local state: libraryOpen, switchTab handler]
    │   ├── TabBar.tsx
    │   │   ├── "WORKSPACE" tab button
    │   │   └── "LIBRARY" tab button
    │   ├── FilterRow.tsx
    │   │   └── [prop: libraryOpen]
    │   ├── WorkspacePanel.tsx           (rendered when libraryOpen === false)
    │   │   ├── PlanSection.tsx          ← plan folders here
    │   │   ├── Debugs file tree row
    │   │   ├── Explorations file tree row
    │   │   ├── Lessons file tree row
    │   │   └── Pipeline-walkthrough row
    │   └── LibraryPanel.tsx             (rendered when libraryOpen === true)
    │       └── [file-system tree: roles/, flows/, skills/]
    ├── FlowCanvas.tsx
    │   └── [drop target — useCanvasDnD]
    └── Monitor/index.tsx
        ├── EventLog
        ├── FsmView
        └── HealthCheck
```

---

## Component Tree: After

```
App.tsx
└── Studio layout
    ├── Sidebar.tsx
    │   ├── [reads uiStore.activePanel — no local libraryOpen]
    │   ├── [derives sidebarContext: 'workspace' | 'library']
    │   ├── SidebarHeader.tsx            ← NEW (shell/)
    │   │   └── <h2> "Workspace" or "Library" (prop-driven, no toggle)
    │   ├── [CSS transition class toggle on context switch]
    │   ├── WorkspacePanel.tsx           (rendered when context === 'workspace')
    │   │   ├── Debugs file tree row
    │   │   ├── Explorations file tree row
    │   │   ├── Lessons file tree row
    │   │   └── Pipeline-walkthrough row
    │   │   (PlanSection removed)
    │   └── LibraryPanel.tsx             (rendered when context === 'library')
    │       ├── [pill filter row — local useState, ALL|FLOWS|SKILLS|AGENTS|TEMPLATES]
    │       ├── [2-column card grid]
    │       │   └── LibraryCard.tsx      ← NEW (items/)
    │       │       ├── type-color left-border accent
    │       │       ├── JetBrains Mono label
    │       │       ├── description text
    │       │       ├── draggable={true} (Conv 3)
    │       │       └── [Flow type: expandable nested items, each draggable]
    │       └── MyLibraryChips.tsx       ← NEW (items/)
    │           └── horizontal scroll chip row, draggable={true} (Conv 3)
    ├── FlowCanvas.tsx
    │   └── [drop target — useCanvasDnD — UNCHANGED]
    └── Monitor/index.tsx
        ├── PlanProgress.tsx             ← NEW
        │   └── [usePlanFiles() — plan rows, max-height + scroll]
        ├── EventLog
        ├── FsmView
        └── HealthCheck

Deleted components:
    TabBar.tsx                           ← no longer imported
    FilterRow.tsx (or libraryOpen prop)  ← removed/gutted in Conv 1
```

---

## Data Flow: activePanel State to Sidebar Content

```
User clicks Monitor tab / Canvas tab
          │
          ▼
uiStore.setActivePanel('monitor' | 'flow')
          │
          │  Zustand subscription
          ▼
Sidebar.tsx: useStore(uiStore, s => s.activePanel)
          │
          │  useMemo derivation
          ▼
sidebarContext: 'workspace' | 'library'
          │
          ├─── 'workspace' ──► render <WorkspacePanel />
          │                    (Debugs, Explorations, Lessons, Pipeline-walkthrough)
          │
          └─── 'library'  ──► render <LibraryPanel />
                              (pill filters, card grid, My Library chips)

activePanel neither 'monitor' nor 'flow':
  → sidebarContext = 'workspace' (fallback)
  → console.warn emitted in development mode

Transition:
  sidebarContext changes
          │
          ▼
  Sidebar.tsx toggles CSS class on wrapper div
          │
          ▼
  Sidebar.module.css: opacity 0→1, translateY 4px→0 over 150ms
  (single class toggle — no setTimeout chains)
```

---

## Drag Flow: Library Card to Canvas

```
Phase 1 — Drag initiation (LibraryCard.tsx or MyLibraryChips.tsx)

User mousedown on card / chip
          │
          ▼
browser drag start event fires
          │
          ▼
onDragStart handler in LibraryCard.tsx / MyLibraryChips.tsx
          │
          ├─ Build payload:
          │    {
          │      dragType: 'canvas',
          │      name: card.name,
          │      section: mapTypeToSection(card.type),
          │      path: [card.id]
          │    }
          │
          ├─ event.dataTransfer.setData(
          │      'application/pathly-drag-item',
          │      JSON.stringify(payload)
          │    )
          │
          └─ [Flow card nested item only]: event.stopPropagation()
               prevents parent LibraryCard onDragStart from firing

Phase 2 — Drag over canvas

User drags over FlowCanvas
          │
          ▼
FlowCanvas onDragOver
          │  (unchanged — existing handler)
          ▼
browser shows drop cursor

Phase 3 — Drop

User releases on FlowCanvas
          │
          ▼
FlowCanvas onDrop handler
          │  (UNCHANGED — no modifications in any conversation)
          ▼
event.dataTransfer.getData('application/pathly-drag-item')
          │
          ▼
JSON.parse → PathlyCanvasDragItem
          │
          ▼
validate: payload.dragType === 'canvas'
          │
          ▼
useCanvasDnD handler processes drop
  (creates node at drop coordinates, section = payload.section)
```

**Invariant:** `types/index.ts` defines `PathlyCanvasDragItem` and `PATHLY_DRAG_MIME`. Both drag sources and the drop target reference only `types/index.ts`. No other file owns the drag contract.

---

## File Dependency Graph — 7 Files Being Modified

The 7 files being modified across the three conversations, and their dependency edges:

```
Conversation 1 modifications:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  uiStore.ts ──reads──► Sidebar.tsx                     │
│                                   │                     │
│                         ┌─────────┤                     │
│                         │         │                     │
│                         ▼         ▼                     │
│           WorkspacePanel.tsx   LibraryPanel.tsx         │
│           (PlanSection removed)                         │
│                                                         │
│  Sidebar.tsx ──creates──► SidebarHeader.tsx (NEW)       │
│                                                         │
│  Monitor/index.tsx ──creates──► PlanProgress.tsx (NEW)  │
│                    ──reads──► usePlanFiles() hook       │
│                                                         │
└─────────────────────────────────────────────────────────┘

Conversation 2 modifications:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Sidebar.module.css ◄── LibraryPanel.tsx                │
│                    ◄── LibraryCard.tsx (NEW)            │
│                    ◄── MyLibraryChips.tsx (NEW)         │
│                                                         │
│  LibraryPanel.tsx ──renders──► LibraryCard.tsx (NEW)   │
│                   ──renders──► MyLibraryChips.tsx (NEW) │
│                                                         │
└─────────────────────────────────────────────────────────┘

Conversation 3 modifications:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  types/index.ts ◄── LibraryCard.tsx                    │
│  (PathlyCanvasDragItem, PATHLY_DRAG_MIME)               │
│                ◄── MyLibraryChips.tsx                   │
│                ◄── FlowCanvas (existing, unchanged)     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Full dependency matrix for the 7 modified files:**

| File | Imports from | Imported by |
|---|---|---|
| `Sidebar.tsx` | `uiStore`, `SidebarHeader`, `WorkspacePanel`, `LibraryPanel`, `Sidebar.module.css` | App layout |
| `WorkspacePanel.tsx` | `Sidebar.module.css` (and existing sub-items) | `Sidebar.tsx` |
| `LibraryPanel.tsx` | `LibraryCard`, `MyLibraryChips`, `Sidebar.module.css` | `Sidebar.tsx` |
| `SidebarHeader.tsx` (NEW) | `Sidebar.module.css` | `Sidebar.tsx` |
| `LibraryCard.tsx` (NEW) | `types/index.ts`, `Sidebar.module.css` | `LibraryPanel.tsx` |
| `MyLibraryChips.tsx` (NEW) | `types/index.ts`, `Sidebar.module.css` | `LibraryPanel.tsx` |
| `Monitor/index.tsx` | `PlanProgress` (NEW), existing deps | App layout |

**Files that are NOT modified in any conversation:**

- `types/index.ts` — read-only reference for `PathlyCanvasDragItem` and `PATHLY_DRAG_MIME`
- `FlowCanvas.tsx` and `useCanvasDnD` — drop target is untouched
- `uiStore.ts` — `activePanel` already exists; no new fields added
- `PlanSection.tsx` — retained as a file, but import removed from `WorkspacePanel.tsx`
- Any canvas component
