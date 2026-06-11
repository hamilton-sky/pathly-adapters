# DESIGN_SPEC — Normalized flow_nodes / flow_edges storage

Status: DESIGN complete — one decision per open question, ready for a builder.
Author: architect
Date: 2026-06-11

Migrate from a YAML blob in `flow_definitions.flow_yaml` to normalized
`flow_nodes` + `flow_edges` SQLite tables as the runtime source of truth,
with YAML demoted to an import/export format.

Grounded in: `fsm_ops.py::_load_flow`, `db/migrations.py`, `db/queries/flow_defs.py`,
`http_server/blueprints/skills.py`, `studio/.../flowToGraph.ts`, `validateFlow.ts`,
`types/index.ts::FlowYaml`, `core/flows/team.flow.yaml`.

---

## The central fact that shapes every decision

The YAML has **two structurally different kinds of keys**:

```
┌─ PER-STATE / PER-EDGE (decomposable into rows) ──────────────────┐
│ states[]          → one node row each                            │
│ transitions{}     → one edge row per (source,target) pair        │
│ agent_map{}       → node.agent       (keyed by state)            │
│ role_map{}        → node.role        (keyed by state)            │
│ adapter_map{}     → node.adapter     (keyed by state) *          │
│ skill_map{}       → node.skill       (keyed by state)            │
│ composition{}     → node.config_json.block (keyed by state)      │
│ transition_rules{}→ node.config_json.rule (keyed by SOURCE state)│
│ transition_actions→ edge.config_json.actions (keyed SRC->TGT)    │
│ gates{}           → edge.config_json.gates   (keyed SRC->TGT)    │
└──────────────────────────────────────────────────────────────────┘

┌─ FLOW-LEVEL SCALARS (no node/edge to attach to) ─────────────────┐
│ version            storage_path        scope_gate                │
│ flow               feedback_routing     adapter_map.default *     │
│ _comments                                                        │
└──────────────────────────────────────────────────────────────────┘
```

`* adapter_map` is split: per-state values land on the node; the mandatory
`adapter_map.default` is flow-level (it is not a state). `feedback_routing` is
keyed by **artifact tag → role**, not by state, so it cannot decompose to a node
or edge — it stays flow-level.

**Conclusion:** `flow_definitions` does NOT fully retire. It keeps a small
flow-level config and remains the parent row (nodes/edges FK to its `id`).
The blob column stays as an export cache / fallback, not the runtime truth.

---

## Q1 — Schema for flow_nodes and flow_edges

**Decision: JSON `config_json` per row for the variable-shape configs; promote
only the high-frequency lookup fields (`agent`, `adapter`) to real columns.**

Rationale: `transition_rules` is a recursive variant union (`on_artifact`,
`on_content` array, `on_state_counter`, `decide` with nested options) — see
`team.flow.yaml` lines 59-87 and the `StateRule` type in `validateFlow.ts`.
Fully decomposing that into rows would mean 4+ child tables and a join-heavy
reassembly on every `next_action`. The FSM reads the whole flow at once, never
queries "all nodes where rule.on_artifact contains X". So relational decomposition
buys nothing and costs a lot. JSON columns are the correct grain here.

Promote `agent` and `adapter` to columns because:
- `agent` is read on every single `build_prompt` (`flow_config["agent_map"][state]`).
- `adapter` drives `preferred_adapter` and the `stage_configs` override merge.
- Both are flat strings, queried by state — cheap to index, and lets the
  `stage_configs` override (`fsm_ops.py` lines 589-604) eventually become a
  surgical column update instead of a dict rebuild.

`role`, `skill`, `composition-block`, and `transition_rule` go inside
`config_json` — they are either rarely read or have irregular shape.

### flow_nodes (additive migration — table already exists)

