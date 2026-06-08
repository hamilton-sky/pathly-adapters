# Pathly Studio — Frontend Specification

## Reference designs (existing HTML previews)
- `pathly/pathly-design/Pathly Studio.html` — Monitor, Notebook, DB Explorer views
- `pathly/pathly-design/DB Explorer.html` — standalone DB Explorer with rail nav
- Color system: Catppuccin Mocha (CSS vars already in `dbx/styles.css`)
- Font: JetBrains Mono (already loaded)

---

## Tech stack
- Electron + React 18 + TypeScript
- Zustand (state management)
- ReactFlow (canvas — already in codebase)
- node-pty (terminals — already in codebase)
- All HTTP calls: `fetch()` to `http://127.0.0.1:8765`
- SSE: `new EventSource('http://127.0.0.1:8765/events/runner?...')`

---

## Pages

| Page | Route key | Purpose |
|---|---|---|
| **Home / Monitor** | `monitor` | Feature list, run controls, live event log |
| **Notebook** | `notebook` | Universal markdown editor for all .md files |
| **Canvas** | `canvas` | Visual flow builder (ReactFlow) |
| **DB Explorer** | `dbx` | Feature cards, event log, agents, artifacts |
| **Settings** | `settings` | Adapters, cost limits, OTel, theme |

---

## App shell layout

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER                                                      │
│  ☰  Projects  │  <project-name> ▾  │  [Canvas][Notebook]   │
│               │  [Monitor][DB Explorer]    │  ◾ ◾ ✕         │
├──────┬──────────────────────────────────────────────────────┤
│      │                                                       │
│ SIDE │   MAIN CONTENT AREA                                   │
│  BAR │   (changes per page)                                  │
│      │                                                       │
│      │                                                       │
└──────┴──────────────────────────────────────────────────────┘
```

The sidebar content changes completely per page (see below).
The header view-switcher is the primary navigation.

---

## Sidebar — per page

### Home / Monitor sidebar
```
┌─────────────────┐
│ [Workspace][Lib]│  ← two tabs
├─────────────────┤
│ Filter…         │
├─────────────────┤
│ Workspace:      │
│  ▸ ◆ login-flow │
│  ▸ ◇ auth-refac │
│  ▸ ◇ payments   │
│  ─────────────  │
│  ⚡ Monitor     │
│  ⛁ DB Explorer │
│  ⚙ Settings    │
├─────────────────┤
│ Library:        │
│  📖 fix/build   │
│  📖 team/build  │
│  📖 review/gate │
└─────────────────┘
```

### Notebook sidebar
```
┌─────────────────┐
│ FILES           │
├─────────────────┤
│ Skills          │
│  📖 fix/build   │  ← global (project_root=NULL)
│  📖 team/build  │
│  📖 review/gate │
│  ─────────────  │
│  LOCAL          │
│  📖 my-review   │  ← local (project_root=current)
├─────────────────┤
│ Agents          │
│  🤖 builder     │
│  🤖 reviewer    │
│  🤖 tester      │
├─────────────────┤
│ Feature Files   │
│  📄 USER_STORIES│
│  📄 IMPL_PLAN   │
│  📄 REVIEW_FAIL │
├─────────────────┤
│ + New skill     │
│ + New agent     │
└─────────────────┘
```

### Canvas sidebar
```
┌─────────────────┐
│ FLOWS           │
├─────────────────┤
│ ● team          │  ← active
│   standard      │
│   nano          │
│ ─────────────── │
│ + New flow      │
├─────────────────┤
│ NODE PROPERTIES │  ← shown when node selected
│ Name: BUILD     │
│ Agent: builder  │
│ Skill: build.md │
│ Adapter: claude │
├─────────────────┤
│ EDGE PROPERTIES │  ← shown when edge selected
│ From: BUILD     │
│ To:   REVIEW    │
│ Cond: PASS      │
└─────────────────┘
```

### DB Explorer sidebar
```
(none — DB Explorer is full width)
```

### Settings sidebar
```
┌─────────────────┐
│ SETTINGS        │
├─────────────────┤
│ ● Adapters      │
│   Cost limits   │
│   OTel / Traces │
│   Appearance    │
│   DB & Storage  │
│   Export / Import│
└─────────────────┘
```

---

## The Notebook — universal markdown editor

The notebook is used for ALL markdown files in Pathly:
- Skills (`pathly-build.md`, `pathly-review.md`, etc.)
- Agent definitions
- Feature artifacts (`USER_STORIES.md`, `REVIEW_FAILURES.md`)

**One editor, all .md content.**

### Layout
```
┌────────────────────────────────────────────────────────┐
│  BREADCRUMB                              [Export] [▶▶] │
│  Skills › fix › build                   NOTEBOOK       │
├───────────────────────────────┬────────────────────────┤
│  CELL LIST (left)             │  COMPOSED PREVIEW (rt) │
│                               │                        │
│  [1] # fix/build              │  [Preview] [Raw]       │
│      HEADING cell             │                        │
│      ↑ ↓ ✎ 🗑                │  (full rendered skill) │
│                               │                        │
│  [2] ## Role                  │                        │
│      markdown cell            │                        │
│      ↑ ↓ ✎ 🗑                │                        │
│      [edit mode: textarea]    │                        │
│                               │                        │
│  [3] ### fragment `CORE`      │                        │
│      fragment cell            │                        │
│      ↑ ↓ ✎ 🗑                │                        │
│                               │                        │
│  + Text cell  + Fragment      │                        │
└───────────────────────────────┴────────────────────────┘
```

### Cell types
| Kind | Description | Icon |
|---|---|---|
| `heading` | Section title (h1/h2) — collapsible | `#` |
| `markdown` | Regular instruction/text block | `¶` |
| `fragment` | Named reusable fragment with badge (CORE, etc.) | `⊞` |

