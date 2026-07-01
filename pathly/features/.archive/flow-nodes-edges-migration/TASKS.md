# TASKS — flow-nodes-edges-migration

Source: DESIGN_SPEC.md (architect, 2026-06-11)
Status: Builder-ready

---

## Phase 1 — WRITE SIDE
Schema additions + decomposition logic. FSM still reads the blob.
The FSM behavior is unchanged at the end of this phase. Safe to ship alone.

---

### T1.1 — Add additive column migrations for flow_nodes, flow_edges, flow_definitions

**File:** `src/pathly_orchestrator/db/migrations.py`

**What to do:**
Extend `_add_additive_migrations` with nine new `(table, col, ctype)` entries:

```
("flow_nodes",       "agent",       "TEXT"),
("flow_nodes",       "role",        "TEXT"),
("flow_nodes",       "adapter",     "TEXT"),
("flow_nodes",       "skill",       "TEXT"),
("flow_nodes",       "is_terminal", "INTEGER DEFAULT 0"),
("flow_nodes",       "position",    "INTEGER DEFAULT 0"),
("flow_edges",       "config_json", "TEXT"),
("flow_edges",       "ordinal",     "INTEGER DEFAULT 0"),
("flow_definitions", "config_json", "TEXT"),
```

All entries use the existing `try/except sqlite3.OperationalError: pass` pattern — idempotent on re-run.