```sql
flow_nodes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id   INTEGER NOT NULL REFERENCES flow_definitions(id),
    node_id       TEXT NOT NULL,        -- the state name, e.g. "BUILDING"
    node_type     TEXT,                 -- 'state' (only kind today; future: 'note')
    config_json   TEXT,                 -- JSON, see shape below
    -- NEW columns (ALTER TABLE ADD COLUMN, like existing additive migrations):
    agent         TEXT,                 -- agent_map[state],  e.g. "team/build"
    role          TEXT,                 -- role_map[state],   e.g. "builder"
    adapter       TEXT,                 -- adapter_map[state] (per-state only)
    skill         TEXT,                 -- skill_map[state]
    is_terminal   INTEGER DEFAULT 0,    -- transitions[state] == []
    position      INTEGER DEFAULT 0     -- ordering = index in states[]; canvas xy NOT stored here
)
-- UNIQUE(flow_def_id, node_id)
```

`config_json` shape for a node:
```json
{
  "transition_rule": { "on_artifact": {...}, "on_state_counter": {...}, "default": "..." },
  "composition_block": "conv1"        // optional, from composition{}
}
```

### flow_edges (additive migration — table already exists)

```sql
flow_edges (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id   INTEGER NOT NULL REFERENCES flow_definitions(id),
    source_node   TEXT NOT NULL,        -- source state
    target_node   TEXT NOT NULL,        -- target state
    label         TEXT,                 -- derived display label (optional, recomputable)
    -- NEW columns:
    config_json   TEXT,                 -- actions + gates for this SRC->TGT, JSON
    ordinal       INTEGER DEFAULT 0     -- order within source's transition list
)
-- UNIQUE(flow_def_id, source_node, target_node)
```

`config_json` shape for an edge:
```json
{
  "actions": [ {"skill":"update_progress","mark":"conv_done"},
               {"skill":"commit","message":"feat: complete building stage"} ],
  "gates":   [ {"type":"verify_gate","artifact":"VERIFY.md","pass_marker":"RESULT: PASS",
                "on_fail":"VERIFY_FAILURES.md"} ]
}
```

Edges are keyed `(source, target)`. `transition_actions` and `gates` are both
keyed `"SOURCE->TARGET"` in YAML — they map onto the SAME edge row. An edge with
no action/gate just has `config_json = NULL`. A self-loop (`BUILDING->BUILDING`)
is a normal edge row; nothing special needed.

### What stays on flow_definitions (flow-level)

Add ONE column rather than scatter scalars:

```sql
ALTER TABLE flow_definitions ADD COLUMN config_json TEXT;  -- additive migration
```
```json
{
  "version": 1,
  "flow": "team",
  "storage_path": "pathly/plans/{topic}/",
  "feedback_routing": { "REVIEW_FAILURES": "builder", ... },
  "scope_gate": { "exempt_prefixes": [] },
  "adapter_default": "claude",
  "_comments": []
}
```

`flow_yaml` column is **kept** but reclassified: it becomes the export cache /
disaster fallback, no longer the runtime source. `_load_flow` stops parsing it
once nodes exist (see Q2).

### Schema summary diagram

```
flow_definitions (1) ──< flow_nodes (N)
       │  id                  flow_def_id, node_id(state)
       │  config_json         agent, role, adapter, skill, config_json
       │  flow_yaml (cache)
       └──────────< flow_edges (N)
                       flow_def_id, source_node, target_node
                       config_json {actions, gates}
```

---

## Q2 — FSM runtime contract

**Decision: keep the internal `dict` contract intact. Reassemble the exact
YAML-shaped dict from rows. Do NOT make the FSM consume nodes/edges directly.**

I considered rewriting `build_prompt`, `evaluate_transition_rules`, `run_gates`,
`route_feedback`, `build_menu_payload` to walk rows. I'm rejecting that: those
functions touch `flow_config["agent_map"][state]`, `flow_config.get("transitions")`,
`flow_config.get("transition_rules")`, etc. in ~8 call sites across `fsm_ops.py`
and `fsm.py`. Changing the contract turns a storage migration into a logic
rewrite with its own test surface and regression risk — for zero runtime benefit,
because the FSM always materializes the whole flow anyway.

The only change is the body of one function:

```
BEFORE                              AFTER
_load_flow()                        _load_flow()
  read flow_definitions row    ─►     read flow_definitions row  (for config_json + id)
  yaml.safe_load(flow_yaml)            if node rows exist for this flow_def_id:
  return dict                              assemble dict from rows   ← new
                                       else:
                                           yaml.safe_load(flow_yaml)  ← fallback (Q5)
                                       return dict   (same shape either way)
```

Add a pure helper next to it:

```python
def _assemble_flow_dict(conn, flow_def_id, flow_level_config) -> dict:
    """Reconstruct the YAML-equivalent dict from flow_nodes + flow_edges rows.
    Inverse of _decompose_flow_dict (Q3). Round-trip identity is the contract."""
```

Reassembly rules (the inverse mapping):
- `states[]`        ← node rows ordered by `position`
- `transitions{}`   ← group edge rows by `source_node`, ordered by `ordinal`
- `agent_map{}` / `role_map{}` / `adapter_map{}` / `skill_map{}` ← node columns
- `adapter_map["default"]` ← flow_level_config.adapter_default (only emitted if any adapter present)
- `transition_rules{}` ← node.config_json.transition_rule, keyed by node_id
- `transition_actions{}`/`gates{}` ← edge.config_json, keyed `"src->tgt"`
- `feedback_routing` / `scope_gate` / `version` / `flow` / `storage_path` ← flow_level_config

This is the single most important property to test: `_assemble(_decompose(yaml)) == yaml`
for every file in `core/flows/`. One parametrized round-trip test guards the
entire migration.

---

## Q3 — Where YAML→nodes/edges decomposition happens

**Decision: eager, at import time, inside the existing `upsert_flow_definition`
write path. NOT lazy-on-first-Studio-open.**

`_refresh_flows()` (in `flow_defs.py`) already runs on every server start and
upserts each `.flow.yaml`. The decomposition rides that same write. Concretely:

```
upsert_flow_definition(conn, name, version, flow_yaml, file_path)
    1. parse yaml.safe_load(flow_yaml)              ← new
    2. split flow-level config vs per-state/edge    ← new (_decompose_flow_dict)
    3. INSERT OR REPLACE flow_definitions
         (flow_yaml cache + config_json + return id)
    4. DELETE flow_nodes WHERE flow_def_id=?         ← new (replace-all)
    5. DELETE flow_edges WHERE flow_def_id=?         ← new
    6. bulk INSERT nodes, bulk INSERT edges          ← new
   ALL inside one _get_write_lock(conn) + one commit (atomic)
```

Why eager, not lazy:
- `_load_flow` must find rows the moment the FSM asks — a feature could start
  via CLI (`pathly-fsm-call`) without Studio ever opening the flow. Lazy-on-open
  would leave the runtime path reading the blob indefinitely for CLI-only users.
- It keeps "rows are the truth" honest from second one. Lazy creates a window
  where blob and rows disagree.
- `_refresh_flows` runs on startup anyway; the marginal cost (parse + ~8 inserts
  per flow, 5 flows) is microseconds and already inside the init path.

Decomposition is the natural counterpart of `upsert_flow_definition` because that
is the ONE chokepoint every YAML-in path already funnels through: startup refresh,
`create_flow`, and `update_flow` all call it. Put the logic there and every writer
gets it free.

```
   .flow.yaml on disk ─┐
   create_flow ─────────┼──► upsert_flow_definition ──► decompose ──► rows
   PUT /flows (YAML) ───┘         (single chokepoint)
```

Edge case — malformed YAML: if `yaml.safe_load` raises, skip decomposition,
still store the blob, log a warning. `_load_flow` then falls back to blob parse
(Q5). One bad flow never blocks the others (mirrors the existing per-file
`try/except` in `_refresh_flows`).

---

## Q4 — Studio API shape

**Decision: add a coarse `PUT /flows/<name>/graph` that replaces all
nodes+edges+flow-config in one atomic call. Do NOT build per-node/per-edge REST
(`POST /nodes`, `DELETE /edges/e1`).**