### Cell interactions
- Click cell → select (highlight)
- Click ✎ → toggle edit mode (textarea replaces rendered preview)
- In edit mode: Save / Cancel buttons
- ↑ / ↓ buttons → reorder (animated swap)
- 🗑 → delete (with undo)
- Keyboard: Ctrl+Z = undo, Escape = cancel edit
- Search bar: filters visible cells, highlights matches

### Per-cell edit vs preview toggle
Each cell independently toggles between:
- **Preview mode** (default): rendered markdown HTML
- **Edit mode**: textarea with raw markdown, Save/Cancel

The right panel always shows the composed full-skill preview (all cells joined).
Right panel has its own Preview/Raw toggle for the full composed output.

### File types and their cell shapes
| File | Cell kinds used | Source table |
|---|---|---|
| Skill `.md` | heading + markdown + fragment | `skill_definitions.content` |
| Agent definition | heading + markdown | `agent_definitions.instructions` |
| `USER_STORIES.md` | heading + markdown | `stage_artifacts.content` (read-only) |
| `REVIEW_FAILURES.md` | heading + markdown | `stage_artifacts.content` (read-only) |

Artifact files (USER_STORIES, REVIEW_FAILURES) open in **read-only** notebook mode — no edit, no reorder. Just rendered cells + composed preview.

---

## Canvas — flow builder