**Also add** two UNIQUE indexes in the `_run_migrations` executescript block (inside the
`CREATE TABLE IF NOT EXISTS` section, after the existing flow index definitions):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_nodes_def_node
    ON flow_nodes(flow_def_id, node_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_edges_def_src_tgt
    ON flow_edges(flow_def_id, source_node, target_node);
```

**Acceptance criteria:**
- `python -c "from pathly_orchestrator.db.migrations import _run_migrations; import sqlite3; c=sqlite3.connect(':memory:'); _run_migrations(c); cols=[r[1] for r in c.execute('PRAGMA table_info(flow_nodes)')]; assert 'agent' in cols and 'is_terminal' in cols and 'position' in cols"` exits 0.
- Same check for `flow_edges` columns `config_json` and `ordinal`.
- Same check for `flow_definitions` column `config_json`.
- Running `_run_migrations` twice on the same in-memory DB raises no exception (idempotency).

---

### T1.2 — Write `_decompose_flow_dict`

**File:** `src/pathly_orchestrator/db/queries/flow_defs.py`

**What to do:**
Add a pure function (no DB I/O):

```python
def _decompose_flow_dict(flow_dict: dict) -> tuple[dict, list[dict], list[dict]]:
    """Split a parsed YAML flow dict into (flow_level_config, node_rows, edge_rows).

    Returns:
        flow_level_config  — dict with keys: version, flow, storage_path,
                             feedback_routing, scope_gate, adapter_default, _comments
        node_rows          — list of dicts with keys: node_id, node_type, agent, role,
                             adapter, skill, is_terminal, position, config_json (JSON str or None)
        edge_rows          — list of dicts with keys: source_node, target_node, ordinal,
                             config_json (JSON str or None)
    """
```

Mapping rules (all drawn from DESIGN_SPEC Q1 and Q2):

**flow_level_config:**
- `version`, `flow`, `storage_path`, `feedback_routing`, `scope_gate`, `_comments`
  copied verbatim from flow_dict (use `.get()` for optional keys).
- `adapter_default`: `flow_dict.get("adapter_map", {}).get("default")` — may be None.

**node_rows** — iterate `flow_dict["states"]` in order (index = position):
- `node_id`: state name string.
- `node_type`: `"state"`.
- `position`: index in the states list.
- `agent`: `flow_dict.get("agent_map", {}).get(state)`.
- `role`: `flow_dict.get("role_map", {}).get(state)`.
- `adapter`: per-state only — `flow_dict.get("adapter_map", {}).get(state)` where state != "default".
- `skill`: `flow_dict.get("skill_map", {}).get(state)`.
- `is_terminal`: `1` if `flow_dict.get("transitions", {}).get(state) == []` else `0`.
  Note: a missing transitions key for a state is treated as non-terminal (not `[]`).
- `config_json`: serialize a dict containing:
  - `"transition_rule"`: `flow_dict.get("transition_rules", {}).get(state)` — omit key if None.
  - `"composition_block"`: `flow_dict.get("composition", {}).get(state)` — omit key if None.
  If both keys would be omitted, store `None` (NULL) rather than `"{}"`.

**edge_rows** — iterate `flow_dict.get("transitions", {})` by source state, preserving
the order of states (outer loop = states list order) and target order (inner loop):
- `source_node`: source state name.
- `target_node`: target state name.
- `ordinal`: index within the source's transition list.
- `config_json`: build a dict containing:
  - `"actions"`: `flow_dict.get("transition_actions", {}).get(f"{src}->{tgt}")` — omit if None.
  - `"gates"`: `flow_dict.get("gates", {}).get(f"{src}->{tgt}")` — omit if None.
  If both would be omitted, store `None`.

`config_json` values must be produced with `json.dumps(..., ensure_ascii=False)`.

**Acceptance criteria:**
- `_decompose_flow_dict` is importable from `pathly_orchestrator.db.queries.flow_defs`.
- Called on the parsed `team.flow.yaml` dict it returns exactly 8 node_rows and the
  correct number of edge_rows (count the non-empty transitions in the file).
- The PLANNING node_row has `config_json` containing `"transition_rule"` with the
  `on_content` array present and ordered (verify with `json.loads`).
- The BUILDING->REVIEWING edge_row has `config_json` containing both `"actions"` and
  `"gates"` keys.
- A flow with no `adapter_map` returns `flow_level_config["adapter_default"] == None`.
- A state whose transitions list is `[]` has `is_terminal == 1`.
- A state whose transitions list is non-empty has `is_terminal == 0`.

---

### T1.3 — Write `replace_flow_graph`, `read_flow_nodes`, `read_flow_edges`

**File:** `src/pathly_orchestrator/db/queries/flow_defs.py`

**What to do:**
Add three functions.

```python
def read_flow_nodes(conn: sqlite3.Connection, flow_def_id: int) -> list[dict]:
    """Return all node rows for a flow, ordered by position."""

def read_flow_edges(conn: sqlite3.Connection, flow_def_id: int) -> list[dict]:
    """Return all edge rows for a flow, ordered by source_node, ordinal."""

def replace_flow_graph(
    conn: sqlite3.Connection,
    flow_def_id: int,
    flow_level_config: dict,
    node_rows: list[dict],
    edge_rows: list[dict],
) -> None:
    """Atomically replace all nodes+edges for a flow and update flow_definitions.config_json.
    Runs inside a single _get_write_lock + one commit.
    """
```

`replace_flow_graph` must:
1. Delete all existing `flow_nodes` rows WHERE `flow_def_id = ?`.
2. Delete all existing `flow_edges` rows WHERE `flow_def_id = ?`.
3. Bulk INSERT node_rows (one `executemany`), setting `flow_def_id` on each row.
4. Bulk INSERT edge_rows (one `executemany`), setting `flow_def_id` on each row.
5. UPDATE `flow_definitions SET config_json = ? WHERE id = ?` with
   `json.dumps(flow_level_config, ensure_ascii=False)`.

All five operations run inside a single `with _get_write_lock(conn):` block, committed once.

**Acceptance criteria:**
- After calling `replace_flow_graph` on an in-memory DB, `read_flow_nodes` returns
  the same rows (node_id, agent, position) that were passed in, in position order.
- After calling `replace_flow_graph` twice with the same inputs, row counts are
  identical to a single call (idempotency: delete-then-insert, no duplicates).
- `read_flow_edges` returns rows ordered so that self-loop edges (BUILDING->BUILDING)
  come in the correct ordinal position within their source group.

---

### T1.4 — Integrate decomposition into `upsert_flow_definition`

**File:** `src/pathly_orchestrator/db/queries/flow_defs.py`

**What to do:**
Modify `upsert_flow_definition` to call `_decompose_flow_dict` and `replace_flow_graph`
after the existing INSERT OR REPLACE. Keep the existing INSERT OR REPLACE intact — it
still stores `flow_yaml` as the cache. The decomposition is additive.

New call sequence inside `with _get_write_lock(conn):`:
1. Parse `yaml.safe_load(flow_yaml)` — call this `flow_dict`.
2. Call `flow_level_cfg, nodes, edges = _decompose_flow_dict(flow_dict)`.
3. Execute the existing `INSERT OR REPLACE INTO flow_definitions`.
4. Obtain `flow_def_id` from `cur.lastrowid`.
5. Call `replace_flow_graph(conn, flow_def_id, flow_level_cfg, nodes, edges)`.
6. Single `conn.commit()` (replace_flow_graph must NOT commit internally — refactor
   replace_flow_graph to accept an optional `commit=True` parameter, default True,
   and pass `commit=False` when called from within the upsert write lock).

**Error handling:** wrap the decompose+replace block in a `try/except Exception`:
- On exception: log a `WARNING` with `logging.getLogger(__name__).warning(...)` and
  continue — the blob is still stored and `_load_flow` will fall back to it.
- Never allow a decomposition failure to prevent the blob from being written.

`yaml` must be imported at the top of `flow_defs.py` (add `import yaml`).
Add `import json` and `import logging` if not already present.

**Acceptance criteria:**
- After a fresh server start, each of the 5 bundled flows has node rows in the DB:
  `SELECT COUNT(*) FROM flow_nodes WHERE flow_def_id = (SELECT id FROM flow_definitions WHERE name='team')` returns 8.
- `flow_definitions.config_json` for the `team` flow is valid JSON containing `"flow": "team"`.
- A malformed YAML string passed to `upsert_flow_definition` does NOT raise — it
  stores the raw blob and logs a warning (test with `pytest -k "upsert"` or a small
  inline test).
- The existing `upsert_flow_definition` return type (int) is unchanged.

---

### T1.5 — Synthetic test fixtures for `decide`, `on_content`, `on_state_counter` branches

**File:** `tests/test_flow_decompose.py` (new file)

**What to do:**
Create a standalone pytest file. Do not rely on any bundled `.flow.yaml` for these
branches — none of the 5 bundled flows use `decide` or `on_state_counter` in
`transition_rules`.

Define three fixture dicts as module-level constants:

**FIXTURE_DECIDE** — a minimal flow where one state has a `decide` transition rule:
```python
FIXTURE_DECIDE = {
    "version": 1, "flow": "decide-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["CHOOSING", "PATH_A", "PATH_B"],
    "transitions": {"CHOOSING": ["PATH_A", "PATH_B"], "PATH_A": [], "PATH_B": []},
    "agent_map": {"CHOOSING": "team/decide", "PATH_A": "team/build", "PATH_B": "team/review"},
    "feedback_routing": {},
    "transition_rules": {
        "CHOOSING": {
            "decide": {
                "context_file": "CONTEXT.md",
                "question": "Which path?",
                "options": {"a": "PATH_A", "b": "PATH_B"},
                "default": "a",
            }
        }
    },
    "transition_actions": {},
}
```

**FIXTURE_ON_CONTENT** — a flow with an `on_content` array rule (two content checks, order matters):
```python
FIXTURE_ON_CONTENT = {
    "version": 1, "flow": "content-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["DRAFTING", "REVIEWING", "DONE"],
    "transitions": {"DRAFTING": ["REVIEWING", "DRAFTING"], "REVIEWING": ["DONE"], "DONE": []},
    "agent_map": {"DRAFTING": "team/build", "REVIEWING": "team/review", "DONE": "team/retro"},
    "feedback_routing": {},
    "transition_rules": {
        "DRAFTING": {
            "on_content": [
                {"file": "PLAN.md", "contains": "## Conversation", "next": "REVIEWING"},
                {"file": "PLAN.md", "contains": "## Summary", "next": "REVIEWING"},
            ],
            "default": "DRAFTING",
        }
    },
    "transition_actions": {},
}
```

**FIXTURE_ON_STATE_COUNTER** — a flow with `on_state_counter` rule:
```python
FIXTURE_ON_STATE_COUNTER = {
    "version": 1, "flow": "counter-test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["BUILDING", "REVIEWING", "DONE"],
    "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": ["BUILDING", "DONE"], "DONE": []},
    "agent_map": {"BUILDING": "team/build", "REVIEWING": "team/review", "DONE": "team/retro"},
    "feedback_routing": {},
    "transition_rules": {
        "REVIEWING": {
            "on_state_counter": {"field": "convs_done", "op": "lt", "compare_to": "convs_total", "next": "BUILDING"},
            "default": "DONE",
        }
    },
    "transition_actions": {},
}
```

Tests to include:
- For each fixture: `_decompose_flow_dict` completes without raising.
- `decide` rule lands in `config_json["transition_rule"]["decide"]` for the CHOOSING node.
- `on_content` array is preserved in order (check index 0 and 1 `contains` values).
- `on_state_counter` dict is present under `config_json["transition_rule"]["on_state_counter"]`.
- No `decide`, `on_content`, or `on_state_counter` key appears in any edge_row.

**Acceptance criteria:**
- `python -m pytest tests/test_flow_decompose.py -v` exits 0 with all tests green.
- No test reads from disk or touches a DB connection.

---

### T1.6 — Round-trip test: `_assemble(_decompose(load(f))) == load(f)` for all 5 bundled flows

**File:** `tests/test_flow_decompose.py` (same file as T1.5, add to it)

**What to do:**
This test is the Phase 1/Phase 2 gate. It MUST be green before Phase 2 begins.

Add `_assemble_flow_dict` as a stub-or-real function at this stage (see Phase 2 T2.1 for
the full implementation). For the round-trip test to be runnable in Phase 1, write a
minimal version of `_assemble_flow_dict` in `flow_defs.py` that takes the decomposition
output (not DB rows) and reconstructs the dict. This is the pure inverse — it does not
query the DB in Phase 1, it operates on the in-memory node/edge lists directly.

```python
def _assemble_from_parts(
    flow_level_config: dict,
    node_rows: list[dict],
    edge_rows: list[dict],
) -> dict:
    """Pure inverse of _decompose_flow_dict. Uses in-memory row lists.
    Used by the round-trip test in Phase 1 and promoted to DB-backed in Phase 2."""