This is the highest-leverage decision and the one I feel strongest about.

The visual editor already holds the **entire** `FlowYaml` object in React state
(`useFlowFile.ts` → `flowData`) and mutates it in memory (`useFlowMutations.ts`).
A drag, a new transition, a renamed state — all mutate that one in-memory object.
Today "save" serializes the whole object to YAML and PUTs it. There is no concept
of an incremental server call, and the editor doesn't need one.

Granular REST would force the frontend to be rewritten to emit a diff stream
(track which node changed, sequence INSERT/DELETE/UPDATE, handle partial-failure
rollback across N requests). That is a large frontend change for a problem the
editor doesn't have. The prompt's own framing — "the visual editor already works
well and just needs to persist to DB instead of to a YAML blob" — points straight
at replace-all.

```
┌──────────── Studio FlowEditor ────────────┐
│ flowData: FlowYaml  (whole object in RAM)  │
│   drag state    → mutate flowData          │
│   draw edge     → mutate flowData          │
│   rename/delete → mutate flowData          │
└───────────────────┬────────────────────────┘
                     │ Save  (send whole graph as JSON)
                     ▼
   PUT /flows/<name>/graph   { graph: <FlowYaml-as-JSON> }
                     │
                     ▼
   server: _decompose_flow_dict(graph) ─► replace-all rows (atomic)
           + re-serialize graph to flow_yaml cache + write .flow.yaml to disk
```

### New endpoint contract

```
PUT /flows/<name>/graph
  body: { "graph": { ...FlowYaml shape (states, transitions, agent_map, ...) } }
  effect (one write-lock, one commit):
    - upsert flow_definitions (config_json + flow_yaml cache from re-dumped graph)
    - replace-all flow_nodes / flow_edges for this flow_def_id
    - write-through .flow.yaml to disk (file_path), same as today
  returns: { ok: true }
```

The server already owns YAML serialization knowledge; the editor sends structured
JSON (no client-side `js-yaml.dump`), the server re-dumps to keep the disk file
and blob cache as faithful exports. This also removes the frontend's dependency on
matching the Python serializer's formatting.

Keep the existing `GET /flows/<name>` working, and extend it:
```
GET /flows/<name>           → { flow_yaml, name, file_path, ... }   (unchanged)
GET /flows/<name>/graph     → { graph: <FlowYaml JSON assembled from rows> }  (new)
```
`/graph` reassembles from rows via the same `_assemble_flow_dict` the FSM uses —
so Studio and the FSM read identical truth. The editor migrates from
`fetchFlow` + client-side parse to `fetchFlowGraph` (already-parsed JSON),
deleting the `js-yaml.loadAll` path in `useFlowFile.ts`.

Keep `PUT /flows/<name>` (YAML body) alive for the raw YAML tab and external
callers — it routes through the same `upsert_flow_definition`, so it decomposes
to rows too. Both write paths converge on one chokepoint.

---

## Q5 — Migration path (phasing, no FSM breakage)

**Decision: rows-first-with-blob-fallback, gated by "do node rows exist".
Four phases, each independently shippable. The blob column never gets dropped in
this migration.**

The safety mechanism is a single runtime branch in `_load_flow`:

```python
node_rows = read_flow_nodes(conn, flow_def_id)
if node_rows:
    return _assemble_flow_dict(conn, flow_def_id, flow_level_config)  # rows = truth
return yaml.safe_load(row["flow_yaml"])                              # fallback
```

If decomposition has run (it runs on every startup once Phase 1 ships), rows
exist and win. If anything goes wrong — bad parse, partial write, an old DB from
before the migration — rows are absent and the FSM reads the blob exactly as it
does today. **There is no flag day.** The running FSM cannot break because the
old path is still physically present and is the automatic fallback.