```
┌──────────────────────────────────────────────────────┐
│  [team ▾]  [+ Node]  [+ Edge]  [Save]  [Run]        │
├──────────────────────────────────────────────────────┤
│                                                      │
│    ┌──────────┐  PASS  ┌──────────┐  PASS           │
│    │  BUILD   │───────>│  REVIEW  │──────>  ...      │
│    │ builder  │        │ reviewer │                   │
│    │ build.md │        │ review.md│                   │
│    │ claude   │        │ codex    │                   │
│    └──────────┘        └──────────┘                  │
│         ▲                   │ FAIL                   │
│         └───────────────────┘                        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

- Each node = a `flow_node` row
- Each edge = a `flow_edge` row with condition label
- Click node → sidebar shows node properties (agent, skill, adapter)
- Click edge → sidebar shows edge properties (condition)
- Drag to reposition → updates `pos_x`, `pos_y`
- Save button → `POST /api/flows`
- Condition options on edge: `PASS`, `FAIL`, `BLOCK`, (unconditional)

---

## DB Explorer

```
┌──────────────────────────────────────────────────────┐
│  DB Explorer   ↻ Refresh   ⬇ Migrate   ⤓ Export     │
├──────────────────────────────────────────────────────┤
│  SUMMARY STRIP                                        │
│  Features: 7 │ Events: 202 │ Invocations: 37 │ $16.72│
├──────────────────────────────────────────────────────┤
│  CARD GRID (or SPLIT view)                           │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ login-flow   │  │ auth-refactor│                 │
│  │ [DONE]       │  │ [BUILDING]   │                 │
│  │ ■■■■■■■■░░  │  │ ■■■░░░░░░░  │                 │
│  │ 35ev $3.64  │  │ 23ev $1.92  │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                      │
│  Click card → Feature Modal opens                    │
└──────────────────────────────────────────────────────┘
```

### Feature Modal tabs
| Tab | Content |
|---|---|
| **Timeline** | Vertical event log (type badge, ts, payload preview) |
| **Agents** | Table: stage, conv, agent, model, tokens, cost, result, summary |
| **Artifacts** | Tabs per artifact type (rendered .md content, read-only notebook) |
| **Traces** | Gantt span timeline — spans as horizontal bars |
| **SQL** | Read-only query box, prefilled with useful queries |

---

## Zustand store shape

```typescript
interface AppStore {
  // Project
  projectRoot: string | null
  setProjectRoot: (path: string) => void

  // Features
  features: Feature[]
  activeFeature: string | null
  setActiveFeature: (name: string) => void
  loadFeatures: () => Promise<void>

  // Navigation
  view: 'monitor' | 'notebook' | 'canvas' | 'dbx' | 'settings'
  setView: (v: AppStore['view']) => void

  // Notebook
  notebookFile: NotebookFile | null   // which file is open
  openNotebook: (file: NotebookFile) => void

  // Canvas
  activeFlowId: string
  setActiveFlowId: (id: string) => void

  // Runner (SSE-driven)
  runnerStatus: RunnerStatus | null
  events: RunnerEvent[]
  pushEvent: (e: RunnerEvent) => void

  // Toasts
  toasts: Toast[]
  pushToast: (t: Omit<Toast, 'id'>) => void
  dismissToast: (id: string) => void
}

interface NotebookFile {
  kind: 'skill' | 'agent' | 'artifact'
  id: string                 // skill slug, agent role, or artifact id
  label: string              // display name
  projectRoot: string | null // null = global
  readOnly: boolean          // true for artifacts
}
```

---

## TypeScript API types

```typescript
// GET /api/features
interface Feature {
  project_root: string
  feature: string
  state: string            // BUILDING | REVIEWING | DONE | etc.
  convs_done: number
  convs_total: number
  event_count: number
  agent_done_count: number
  total_tokens: number
  total_cost_usd: number
  last_event_ts: string    // ISO-8601
}

// GET /api/features/<feature>/events
interface FsmEvent {
  seq: number
  feature: string
  type: string             // AGENT_DONE | STATE_TRANSITION | PHASE_START | etc.
  ts: string
  payload: Record<string, unknown>
}

// GET /api/features/<feature>/invocations
interface AgentInvocation {
  id: number
  feature: string
  run_id: string
  stage: string
  conv_id: string
  agent_role: string
  model: string
  input_tokens: number
  output_tokens: number
  tool_uses: number
  cost_usd: number
  wall_seconds: number
  result: string           // PASS | FAIL | BLOCK | ERROR
  summary: string
  trace_id: string | null
  started_at: string
  finished_at: string
}