```

Reassembly rules (from DESIGN_SPEC Q2, inverse mapping):
- `states`: `[r["node_id"] for r in sorted(node_rows, key=lambda r: r["position"])]`
- `transitions`: group edge_rows by source_node (ordered by ordinal), emit `{src: [tgt, ...]}`;
  terminal nodes (is_terminal==1 AND no outgoing edges) get `{state: []}`.
  States with no outgoing edges at all MUST still appear in transitions as `{state: []}`.
- `agent_map`: `{r["node_id"]: r["agent"] for r in node_rows if r.get("agent")}` — omit entire
  key if empty.
- `role_map`: same pattern for `role`.
- `skill_map`: same pattern for `skill`.
- `adapter_map`: start with per-state entries `{r["node_id"]: r["adapter"] ...}` for rows
  where `r.get("adapter")` is not None. If `flow_level_config.get("adapter_default")` is
  not None, add `{"default": flow_level_config["adapter_default"]}`. Omit entire key if
  the resulting dict would be empty. (This guards the validator rule: never emit
  `adapter_map` without `default`.)
- `composition`: `{r["node_id"]: cfg["composition_block"] for r in node_rows if (cfg := json.loads(r["config_json"] or "{}")).get("composition_block")}` — omit if empty.
- `transition_rules`: `{r["node_id"]: cfg["transition_rule"] for r in node_rows if (cfg := json.loads(r["config_json"] or "{}")).get("transition_rule")}` — omit if empty.
- `transition_actions`: build from edge_rows where `cfg.get("actions")` is set —
  key is `f"{r['source_node']}->{r['target_node']}"`. Omit if empty.
- `gates`: build from edge_rows where `cfg.get("gates")` is set. Omit if empty.
- `feedback_routing`, `scope_gate`, `version`, `flow`, `storage_path`, `_comments`:
  copy from `flow_level_config` — omit keys whose value is None or an empty structure
  only if the original flow did not have them (safest: always emit if present in
  flow_level_config, skip if value is None).

Add a parametrized pytest:

```python
import yaml
from importlib.resources import files
import pytest
from pathly_orchestrator.db.queries.flow_defs import _decompose_flow_dict, _assemble_from_parts

