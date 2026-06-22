# TaskGraph — Design Specification

> Status: design complete, not yet implemented  
> Depends on: Phase 14 (DAG infrastructure) — already shipped  
> Target: Studio `CommandCenter` / `CommsPanel`

---

## Goal

Make the dependency structure of a feature's implementation visible in real time.

When the planner seeds the comms board (plan.md Step 6), it posts one `type="task"` message per implementation phase with `depends_on` referencing prerequisite phase IDs. The TaskGraph reads those messages and renders a live DAG — nodes are phases, edges are dependencies, fill colour is current execution status.

The graph updates automatically as the builder marks tasks complete via `POST /comms/tasks/complete`. No manual refresh. No separate data pipeline. The comms board IS the task store.

---

## Scope levels

The board already has three tiers. The TaskGraph follows the active tier — one component, three views.

| Board tier | Scope field | Graph shows | Posted by |
|---|---|---|---|
| `feature` | feature name (e.g. `comms-board`) | Implementation phases (Phase 1 … N) | planner at end of planning |
| `project` | project root path | Cross-feature milestones (e.g. "complete auth", "start dashboard") | planner during cross-feature planning pass |
| `global` | `"global"` | Not used yet; reserved | — |

Debug flow is a future addition: the debug skill would post 4 tasks (`reproduce → isolate → fix → verify`) to the feature board at session start with `assigned_to_stage="DEBUGGING"`. These appear alongside build tasks in the feature-tier graph, giving a unified view of what's happening to that feature across flows. Explorer flow is deliberately excluded — explorations are open-ended discovery, not executable deliverables.

---

## Data model

Everything the graph needs is already in `comms_messages`:

```
message_id    → graph node ID
text          → node label (e.g. "Phase 3: Semantic Embeddings — sqlite-vec + embed_async")
task_status   → node state: "pending" | "in_progress" | "done"
depends_on    → JSON array of message_id strings → directed edges
board + scope → filter to the current board panel scope
```

The REST surface is already live:

```
GET  /comms/tasks?feature=<f>&ready=true   → unblocked tasks (builder polls this)
GET  /comms/tasks?feature=<f>              → all tasks for the scope (graph reads this)
POST /comms/tasks/complete                 → marks done, returns newly-unblocked IDs
```

The graph queries `GET /comms/tasks?feature=<scope>` on mount and on every `COMMS_UPDATE` SSE event. No polling needed — the SSE stream is already wired in `commsStore`.

---

## UI placement — Option A (chosen)

The TaskGraph lives as a second tab inside the `CommsPanel`, alongside the existing message list.

```
┌─ CommandCenter panel ────────────────────────────────────────┐
│  Feature ▸  Project  ▸  Global      scope: comms-board   ▾  │  ← board header (existing)
├──────────────────────────────────────────────────────────────┤
│  Messages (7)  │  Tasks (6)                                  │  ← NEW tab bar
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   [Phase 1 DB Schema ✓] ──► [Phase 2 HTTP Routes ✓] ──►    │
│                         └──► [Phase 3 Embeddings ✓]  ──►   │
│                                                   ──►        │
│                              [Phase 4 Write Perms ⬤] ──►   │
│                              [Phase 5 Hybrid ●]    ──►      │
│                                                   ──►        │
│                                          [Phase 6 DAG ⊘]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Why Option A over a separate panel:
- The scope selector is shared — switching from Feature to Project tier updates both tabs simultaneously, with no risk of the two panels drifting out of sync.
- The graph is supplementary context, not a primary control surface. It doesn't need its own real estate.
- Zero new navigation: users already know the comms board header controls what they're looking at.

---

## Node states

| State | Condition | Border colour | Fill |
|---|---|---|---|
| `done` | `task_status = "done"` | `#3a7a4a` (green) | `#141e14` |
| `active` | `task_status = "in_progress"` | `#7c6cf0` (purple) | `#1a1a28` |
| `ready` | `task_status = "pending"` AND all deps are `done` | `#5a7ac0` (blue) | `#1a1e2a` |
| `blocked` | `task_status = "pending"` AND any dep is not `done` | `#3a3030` (dark red) | `#1a1414` |

Edge style:
- Solid line when the source node is `done`
- Dashed line when the source node is `active` or `ready`
- Very faint when source is `blocked`

---

## Implementation plan

