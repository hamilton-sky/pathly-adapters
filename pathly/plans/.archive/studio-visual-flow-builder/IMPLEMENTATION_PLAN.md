# studio-visual-flow-builder - Implementation Plan

## Overview

This feature makes Pathly Studio's visual flow editor the primary authoring surface. It rebuilds the sidebar as a filesystem-mirroring tree with full CRUD and dual-drag, repairs connected graph rendering from YAML, replaces basic panels with an inspector, validates the canonical flow model, and adds YAML preview/export flows for Pathly, Claude Code, and Codex.

## Layer Architecture

```
Sidebar library       ->  Flow graph model       ->  YAML/export outputs
skills/agents/files       states/transitions         pathly package
templates/flows           node/edge config           Claude Code/Codex

React components      ->  hooks/types/utils      ->  pathlyApi/fs writes
```

## Conversation Map

| Conv | Phases | Focus |
|------|--------|-------|
| 1 | 1, 2, 3 | Graph rendering, resync, canonical model |
| 2a | 4, 4b, 4c, 4d | Sidebar types, filesystem tree, CRUD, context menus |
| 2b | 5, 6, 7 | Click behavior, dual-drag, canvas drop |
| 3 | 7b, 8, 9, 10, 11 | z-index, docked inspector, node/edge panels, validation |
| 4 | 12, 13, 14 | YAML sync hardening, export UI, helpers |

## Phases

### Phase 1: Restore connected graph rendering <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` - MODIFY: add React Flow source and target handles, compact connection affordances, and invalid-state badges.
**Done when:** Existing YAML transitions can attach visually to state nodes.
**Delivers stories:** S1
**Depends on:** Existing React Flow setup.
**Enables:** Canvas edge creation and edge inspector behavior.
**Details:**
Add `Handle` components from `reactflow`. Keep the node compact and consistent with current Studio styling. On node hover, show handles with a scale animation (0.8→1.0, 150ms ease-out) so they are discoverable without dominating the resting state. Consider a one-time tooltip on the first node: "Drag from dot to connect →".
**Verify:** `cd studio; npm run typecheck`

### Phase 2: Resync graph state when selected flow changes <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` - MODIFY: rebuild nodes and edges when `data` or selected flow changes, without wiping in-progress edits from the current file.
**Done when:** Switching from `debug.flow.yaml` to another flow shows that flow's own nodes and edges.
**Delivers stories:** S1
**Depends on:** Phase 1.
**Enables:** Stable visual editing across flow files.
**Details:**
Use React Flow setters to rehydrate nodes and edges from `flowToGraph(data, t)` when the flow identity changes. Avoid stale closures by keeping `dataRef` current. Preserve semantic edits through `onChange`.
**Verify:** `cd studio; npm run typecheck`

### Phase 3: Keep visual graph edits canonical <- Conversation: 1

**File:** `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` - MODIFY: make YAML-to-graph conversion deterministic, label edges from actual transition metadata, and tolerate malformed references.
**File:** `studio/src/renderer/src/types/index.ts` - MODIFY: extend `FlowYaml` to include `storage_path?: string` and `feedback_routing?: Record<string, string>` so existing YAML keys round-trip without loss.
**Done when:** Visual connect actions add transitions and YAML preview/save reflects those transitions. `debug.flow.yaml` round-trips through visual edit and YAML serialize without losing `storage_path` or `feedback_routing`.
**Delivers stories:** S2
**Depends on:** Phase 2.
**Enables:** Drag/drop and inspector edits to write through the same model.
**Details:**
Keep node position layout deterministic (column layout `i * 220` is fine for now). Use stable edge ids of form `${source}__${target}` so the same edge across re-renders has the same id. Label edges from the runtime schema:
- `transition_rules[source].default === target` -> `default`
- `transition_rules[source].on_artifact[artifactName] === target` -> `artifactName`
- `transition_rules[source].on_content[]` entries whose `next` is `target` -> their file/contains/regex summary
- `transition_rules[source].decide.options[option] === target` -> the option label
Tolerate transitions whose source or target is missing from `states` by skipping the edge and emitting a validation issue (Phase 11 surfaces it). Do not drop unknown YAML keys.
**Verify:** `cd studio; npm run typecheck`

### Phase 4: Define filesystem-tree types and section model <- Conversation: 2a