BUNDLED_FLOWS = ["team", "debug", "explore", "test", "quick-fix"]

@pytest.mark.parametrize("flow_name", BUNDLED_FLOWS)
def test_round_trip(flow_name):
    text = files("pathly_data").joinpath(f"core/flows/{flow_name}.flow.yaml").read_text(encoding="utf-8")
    original = yaml.safe_load(text)
    flow_cfg, nodes, edges = _decompose_flow_dict(original)
    reconstructed = _assemble_from_parts(flow_cfg, nodes, edges)
    assert reconstructed == original, (
        f"Round-trip failed for {flow_name}. "
        f"Keys in original not in reconstructed: {set(original) - set(reconstructed)}. "
        f"Keys in reconstructed not in original: {set(reconstructed) - set(original)}."
    )
```

**Acceptance criteria (this is the Phase 2 gate):**
- `python -m pytest tests/test_flow_decompose.py::test_round_trip -v` exits 0, all 5
  parametrize cases green.
- If ANY case fails, Phase 2 MUST NOT begin. Fix `_decompose_flow_dict` or
  `_assemble_from_parts` until all 5 pass.

---

### T1.7 — Decompose idempotency test

**File:** `tests/test_flow_decompose.py` (same file)

**What to do:**
Add a test that calls `upsert_flow_definition` twice with identical YAML and asserts
that the resulting row counts and content are unchanged after the second call.

```python
def test_upsert_idempotency(tmp_path):
    import sqlite3, yaml
    from importlib.resources import files
    from pathly_orchestrator.db.migrations import _run_migrations
    from pathly_orchestrator.db.queries.flow_defs import (
        upsert_flow_definition, read_flow_nodes, read_flow_edges,
    )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _run_migrations(conn)
    text = files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text(encoding="utf-8")
    fid = upsert_flow_definition(conn, None, "team", "", text)
    nodes_1 = read_flow_nodes(conn, fid)
    edges_1 = read_flow_edges(conn, fid)
    upsert_flow_definition(conn, None, "team", "", text)
    nodes_2 = read_flow_nodes(conn, fid)
    edges_2 = read_flow_edges(conn, fid)
    assert len(nodes_1) == len(nodes_2)
    assert len(edges_1) == len(edges_2)
    assert [r["node_id"] for r in nodes_1] == [r["node_id"] for r in nodes_2]