### What's already in place

- `depends_on` column on `comms_messages` (Phase 14 migration) ✓
- `GET /comms/tasks` endpoint ✓
- `POST /comms/tasks/complete` endpoint ✓
- `COMMS_UPDATE` SSE broadcast on task state change ✓
- `commsStore` already subscribes to the SSE stream ✓
- `reactflow` v11 + `dagre` v3 in `studio/package.json` ✓
- planner seeds task messages at end of planning (plan.md Step 6) ✓
- HTML mockup showing the visual target: `.mock-comms-board/task-graph-mockup.html` ✓

### Files to create / modify

```
studio/src/renderer/src/components/HQ/CommsPanel/
  TaskGraph/
    TaskGraph.tsx          ← ReactFlow canvas; fetches tasks, lays out with dagre
    TaskGraph.module.css   ← node styles, edge colours
    useTaskGraph.ts        ← data hook: GET /comms/tasks, dagre layout, SSE subscription
```

```
studio/src/renderer/src/components/HQ/CommsPanel/
  CommsPanel.tsx           ← add tab bar (Messages | Tasks); render <TaskGraph> when active
```

### `useTaskGraph.ts` sketch

```typescript
// Fetches tasks for the current board scope, computes dagre layout,
// subscribes to COMMS_UPDATE to re-layout on task completion.
export function useTaskGraph(scope: BoardScope) {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])

  useEffect(() => {
    fetchTasks(scope).then(tasks => {
      const { nodes, edges } = buildDagreLayout(tasks)
      setNodes(nodes)
      setEdges(edges)
    })
  }, [scope])

  // Re-fetch when any task completes (SSE COMMS_UPDATE already fires)
  useCommsSSE(() => fetchTasks(scope).then(...), scope)

  return { nodes, edges }
}
```

`buildDagreLayout(tasks)`:
1. Create a `dagre.graphlib.Graph` with `rankdir: 'LR'` (left → right)
2. Add each task as a node (width 160, height 60)
3. Parse `depends_on` JSON and add edges
4. Call `dagre.layout(g)` to get x/y positions
5. Map to ReactFlow `Node[]` and `Edge[]` with className based on `task_status` + dep analysis

### `TaskGraph.tsx` sketch

```tsx
export function TaskGraph({ scope }: { scope: BoardScope }) {
  const { nodes, edges } = useTaskGraph(scope)

  if (!nodes.length) return (
    <div className={s.empty}>No tasks seeded yet — run /pathly plan to populate.</div>
  )

  return (
    <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false}>
      <Background color="#1a1a1e" gap={20} />
      <MiniMap nodeColor={n => STATUS_COLORS[n.data.status]} />
    </ReactFlow>
  )
}
```

### `CommsPanel.tsx` change

Add a `tab: 'messages' | 'tasks'` local state. Render:

```tsx
<div className={s.tabBar}>
  <button onClick={() => setTab('messages')} className={tab === 'messages' ? s.active : ''}>
    Messages <span className={s.badge}>{messages.length}</span>
  </button>
  <button onClick={() => setTab('tasks')} className={tab === 'tasks' ? s.active : ''}>
    Tasks <span className={s.badge}>{taskCount}</span>
  </button>
</div>

{tab === 'messages' && <CommsMsgList ... />}
{tab === 'tasks'    && <TaskGraph scope={scope} />}
```

`taskCount` comes from a `GET /comms/tasks?feature=<scope>` count — can be cached in `commsStore`.

---

## What this unlocks later

- **Studio progress bar** — derive % complete from `done / total` task count per feature
- **Project board DAG** — same component, different scope: shows which features depend on which, coloured by feature FSM state
- **Debug DAG** — debug skill posts 4 tasks at session start; they appear inline in the feature graph alongside build tasks
- **Blocked-task highlighting** — when a builder marks a task blocked (not yet implemented), the graph highlights the cascade of downstream tasks that will be delayed

---

## Build estimate

| Work | Effort |
|---|---|
| `useTaskGraph.ts` (fetch + dagre layout) | ~2h |
| `TaskGraph.tsx` (ReactFlow canvas + node styles) | ~2h |
| `CommsPanel.tsx` (tab bar + conditional render) | ~30m |
| CSS (node colours, edge dash styles, empty state) | ~30m |
| **Total** | **~5h / 1 builder conversation** |