**File:** `studio/src/renderer/src/types/index.ts` - MODIFY: replace flat library item types with filesystem-tree node types and section-aware drag payload.
**Done when:** UI code can represent tree nodes (file vs folder), section membership, and both drag modes in a type-safe way.
**Delivers stories:** S3, S8
**Depends on:** Conversation 1 completed.
**Enables:** Phases 4b–6.
**Details:**

```ts
// Sidebar section domains — the four managed directories
type PathlySection = 'skills' | 'agents' | 'flows' | 'templates';

// A node in the filesystem tree (file or category folder)
interface PathlyTreeNode {
  name: string;               // filename or folder name
  type: 'file' | 'folder';
  path: string[];             // path segments from section root
  section: PathlySection;
  children?: PathlyTreeNode[]; // present on folders once loaded
  handle?: FileSystemHandle;  // Electron local FS handle
}

// Drag payload for canvas assignment (from ⠿ grip)
interface PathlyCanvasDragItem {
  dragType: 'canvas';
  name: string;               // e.g. "review.md"
  section: PathlySection;     // 'skills' | 'agents'
  path: string[];
}

// Drag payload for tree reorg (from row body)
interface PathlyReorgDragItem {
  dragType: 'reorg';
  name: string;
  section: PathlySection;     // drop handlers reject mismatched sections
  path: string[];
  type: 'file' | 'folder';
}

type PathlyDragItem = PathlyCanvasDragItem | PathlyReorgDragItem;
```

Use MIME key `application/pathly-drag-item` for both drag types (differentiated by `dragType` field in the payload).

**Section defaults:**
- Default-open: Flows, Skills, Agents
- Default-collapsed: Templates, Workspace

**File type constraints per section:**
- SKILLS / AGENTS / TEMPLATES → `.md` files
- FLOWS → `.flow.yaml` files

**Domain icons (Lucide):**

| Section | Folder icon | File icon | File icon color |
|---|---|---|---|
| SKILLS | `Folder` violet | `Wrench` | `textMuted` |
| AGENTS | `Folder` violet | `Bot` | `textMuted` |
| FLOWS | `Folder` violet | `Workflow` | `runtime cyan #22D3EE` |
| TEMPLATES | `Folder` violet | `FileText` | `textMuted` |
**Verify:** `cd studio; npm run typecheck`

### Phase 4b: Rebuild Sidebar as filesystem-tree component <- Conversation: 2a

**File:** `studio/src/renderer/src/components/Sidebar.tsx` - REWRITE: replace the flat section list with a filesystem-mirroring tree using the ZakaMurai `Sidebar.js` / `TreeItem.js` pattern, adapted for Pathly's four domain sections.
**File:** `studio/src/renderer/src/components/Sidebar.module.css` - MODIFY: add tree item styles, drop target highlight, drag ghost, grip icon, section header hover reveal.
**Done when:** The sidebar shows Skills, Agents, Flows, Templates as collapsible trees that mirror the actual directory structure. Category folders expand/collapse. Global filter highlights matches and collapses empty sections.
**Delivers stories:** S3, S8
**Depends on:** Phase 4.
**Enables:** CRUD (Phase 4c), context menus (Phase 4d), dual-drag (Phase 6).
**Details:**

Structure: four fixed section root nodes (SKILLS, AGENTS, FLOWS, TEMPLATES) plus a WORKSPACE nav block. Section roots cannot be renamed or deleted.