```

**Acceptance criteria:**
- Test passes. Node count and order are stable across two identical upserts.

---

## PHASE 1 CHECKPOINT

Before starting Phase 2, verify ALL of the following:
1. `python -m pytest tests/test_flow_decompose.py -v` — all tests green (includes round-trip).
2. `python -m pytest tests/ -q` — no pre-existing tests regressed.
3. In a live DB, after server restart, run:
   `SELECT name, COUNT(*) as node_count FROM flow_definitions fd JOIN flow_nodes fn ON fn.flow_def_id=fd.id GROUP BY fd.id`
   and confirm all 5 flows have > 0 nodes.
4. `_load_flow` is NOT modified in Phase 1 — FSM still reads the blob.

---

## Phase 2 — READ SIDE
Flip FSM to read from rows. Blob becomes the fallback.
The FSM behavior is identical to Phase 1 from the outside — same dict, same call sites.

---

### T2.1 — Promote `_assemble_from_parts` to `_assemble_flow_dict` (DB-backed)

**File:** `src/pathly_orchestrator/db/queries/flow_defs.py`

**What to do:**
The Phase 1 function `_assemble_from_parts` takes in-memory lists. Phase 2 needs a
DB-backed version that reads rows from the DB. Add:

```python
def _assemble_flow_dict(
    conn: sqlite3.Connection,
    flow_def_id: int,
    flow_level_config: dict,
) -> dict:
    """Reconstruct the YAML-equivalent dict from flow_nodes + flow_edges rows.
    Calls read_flow_nodes and read_flow_edges, then delegates to _assemble_from_parts.
    """
    nodes = read_flow_nodes(conn, flow_def_id)
    edges = read_flow_edges(conn, flow_def_id)
    return _assemble_from_parts(flow_level_config, nodes, edges)
```

`_assemble_from_parts` from T1.6 is not deleted — it stays as the pure helper called
by both the DB-backed function and the round-trip test.

**Acceptance criteria:**
- `_assemble_flow_dict` is importable from `pathly_orchestrator.db.queries.flow_defs`.
- Called on an in-memory DB populated by `upsert_flow_definition` with `team.flow.yaml`,
  it returns a dict equal to `yaml.safe_load(team_flow_yaml)`.

---

### T2.2 — Flip `_load_flow` to rows-if-present / blob-fallback

**File:** `src/pathly_orchestrator/fsm_ops.py`

**What to do:**
Replace the body of `_load_flow` with the branching logic from DESIGN_SPEC Q2.

Current body (lines 68-84):
```python
def _load_flow(flow_name: str, project_root: str | None = None) -> dict:
    if project_root is not None:
        try:
            ...
            for row in read_flow_definitions(conn, search_root):
                if row["name"] == flow_name:
                    return yaml.safe_load(row["flow_yaml"])   # <- THIS IS WHAT CHANGES
        except Exception:
            pass
    text = (files("pathly_data")
            .joinpath(f"core/flows/{flow_name}.flow.yaml")
            .read_text(encoding="utf-8"))
    return yaml.safe_load(text)