```
Phase 0  (today)        flow_yaml blob is truth. nodes/edges empty.

Phase 1  WRITE side      Add columns (additive ALTERs). Teach
 (ship alone)            upsert_flow_definition to decompose → rows.
                         _load_flow STILL reads blob. Rows now populated but
                         unused. Ship + verify rows match blob in DB explorer.
                         Add the round-trip test (Q2). Zero runtime behavior change.

Phase 2  READ side       Flip _load_flow to "rows if present, else blob".
 (ship alone)            Now rows are truth at runtime. Blob is fallback.
                         Full pipeline regression run on team.flow before merge.

Phase 3  STUDIO          Add GET/PUT /flows/<name>/graph. Point the visual editor
 (ship alone)            at /graph (structured JSON, server-side serialize).
                         YAML tab + PUT /flows (YAML) stay as import/export.

Phase 4  (optional,      Once stable in production, the blob is pure export cache.
 not in this migration)  Could stop write-through to flow_yaml, but recommend
                         KEEPING it: it is the human-diffable git artifact and the
                         fallback. Do not drop the column.
```

Why blob stays permanently:
- It is the export format — `useFlowExport.ts` and the `.flow.yaml` on-disk files
  in `core/flows/` are how flows are shared and version-controlled. The git diff
  on `team.flow.yaml` is the review surface.
- It is the zero-cost disaster fallback. Dropping it trades a few KB of text for
  the loss of the one path that makes the migration unbreakable.

Ordering rule (record in MEMORY-style note): **Phase 1 (write) must land and be
verified before Phase 2 (read flip).** Never flip the read path in the same ship
as introducing the write path — that removes the ability to diff rows-vs-blob in
production before trusting rows.

---

## New / changed surfaces (builder checklist)

```
db/migrations.py            +5 ALTER COLUMN (additive, idempotent):
                              flow_nodes.agent/role/adapter/skill/is_terminal/position
                              flow_edges.config_json/ordinal
                              flow_definitions.config_json
                            +2 UNIQUE indexes (flow_def_id,node_id) /
                              (flow_def_id,source,target)

db/queries/flow_defs.py     _decompose_flow_dict(dict) -> (flow_cfg, nodes[], edges[])
                            _assemble_flow_dict(conn, flow_def_id, flow_cfg) -> dict
                            read_flow_nodes / read_flow_edges
                            replace_flow_graph(conn, flow_def_id, nodes, edges)  (atomic)
                            upsert_flow_definition: call decompose + replace_flow_graph

fsm_ops.py::_load_flow      branch: rows-if-present else blob. No other FSM change.

http_server/blueprints/     GET  /flows/<name>/graph   (assemble from rows)
  skills.py                 PUT  /flows/<name>/graph   (decompose + replace-all + disk)

studio/.../useFlowFile.ts   fetch /graph (JSON) instead of /flows + js-yaml parse;
                            save via PUT /graph (send object, no client dump).
                            YAML tab keeps existing PUT /flows path.

tests                       parametrized round-trip: _assemble(_decompose(load(f))) == load(f)
                              for every core/flows/*.flow.yaml
                            decompose idempotency: re-upsert same YAML twice → identical rows
```

## Risks / watch-items

1. **Round-trip fidelity is the whole ballgame.** `transition_rules` variants
   (`on_content` is an *ordered array*, `on_state_counter`, nested `decide.options`)
   must survive JSON round-trip with order preserved. The test in Q2 is mandatory,
   not optional. Use `json.dumps`/`yaml.dump` with key order from the source.
2. **`adapter_map.default` placement.** It is flow-level, not a node. Assembly must
   only emit `adapter_map` at all if there is at least one adapter value, or the
   `state.py` validator (requires `default` when `adapter_map` present) will reject
   a flow that previously had no adapter_map. Guard the emission.
3. **`stage_configs` override.** `fsm_ops.py` 589-604 patches the assembled dict
   after load. Because the dict shape is unchanged (Q2), this code needs no change.
   Confirm it still operates on the assembled dict, not on rows.
4. **`flow_def_id` scoping.** `read_flow_by_name` has a NULL-project-root fallback.
   Node/edge reads MUST use the resolved `flow_def_id`, never re-resolve by name,
   to avoid attaching to the wrong project's flow.