Each section root loads its directory tree on mount and re-loads on `fs.version` change (same pattern as ZakaMurai's `useEffect` on `fs.files`). Use a `VirtualList` for performance if item counts exceed ~50.

Tree item row layout:
```
[⠿ grip][domain icon][  name  ][chevron if folder]    [🔧+][📁+] on hover
```

Section header row layout:
```
[chevron][  SECTION LABEL  ]                           [🔧+][📁+] on hover
```

- Grip (`⠿`, `GripVertical`) is visible only on skill and agent file rows (not folders, not flows, not templates).
- Section header `+` icons are hover-reveal only, flush-right.
- Folder rows show expand/collapse chevron. File rows show no chevron.
- Active flow indicator: cyan `●` dot on any `.flow.yaml` that is currently running (SSE signal). Read from monitor state.
- Workspace section (Plan, Monitor, Settings): nav-link rows only — no grip, no `+` actions, no drag.
**Verify:** `cd studio; npm run typecheck`

### Phase 4c: Add CRUD operations to sidebar tree <- Conversation: 2a

**File:** `studio/src/renderer/src/components/Sidebar.tsx` - MODIFY: implement create, rename, and delete handlers on the tree component.
**Done when:** Users can create `.md` / `.flow.yaml` files, create category folders, rename via double-click, and delete with a confirmation dialog — all within their section.
**Delivers stories:** S3
**Depends on:** Phase 4b.
**Enables:** Full user control over library organization.
**Details:**

**Create file:**
- Triggered by hover-reveal `[🔧+]` icon on section header or folder row.
- Inline input row appears as a child of the selected folder (or section root if nothing selected).
- Ghost extension shown after cursor: `.md` for skills/agents/templates, `.flow.yaml` for flows.
- On `Enter`: append ghost extension if user has not typed one (stem-only input → auto-append). If user typed a wrong extension, show inline error `"Skills must be .md files"` and keep input open. Do not auto-rename.
- On `Escape`: cancel, remove input row.

**Create folder:**
- Triggered by hover-reveal `[📁+]` icon.
- Inline input appears at the same level as the icon source.
- No extension ghost — folders have no extension.

**Rename:**
- Double-click on any non-root item name activates inline edit input in place.
- `Enter` confirms, `Escape` cancels.
- Cascade: update any open editor tabs whose path matches the old path (mirror ZakaMurai `handleRename` tab cascade).

**Delete:**
- Right-click → "Delete" (see Phase 4d context menu).
- Confirmation dialog: "Delete 'writing/' and its 3 files? This cannot be undone." Dialog shows file count for folders; plain name for files.
- On confirm: remove from tree, close any tabs whose path is under the deleted path.

**Move (tree reorg):**
- Drag-and-drop within section (Phase 6 wires the drag; this phase implements the drop handler).
- After drop: update tree state and rename open tabs with the new path prefix (mirror ZakaMurai `handleDrop`).
**Verify:** `cd studio; npm run typecheck`

### Phase 4d: Add context menus to sidebar tree <- Conversation: 2a

**File:** `studio/src/renderer/src/components/SidebarContextMenu.tsx` - CREATE: right-click context menu component, rendered at cursor position, dismissed on outside click.
**Done when:** Right-clicking any tree item opens a context menu with the correct actions for that item type.
**Delivers stories:** S3, S8
**Depends on:** Phase 4c.
**Enables:** Discoverability of CRUD operations beyond hover icons.
**Details:**

Context menu items by item type:

**Section root (e.g. SKILLS header):**
```
  🔧 New skill file
  📁 New category
```

**Category folder:**
```
  🔧 New skill file      (label adapts: "New flow" for FLOWS)
  📁 New subcategory
  ─────────────
  ✏  Rename
  ─────────────
  🗑  Delete
```

**Skill / Agent file:**
```
  👁  Open preview
  ─────────────
  ✏  Rename
  →  Move to…           (submenu: category folders in section + "/ Root")
  ─────────────
  🗑  Delete
```

**Flow file:**
```
  ⚡ Open in canvas
  👁  Open source (YAML)
  ─────────────
  ✏  Rename
  →  Move to…
  ─────────────
  🗑  Delete
```

Menu styling: `bgSurface1 #252C36` background, 4px border radius, 1px `borderSubtle` border, 12px text. Destructive items (`Delete`) use `#EF4444` text. Dividers are 1px `borderSubtle` lines. Menu dismisses on outside click or `Escape`.
**Verify:** `cd studio; npm run typecheck`

### Phase 5: Wire click behavior for tree items <- Conversation: 2b

**File:** `studio/src/renderer/src/components/Editor/index.tsx` - MODIFY: when `selectedItem.type` is `skill`, `agent`, or `template`, initialize `tab` to `'preview'` and add a gated "Edit source" affordance.
**Done when:** Clicking a skill, agent, or template file opens read-only preview. Clicking a flow file opens the visual canvas. Clicking a folder expands/collapses it.
**Delivers stories:** S8
**Depends on:** Conversation 2a completed.
**Enables:** Progressive disclosure — library items are reuse primitives by default.
**Details:**
Do not introduce a new preview panel. The existing `Editor` already supports a `preview` tab; the change is the default tab plus a small "Edit source" toolbar button. Do not auto-save while previewing. Frontmatter (`ConfigForm`) shown read-only in preview.

Click behavior by item type:
- **Skill / Agent / Template file**: open Editor in `preview` tab → "Edit source" button available in toolbar
- **Flow file**: open visual canvas editor (existing behavior)
- **Folder**: expand/collapse tree node — no editor opened
- **Workspace items** (Plan, Monitor, Settings): navigate to that Studio panel
**Verify:** `cd studio; npm run typecheck`

### Phase 6: Wire dual-drag — canvas assign and tree reorg <- Conversation: 2b

**File:** `studio/src/renderer/src/components/Sidebar.tsx` - MODIFY: add two distinct drag behaviors to the tree component.
**Done when:** Dragging from the `⠿` grip assigns a skill/agent to a canvas node. Dragging a row body moves the item within its section. Cross-section drops are rejected silently.
**Delivers stories:** S3
**Depends on:** Phase 4c.
**Enables:** Canvas drop behavior (Phase 7) and within-section reorganization.
**Details:**

**Canvas drag (from `⠿` grip — skills and agents only):**
- `onMouseDown` / `onPointerDown` on the grip element sets `dragType: 'canvas'` in a ref before the drag starts.
- `onDragStart` on the row: if drag originated from grip, set payload `{ dragType: 'canvas', name, section, path }` on `dataTransfer` with MIME `application/pathly-drag-item`. Set `effectAllowed = 'copy'`.
- Canvas drag ghost: violet `#8B5CF6` border, semi-transparent item chip.
- This drag type is consumed by the canvas drop handler (Phase 7).

**Tree reorg drag (from row body — all file/folder items):**
- `onDragStart` on the row: if drag did NOT originate from grip, set payload `{ dragType: 'reorg', name, section, path, type }`. Set `effectAllowed = 'move'`.
- Drop handler on folder rows: reject if `payload.dragType !== 'reorg'` OR `payload.section !== thisFolderSection`. Set `dropEffect = 'none'` for rejected drops → browser shows `not-allowed` cursor automatically.
- Valid drop target (same-section folder): highlight with `border-left: 2px solid #8B5CF6` + `rgba(139,92,246,0.08)` background. No highlight on foreign sections — they are inert.
- On successful drop: call `handleDrop` from Phase 4c (moves file, updates tree, cascades tab paths).

**Cross-section constraint:** The drop handler checks `payload.section === dropTargetSection`. If they differ, return without calling `preventDefault()` — the browser's default drag rejection behavior (`not-allowed` cursor) applies. No red tint on foreign sections.
**Verify:** `cd studio; npm run typecheck`

### Phase 7: Handle canvas drops <- Conversation: 2b

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: accept dropped library items, assign them to an existing node when dropped over one, or create a new state when dropped on empty canvas.
**Done when:** Dropping a skill or agent changes the flow data and marks the selected flow dirty.
**Delivers stories:** S3
**Depends on:** Phase 6.
**Enables:** Inspector-driven refinement.
**Details:**
Wrap React Flow in a `<ReactFlowProvider>` so the drop handler can call `useReactFlow().screenToFlowPosition` for canvas-space coords. On `onDrop`, parse the `application/pathly-library-item` payload, then:
- If the drop event target resolves to an existing `stateNode`, update `agent_map[stateId]` with the item name (without extension).
- Otherwise, generate a unique uppercase state id from the item name (e.g. `commit.md` -> `COMMIT`, with `_2` suffix on collision), append to `states`, set `agent_map[newId]`, and place the new node at the converted drop coordinates.
- Always call `onChange(updated)` so the selected file is marked dirty.
Keep canvas position as UI state only; do not write positions to YAML in this feature.

**Canvas toolbar `+` button:** Confirm that a bare "+ Add state" button exists in the canvas toolbar by Phase 7 (or Phase 1 at latest). If a user has no skills/agents to drag from the library, they must still be able to add a bare state node from the canvas directly. This button creates an unnamed state with a generated ID and no assigned behavior.
**Verify:** `cd studio; npm run typecheck`

### Phase 7b: Create z-index constants file <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/zIndex.ts` - CREATE: export a single constants object with the full z-index scale used in the flow editor.
**Done when:** All flow editor components import z-index values from this file rather than hardcoding them.
**Delivers stories:** S4, S5
**Depends on:** Conversation 2b completed.
**Enables:** Phase 8 (inspector) and Phase 9 (behavior picker popover) to reference a canonical scale without collision.
**Details:**
```ts
export const Z = {
  canvas:    0,
  inspector: 10,
  popover:   40,
  toast:     60,
  modal:     100,
} as const;
```
Do this before any other Conversation 3 phase. The behavior picker popover (z=40) must render above the inspector (z=10) but below toasts (z=60). Without a constants file this scale drifts during implementation.
**Verify:** `cd studio; npm run typecheck`

### Phase 8: Convert inspector overlay into a docked third pane <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: replace the absolutely-positioned overlay with a flex-row layout that makes the inspector a sibling pane of the canvas.
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/VisualView.styles.ts` - MODIFY: replace `detailPanel: { position: 'absolute', ... }` with a docked layout: canvas flex 1, inspector fixed 300px (from `DESIGN.md`).
**Done when:** Opening the inspector reduces canvas width without remounting React Flow; closing returns it to full width.
**Delivers stories:** S4, S5
**Depends on:** Conversation 2b completed.
**Enables:** Phases 9 and 10 to assume a stable docked inspector surface.
**Details:**
React Flow handles container resize automatically when inside a flex parent. Apply `transition: width 200ms` only when `prefers-reduced-motion` is not set. Set the inspector container's `z-index` to 10 per the `DESIGN.md` scale.
**Verify:** `cd studio; npm run typecheck`

### Phase 9: Replace node panel with node inspector <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` - MODIFY: implement identity, assigned behavior, transition summary, and validation sections.
**Done when:** Clicking a node opens a useful inspector that can edit node behavior and show validation issues.
**Delivers stories:** S4
**Depends on:** Phase 8.
**Enables:** Full no-YAML node authoring.
**Details:**
Use the docked inspector layout introduced in Phase 8. Implement the "Assigned behavior" picker as a popover from `DESIGN.md` (chip-style trigger -> searchable list with type filter; z-index 40 from `Z.popover` in `zIndex.ts`). Source the list from `useProjectFiles().sections.Skills.items` and `sections.Agents.items`. Missing-on-disk references stay selected with a warning badge. State rename is **out of scope for this feature** to avoid touching `transitions`/`agent_map`/`transition_rules`/`transition_actions` cascade; show state id as read-only with a hint "Rename in YAML view for now."

**Keyboard trap (required):** The behavior picker popover must implement a full keyboard trap: `↑`/`↓` to navigate items, `Enter` to select, `Esc` to close and return focus to the chip trigger. Keyboard-only users cannot use the picker without this. Do not ship Phase 9 without verifying keyboard navigation works end-to-end.

**onChange synchronization:** Inspector field `onChange` handlers must write to the graph model synchronously — no debounce. Debounce only CodeMirror YAML edits (Phase 12). If `onChange` is debounced here and the user presses `Ctrl+S` immediately after an inspector edit, the save captures stale model state.
**Verify:** `cd studio; npm run typecheck`

### Phase 10: Replace edge panel with edge inspector <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` - MODIFY: implement transition condition, artifact gate, and action editing.
**Done when:** Clicking an edge opens a useful inspector that can add or edit transition actions.
**Delivers stories:** S5
**Depends on:** Phase 9.
**Enables:** Visual routing configuration.
**Details:**
Keep YAML structures compatible with existing `transition_actions` (`"SOURCE->TARGET": [{ skill, message }]`) and the real runtime `transition_rules` schema:

```yaml
transition_rules:
  SOURCE:
    on_artifact:
      ARTIFACT.md: TARGET
    on_content:
      - file: NOTES.md
        contains: "ready"
        next: TARGET
    decide:
      question: "Where next?"
      options:
        approve: TARGET
      default: approve
    default: TARGET
```

Do not use the older incorrect shape `{ artifact_name: { source: target } }`. The edge inspector should edit the rule object for the edge source state and ensure the chosen target is one of that source's declared `transitions[source]`. Use existing `handleAddTransitionAction` and `handleAddTransitionRule` from `useFlowGraph` only after updating them to this state-keyed schema; extend with edit + delete. Avoid inventing a new flow schema.

**Human-readable label mapping (required — do not expose raw YAML keys in the inspector UI):**

| YAML key | Inspector label | Lucide icon |
|---|---|---|
| `default` | "Always continues to →" | `ArrowRight` |
| `on_artifact` | "When artifact arrives:" | `FileCheck` |
| `on_content` | "When file contains:" | `FileSearch` |
| `decide` | "Human decision required:" | `GitFork` |
| `transition_actions` | "Run before transitioning:" | `Zap` |

Raw YAML key names (`on_artifact`, `decide`, etc.) must appear only in the YAML tab, never in the visual inspector. The label mapping lives in `EdgePanel.tsx` as a constants object.

**Interaction pattern for conditions:**
- Adding a condition: `+ Add condition` button at bottom of the conditions section → inline form (type selector → type-specific fields). Not a modal.
- Removing a condition: `×` icon on the condition row + a brief undo toast.
- Multiple conditions to the same target: show stacked; surface a validation warning if they could conflict.
**Verify:** `cd studio; npm run typecheck`

### Phase 11: Extract validation utility and surface issues <- Conversation: 3

**File:** `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` - CREATE: pure function that takes `FlowYaml` plus known skill/agent names and returns `FlowValidationIssue[]`.
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: run validation each render, pass issues into `StateNode` (badge), edge style (color), and inspector (inline error rows).
**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` - MODIFY: accept an optional `issues` array and render a subtle warning badge (Lucide `AlertTriangle`) when present.
**Done when:** Invalid graph conditions are visible inline before save/export. Inspector inputs validate on blur, with `role="alert"` and `aria-live="polite"`.
**Delivers stories:** S4, S5
**Depends on:** Phase 10.
**Enables:** Safe YAML preview and export.
**Details:**
Run the validation checks listed in `DESIGN.md` (states exist, transitions reference real states, behavior references exist, non-terminal states have outgoing transitions, terminal states do not require outgoing). Also validate runtime routing compatibility:
- every `transition_rules` key is an existing state
- every `default`, `on_artifact`, `on_content.next`, and `decide.options/default` target is listed in `transitions[source]`
- every `transition_actions` key uses `SOURCE->TARGET` or `->TARGET` and points at known transitions/states
Keep messages short ("Target state DEPLOY missing", "Behavior commit not in library"). Do not use banners.
**Verify:** `cd studio; npm run typecheck`

### Phase 12: Harden YAML preview sync <- Conversation: 4

**File:** `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` - MODIFY: preserve the last valid parsed model, show parse errors, and prevent unsafe visual switches.
**Done when:** Invalid YAML does not destroy the last valid graph and valid YAML rehydrates Visual view.
**Delivers stories:** S6
**Depends on:** Conversation 3 completed.
**Enables:** User trust in round-trip editing.
**Details:**
Coordinate with `useFlowFile.ts` so raw YAML and parsed flow data stay explicit. Surface YAML parse errors via the existing error banner; on a tab switch back to Visual while YAML is invalid, keep the last valid `flowData` rendered and show a non-blocking warning.
**Verify:** `cd studio; npm run typecheck`

### Phase 13: Add export target UI and service calls <- Conversation: 4

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` - MODIFY: add export controls and target selection for Pathly package, Claude Code, and Codex per the toolbar layout in `DESIGN.md`.
**Done when:** A valid flow can be exported through an explicit target action.
**Delivers stories:** S7
**Depends on:** Phase 12.
**Enables:** Packaging workflows.
**Details:**
Use one canonical YAML serialization (`jsYaml.dump(flowData, { lineWidth: 120 })`). Export target adapters write the same content to host-specific paths:

| Target | Destination | Notes |
|---|---|---|
| Pathly package | `${projectPath}/src/pathly_data/core/flows/${flow}.flow.yaml` | Overwrites in place; same path as the source flow. |
| Claude Code | `${projectPath}/.claude/pathly-flows/${flow}.flow.yaml` | Creates folder if missing. Claude Code reads from `.claude/`. |
| Codex | `${projectPath}/.codex/pathly-flows/${flow}.flow.yaml` | Creates folder if missing. Mirrors the Claude Code convention for now. |

Disable the Export button while `validateFlow` returns errors. Warnings require an explicit confirmation modal. Successful export shows a toast with a "Copy path" action.

**Last-exported path hint:** Below the target dropdown + Export button, show the last-exported destination as a muted one-line status:
```
[Pathly package ▾]  [Export]
Last: src/pathly_data/core/flows/debug.flow.yaml  ✓ 3m ago
```
Store this in component state (not persisted). Reset on flow file change. This gives users confidence the file landed where they expect without requiring them to navigate the filesystem.

**Export button placement:** Keep a visible divider between layout controls (zoom/fit/lock) and authoring controls (validate/export) in the canvas toolbar. Export must not be visually buried next to zoom buttons.
**Verify:** `cd studio; npm run typecheck`

### Phase 14: Add export helpers if needed <- Conversation: 4

**File:** `studio/src/renderer/src/services/pathlyApi.ts` - MODIFY: add a minimal helper for writing exported flow files when the destination directory does not exist yet. Add only if `writeFile` does not already create missing parent directories on the IPC side.
**Done when:** Export does not duplicate filesystem IPC logic in React components.
**Delivers stories:** S7
**Depends on:** Phase 13.
**Enables:** Cleaner host-specific export behavior.
**Details:**
Keep Electron IPC boundaries unchanged unless a missing capability blocks export. The current main-process `fs:write` handler already calls `fs.mkdirSync(path.dirname(filePath), { recursive: true })`, so this phase is expected to be a no-op unless that behavior changes before implementation. Prefer reusing `writeFile(path, content)` from `pathlyApi.ts` directly for export writes.
**Verify:** `cd studio; npm run typecheck`

## Prerequisites

- Confirm current dirty files before implementation and do not overwrite unrelated user edits.
- Verify React Flow imports and current canvas behavior before editing.
- Treat existing `src/pathly_data/core/flows/*.flow.yaml` as schema examples.

## Key Decisions

- Canvas is the primary authoring model; wizard becomes a template starter.
- YAML remains inspectable and editable, but it serializes from the canonical graph model.
- The sidebar is a **filesystem-mirroring tree** per domain section. Each section maps to a real directory (`skills/`, `agents/`, `flows/`, `templates/`). Users organize with category folders; Studio reflects what is on disk.
- All flows — team, debug, explore, custom — live in the FLOWS section. There are no special-cased flow types in the sidebar. Users create category folders to organize them.
- Skills and agents have **two distinct drag modes**: `⠿` grip → canvas assign; row body → tree reorg within section. Cross-section reorg is rejected.
- Skills, agents, and templates are exposed for **reuse by default**. Clicking such an item opens read-only preview; editing the source requires an explicit user action.
- Export targets are adapters over one canonical flow model, not separate editors.

## Scope Exclusions

The following are explicitly **out of scope** for this feature. Do not implement them in any of the conversations.

| Excluded | Why |
|---|---|
| **Multi-select in sidebar** | Single-item drag/CRUD is sufficient. Multi-select is a future enhancement. |
| **Cut/copy/paste in sidebar** | Context menu covers move-to. Clipboard operations are a future enhancement. |
| **Cross-section move** | A skill cannot become an agent. Domain boundaries are enforced; cross-section ops are rejected silently. |
| **Drag/drop from OS filesystem onto the canvas** | Library is the only source of skills/agents. OS filesystem drag is a separate future feature. |
| **State rename from the node inspector** | Renaming a state requires cascading edits to `transitions`, `agent_map`, `transition_rules`, `transition_actions`. YAML view is the rename path. |
| **Persisting canvas node positions to YAML** | Positions stay UI state only. A future layout-persistence feature can revisit this. |
| **Editing skills/agents/templates from inside the visual flow editor** | The visual editor is for assembly. Editing source requires an explicit action in the existing Editor. |
| **Redesigning Monitor, Terminal, TopBar, PlanBoard, Settings, HomeScreen, SetupScreen, FlowWizard** | These surfaces are stable. Monitor improvements are a separate `studio-monitor-live` plan. |
| **MCP runtime, Electron installer, or backend changes** | This feature is renderer-side except for the optional `pathlyApi.ts` helper in Phase 14. |
| **Workspace rows (Plan, Monitor, Settings) drag/CRUD** | Workspace items are navigation destinations, not library primitives. Click-to-navigate only. |