```

New body — for each flow definition row found, attempt DB-backed assembly:
```python
def _load_flow(flow_name: str, project_root: str | None = None) -> dict:
    if project_root is not None:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.flow_defs import (
                read_flow_definitions, read_flow_nodes, _assemble_flow_dict,
            )
            import json as _json
            conn = get_db(project_root)
            for search_root in [project_root, None]:
                for row in read_flow_definitions(conn, search_root):
                    if row["name"] == flow_name:
                        # Rows-if-present path (Phase 2)
                        node_rows = read_flow_nodes(conn, row["id"])
                        if node_rows:
                            flow_level_config = _json.loads(row.get("config_json") or "{}")
                            return _assemble_flow_dict(conn, row["id"], flow_level_config)
                        # Fallback: blob
                        return yaml.safe_load(row["flow_yaml"])
        except Exception:
            pass
    # Package resource fallback (CLI without DB / test isolation)
    text = (files("pathly_data")
            .joinpath(f"core/flows/{flow_name}.flow.yaml")
            .read_text(encoding="utf-8"))
    return yaml.safe_load(text)
```

**Acceptance criteria:**
- `grep -n "yaml.safe_load(row" src/pathly_orchestrator/fsm_ops.py` returns no matches
  (the old blob read path is gone from the DB branch).
- `python -m pytest tests/test_fsm_ops.py -v` — all pre-existing tests pass.
- `python -m pytest tests/ -q` — no regressions.
- Manual smoke: `pathly-fsm-call next-action --flow team --topic smoke-test-phase2 --project-root <repo>` returns a valid response with `current_state` and `agent`.

---

### T2.3 — `stage_configs` override still operates on assembled dict

**File:** `src/pathly_orchestrator/fsm_ops.py`

**What to do:**
Read lines 589-604 of `fsm_ops.py` (the `stage_configs` override merge). Confirm that
code operates on `flow_config` (the assembled dict returned by `_load_flow`), not on
DB rows directly. No code change required if it already does — this task is a
verification + comment.

Add a one-line comment above the override block:
```python
# stage_configs override: operates on the assembled flow_config dict (Q3 DESIGN_SPEC).
# No change needed here — _load_flow now returns rows-assembled dict, same shape.
```

**Acceptance criteria:**
- `grep -n "stage_configs" src/pathly_orchestrator/fsm_ops.py` shows the override block
  references `flow_config[...]` dict-style access, not any DB query.
- Grep confirms the comment is present.

---

### T2.4 — FSM full-pipeline regression test on team flow

**File:** `tests/test_fsm_ops.py` (add one test)

**What to do:**
Add a parametrized test that drives `next_action` for each of the 5 bundled flows
starting from their first state, using an in-memory DB populated by `upsert_flow_definition`.
This confirms that `_load_flow` (now rows-backed) returns a valid, FSM-consumable dict.

```python
@pytest.mark.parametrize("flow_name,expected_first_state", [
    ("team",      "STORMING"),
    ("debug",     "INVESTIGATING"),
    ("explore",   "FRAMING"),
    ("test",      "STORMING"),
    ("quick-fix", "SCOPING"),
])
def test_load_flow_from_rows(flow_name, expected_first_state, tmp_path):
    # Populate DB, then call _load_flow with a project_root that resolves to that DB.
    # Assert states[0] == expected_first_state.
    ...
```

Use the existing `tmp_path` fixture pattern from `conftest.py` / `test_fsm_ops.py` to
set up an isolated DB.

**Acceptance criteria:**
- `python -m pytest tests/test_fsm_ops.py -v -k "test_load_flow_from_rows"` exits 0.
- All 5 parametrize cases green.

---

## PHASE 2 CHECKPOINT

Before starting Phase 3, verify ALL of the following:
1. `python -m pytest tests/ -q` — zero failures.
2. `python -m pytest tests/test_flow_decompose.py::test_round_trip -v` — still green.
3. `python -m pytest tests/test_fsm_ops.py -v -k "test_load_flow_from_rows"` — green.
4. Manual full-pipeline smoke run completes at least STORMING → PLANNING with no
   `yaml.safe_load` fallback path triggered (confirm by adding a debug log or by
   checking that node rows exist in the DB after startup).

---

## Phase 3 — STUDIO
New `/graph` HTTP endpoints + Studio frontend migration.
All Phase 3 tasks depend on Phase 2 being merged and verified.

---

### T3.1 — Add `GET /flows/<name>/graph` endpoint

**File:** `src/pathly_orchestrator/http_server/blueprints/skills.py`

**What to do:**
Add a new route BEFORE the existing `GET /flows/<path:name>` route (Flask route
specificity: the `/graph` suffix must be registered before the catch-all `<path:name>`
pattern):

```python
@bp.route("/flows/<name>/graph", methods=["GET"])
def get_flow_graph(name: str):
    """Return a flow's structure as a parsed JSON object (assembled from rows).
    Response: { "graph": <FlowYaml-shaped dict>, "name": str }
    """