// GET /api/features/<feature>/metrics
interface FeatureMetrics {
  total_cost_usd: number
  total_tokens: number
  by_stage: Array<{ stage: string; cost_usd: number; tokens: number; count: number }>
  by_run:   Array<{ run_id: string; cost_usd: number; started_at: string }>
  cost_over_time: Array<{ ts: string; cumulative_cost: number }>
}

// GET /api/features/<feature>/artifacts
interface StageArtifact {
  id: number
  stage: string
  artifact_type: string    // REVIEW_FAILURES | USER_STORIES | etc.
  content: string          // full markdown
  file_path: string
  created_at: string
}

// GET /api/flows/<id>
interface Flow {
  id: string
  name: string
  description: string
  rigor: string
  version: number
  nodes: FlowNode[]
  edges: FlowEdge[]
}
interface FlowNode {
  id: number
  name: string
  agent_role: string
  skill_name: string
  adapter: string
  pos_x: number
  pos_y: number
}
interface FlowEdge {
  id: number
  from_node: string
  to_node: string
  condition: string | null
  label: string | null
}

// GET /api/skills
interface SkillDef {
  id: string
  file_name: string
  display_name: string
  category: string
  content: string
  description: string
  compatible_stages: string[]
  project_root: string | null  // null = global
  is_custom: boolean
  version: number
  scope: 'global' | 'local'   // derived from project_root
}

// GET /api/agents
interface AgentDef {
  role: string
  display_name: string
  model: string
  description: string
  instructions: string
  capabilities: string[]
  project_root: string | null
  is_custom: boolean
}

// GET /api/traces/<trace_id>
interface OtelSpan {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  start_time_ns: number
  end_time_ns: number
  status_code: string
  attributes: Record<string, unknown>
}

// SSE event shape (GET /events/runner)
interface SseEvent {
  type: 'RUN_STARTED' | 'TERMINAL_SPAWN' | 'STATUS' | 'AGENT_DONE' | 'RUN_COMPLETE' | 'RUNNER_WARNING'
  topic: string
  run_id?: string
  stage?: string
  adapter?: string
  cost_usd?: number
  status?: string
  tab_id?: string
  argv?: string[]
  summary?: string
}
```

---

## Settings page

| Section | Fields |
|---|---|
| **Adapters** | CLI path for claude / codex / G / antigravity; test button |
| **Cost limits** | Default max_cost_usd per run; currency display |
| **OTel / Traces** | OTLP collector endpoint URL; enable/disable toggle |
| **Appearance** | Accent color picker; density (compact/regular/comfy) |
| **DB & Storage** | Show path to `~/.pathly/pathly.db`; vacuum button; export all data |
| **Export / Import** | Export flows as YAML; import YAML; export skills as .md |

---

## Component file tree (target)

```
studio/src/
  app/
    App.tsx              ← shell: header + sidebar + view router
    store.ts             ← Zustand store
    types.ts             ← all TypeScript interfaces
    api.ts               ← all fetch() wrappers

  views/
    MonitorView.tsx      ← existing, extend
    NotebookView.tsx     ← existing, extend to all file types
    CanvasView.tsx       ← ReactFlow canvas
    DBExplorerView.tsx   ← existing, extend
    SettingsView.tsx     ← new

  components/
    sidebar/
      WorkspaceSidebar.tsx
      NotebookSidebar.tsx
      CanvasSidebar.tsx
      SettingsSidebar.tsx
    notebook/
      Cell.tsx           ← existing Cell component
      CellToolbar.tsx
      ComposedPreview.tsx
    canvas/
      FlowNode.tsx       ← custom ReactFlow node
      FlowEdge.tsx       ← custom ReactFlow edge
      NodePanel.tsx      ← right sidebar for selected node
    dbx/
      FeatureCard.tsx    ← existing
      FeatureModal.tsx   ← existing, add Artifacts + Traces tabs
      SummaryStrip.tsx
    shared/
      Toast.tsx
      Badge.tsx
      MarkdownRenderer.tsx  ← renderMarkdown() utility
```