```

Implementation:
1. `read_flow_by_name(conn, name)` — 404 if not found.
2. `read_flow_nodes(conn, row["id"])` — if empty, fall back to `yaml.safe_load(row["flow_yaml"])` as graph.
3. If rows exist: `flow_level_config = json.loads(row.get("config_json") or "{}")`,
   then `graph = _assemble_flow_dict(conn, row["id"], flow_level_config)`.
4. Return `jsonify({"graph": graph, "name": name}), 200`.

**Acceptance criteria:**
- `curl http://127.0.0.1:8765/flows/team/graph` returns HTTP 200 with a JSON body
  containing `"graph"` key and `graph.states` list of length 8.
- `curl http://127.0.0.1:8765/flows/nonexistent/graph` returns HTTP 404.
- The `"graph"` value equals `yaml.safe_load(team.flow.yaml)` (same structure as the
  existing `GET /flows/team` blob, but pre-parsed).

---

### T3.2 — Add `PUT /flows/<name>/graph` endpoint

**File:** `src/pathly_orchestrator/http_server/blueprints/skills.py`

**What to do:**
Add a route immediately after T3.1:

```python
@bp.route("/flows/<name>/graph", methods=["PUT"])
def update_flow_graph(name: str):
    """Replace a flow's nodes+edges from a structured graph JSON payload.
    Body: { "graph": <FlowYaml-shaped dict> }
    Effect (one write-lock, one commit):
      - upsert flow_definitions (re-serialized flow_yaml cache + config_json)
      - replace-all flow_nodes / flow_edges
      - write-through .flow.yaml to disk
    Returns: { "ok": true }
    """
```

Implementation:
1. Parse `data = request.get_json()` — 400 if missing.
2. `graph = data.get("graph")` — 400 if missing or not a dict.
3. Re-serialize to YAML: `flow_yaml = yaml.dump(graph, allow_unicode=True, sort_keys=False)`.
4. `existing = read_flow_by_name(conn, name)` — use `file_path` for disk write-through.
5. Call `upsert_flow_definition(conn, project_root=None, name=name, version="", flow_yaml=flow_yaml, file_path=file_path)`.
   This single call handles: blob update + decompose + replace_flow_graph atomically.
6. Write-through to disk (same pattern as existing `PUT /flows/<name>`).
7. Return `jsonify({"ok": True}), 200`.

**Acceptance criteria:**
- `PUT /flows/team/graph` with a valid `FlowYaml`-shaped body returns `{"ok": true}`.
- After the PUT, `GET /flows/team/graph` returns the same graph that was PUT.
- After the PUT, `GET /flows/team` returns `flow_yaml` consistent with the PUT graph.
- The `.flow.yaml` file on disk is updated (check mtime or content).
- `PUT /flows/team/graph` with `{}` body (missing `graph` key) returns 400.

---

### T3.3 — Add `fetchFlowGraph` and `saveFlowGraph` to `pathlyApi.ts`

**File:** `studio/src/renderer/src/services/pathlyApi.ts`

**What to do:**
Add two new exported async functions alongside the existing `fetchFlow` and `saveFlow`.
Do NOT modify `fetchFlow` or `saveFlow` — the YAML tab and existing callers keep using them.

```typescript
export async function fetchFlowGraph(
  name: string
): Promise<{ name: string; graph: FlowYaml } | null> {
  const { apiFetch } = await import('../lib/config')
  try {
    const r = await apiFetch(`/flows/${encodeURIComponent(name)}/graph`)
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

export async function saveFlowGraph(name: string, graph: FlowYaml): Promise<void> {
  const { apiFetch } = await import('../lib/config')
  await apiFetch(`/flows/${encodeURIComponent(name)}/graph`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ graph }),
  })
}
```

**Acceptance criteria:**
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes with no errors.
- `fetchFlowGraph` and `saveFlowGraph` are importable from `pathlyApi`.
- `fetchFlow` and `saveFlow` signatures are unchanged (grep confirms).

---

### T3.4 — Migrate `useFlowFile.ts` visual-save path to `/graph`

**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`

**What to do:**
The hook currently loads via `fetchFlow` (YAML blob) and saves via `saveFlow` (YAML string).
Migrate the visual path only — the YAML tab (`handleYamlSave`) stays on the existing path.

**Load path change** (in the `useEffect` that fires on `selectedItem?.path`):
- Replace `fetchFlow(name)` with `fetchFlowGraph(name)`.
- On success, `result.graph` is already a parsed `FlowYaml` — assign directly to
  `setFlowData(result.graph)` and `lastValidFlowDataRef.current = result.graph`.
- The `rawYaml` state for the YAML tab still needs content. Set it by serializing:
  `setRawYaml(jsYaml.dump(result.graph, { lineWidth: 120 }))`.
- Remove the `parseFirstDoc` call from the load path (the graph is already parsed).
- Keep the `try/catch` and error state assignments.

**Save path change** (`handleVisualSave`):
- Replace `saveFlow(name, content)` (where `content = jsYaml.dump(...)`) with
  `saveFlowGraph(name, flowDataRef.current)` — send the object directly, no client-side dump.
- Remove `const content = jsYaml.dump(...)` from this function.

**What does NOT change:**
- `handleYamlSave(content: string)` — still calls `saveFlow(name, content)`.
- `handleTabSwitch` logic — no change.
- `parseFirstDoc` function — keep it (still used by YAML→Visual tab switch path).
- `fetchFlow` import — keep it if `handleTabSwitch` or `handleYamlSave` needs it,
  but it is no longer called during initial load.

**Acceptance criteria:**
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes with no errors.
- `grep -n "fetchFlow\b" studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
  — `fetchFlow` is no longer called in the load `useEffect`.
- `grep -n "fetchFlowGraph" studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
  — present and used in the load `useEffect`.
- `grep -n "saveFlowGraph" studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
  — present and used in `handleVisualSave`.
- `grep -n "saveFlow\b" studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
  — still present in `handleYamlSave` only.
- `grep -n "jsYaml.dump" studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts`
  — NOT present in `handleVisualSave` (only in `handleTabSwitch` and the rawYaml seed).
- Opening a flow in Studio visual view loads without errors, and Save persists to the DB.

---

### T3.5 — Update `useFlowFile.test.ts` for new load path

**File:** `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.test.ts`

**What to do:**
Read the existing test file. Update any mocks or assertions that stub `fetchFlow` in
the visual-load path — change them to stub `fetchFlowGraph` returning
`{ name: "...", graph: <FlowYaml object> }` instead of `{ name: "...", flow_yaml: "..." }`.

Keep tests that test the YAML tab save path pointing at `saveFlow`.

**Acceptance criteria:**
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes.
- All existing tests in `useFlowFile.test.ts` pass (if the project has a test runner
  configured: run `npm test` or `npx vitest run` from the repo root).
- No test mocks `fetchFlow` for the visual load path.

---

## PHASE 3 CHECKPOINT

Verify ALL of the following:
1. `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` — no errors.
2. `python -m pytest tests/ -q` — zero failures.
3. Live Studio smoke:
   - Open the FlowEditor visual view on any flow — loads without error toast.
   - Rename a state, click Save — no error, `GET /flows/<name>/graph` returns the change.
   - Switch to YAML tab, make an edit, Save — blob path still works.
4. `curl http://127.0.0.1:8765/flows/team/graph` — 200 with full graph JSON.
5. `curl http://127.0.0.1:8765/flows/team` — still 200 with `flow_yaml` field (unchanged).

---

## Cross-phase constraints (enforced across all phases)

1. **`flow_def_id` scoping** — every `read_flow_nodes` / `read_flow_edges` / `replace_flow_graph`
   call MUST use the resolved `flow_def_id` integer from the `flow_definitions` row, never
   re-resolve by name. Verify with grep: no `WHERE name=?` in `flow_nodes` or `flow_edges` queries.

2. **`adapter_map` emission guard** — `_assemble_from_parts` must never emit `adapter_map`
   with only a `"default"` key and no per-state entries, AND must never emit an `adapter_map`
   at all when `adapter_default` is None and no per-state adapters exist. The team flow has no
   `adapter_map` — verify the round-trip test covers this (team reconstructed dict must have
   no `adapter_map` key).

3. **Blob column never dropped** — `flow_definitions.flow_yaml` must remain a NOT NULL
   column through all three phases. Grep: `flow_yaml` still appears in the CREATE TABLE
   statement in `migrations.py`.

4. **No FSM call-site changes** — grep `build_prompt`, `evaluate_transition_rules`,
   `run_gates`, `route_feedback`, `build_menu_payload` across `fsm_ops.py` and `fsm.py`:
   none of them should reference `flow_nodes`, `flow_edges`, or `read_flow_nodes` — they
   all continue to operate on the assembled `flow_config` dict.
