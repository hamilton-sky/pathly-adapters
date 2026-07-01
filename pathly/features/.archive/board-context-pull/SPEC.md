# Board Context Pull — design spec

**Feature:** `board-context-pull`
**Status:** proposed (2026-06-24)
**Owner area:** comms-board / Goals-DAG (`src/pathly_orchestrator/runner/comms_context.py`,
`supervisor/`, `core/skills/development/drain-dag.md`, Studio Goals & Tasks view)
**Relation:** complements [comms-board/ROADMAP.md](../comms-board/ROADMAP.md). All of
comms-board is shipped to `master` **except P3 (parallel)**; this feature is a set of
near-term, lower-risk quality wins that should land **before** P3 and make P3 more valuable.

---

## 0. Why this feature

The Board → Goals → per-goal Task-DAG → pluggable-executors system is live and verified
end-to-end (2026-06-22). Agents already receive board context, but the way they receive
it has three concrete gaps. This feature closes them.

| # | Gap | Today | This feature |
|---|---|---|---|
| A | Context is **push-only & k-capped** | Agent sees only 🔒 governance + 📎 pre-attached `context_refs` + 💡 top-k semantic hits. No sanctioned way to fetch more. | Add a **permission-scoped catalog-pull affordance** — tell the agent it may browse + hydrate the artifact catalog for its own board. |
| B | **No per-task timing / flow visibility** | `task_status` flips pending→in_progress→done, but there's no surfaced duration or "what context did this task pull" trail. | Instrument **claim→complete duration** + a context-access trail, surface on the Goals & Tasks view. |
| C | **No way to preview/simulate** an agent's context | You can't see what the board-context block *would* contain for a task without running it. | Add a **context-preview ("simulation") endpoint** that renders the block read-only. |

Plus one piece of housekeeping (§5): `comms-board/STATE.json` still reports a stale
`BUILDING` mirror from 2026-06-14 and should be cleared.

---

## 1. Background — how board context reaches an agent today

`runner/comms_context.py::retrieve_board_context()` assembles a `## Communication Board`
markdown block and appends it to `agent_hint.instructions`. It has three channels:

1. **🔒 Governance** — `get_pending_decisions()` + `get_active_escalations()`, injected
   unconditionally ("always applies — do not override"). Computed *before* the semantic
   search so governance rows don't consume the tight semantic slots.
2. **📎 Referenced context** — only when a `task_id` is passed: reads the task's
   `context_refs` JSON, hydrates each `{artifact, anchor}` via
   `runner/hydrate.py::hydrate_section()`, and inlines the authoritative section `text`.
3. **💡 Context** — `search_by_hybrid()` semantic/keyword matches, relevance-gated
   (`_SEMANTIC_MAX_DISTANCE = 0.75`) and char-budgeted (`_CONTEXT_CHAR_BUDGET = 2000`),
   per-board k-caps (feature 3 / project 2 / global 1).

`board_context_for(board, scope, project_root, task_description, task_id)` is the
scope-aware entry point used by the **single**, **loop**, and `/comms/run` execution
surfaces. It resolves the user's per-feature board-scope toggle
(`get_board_scope`) and delegates to `retrieve_board_context`.

**The catalog already exists but agents never pull from it.** These backend primitives
are live and unused by the agent prompt path:

- `GET /comms/artifacts?board=<board>&scope=<scope>` →
  `db/queries/comms.py::list_artifacts_catalog(conn, scope, exposed_boards=[board], …)`.
  **Already permission-scoped** via `exposed_boards` — this is the "specific board
  permissions" the agent should be limited to.
- `GET /comms/artifacts/<id>/section` and `?artifact=&anchor=` →
  `hydrate_section()` — hydrate any named section on demand.

So the gap is **prompt-side**: agents are never told the catalog is browsable, and the
`drain-dag` skill only hydrates refs that were *pre-attached* to the task.

---

## 2. Solution A — permission-scoped catalog-pull affordance (lead)

**Goal:** turn today's passive *push* into *push + pull*. The curated channels stay; we
add an explicit, bounded invitation for the agent to fetch more, scoped to the boards its
permissions expose.

### A.1 New channel in the context block

Add a fourth channel to `retrieve_board_context()` output, after 💡 Context:

```
### 📚 Catalog (you may pull more — scoped to your board)
You have access to additional artifacts beyond the references above. To list them:
  GET /comms/artifacts?board=<board>&scope=<scope>
To read a section of one:
  GET /comms/artifacts/<id>/section?anchor=<anchor>   (omit anchor for the whole file)
Only pull what the task needs. The references in 📎 above are already hydrated — don't refetch them.
```

- Emitted only when the catalog for the agent's exposed boards is **non-empty** (one
  cheap `list_artifacts_catalog(limit=1)` existence probe; if empty, omit the channel so
  the block stays byte-identical to today for empty boards).
- `<board>`/`<scope>` are filled from the resolved scope so the agent can't widen its own
  permissions — the URL it's handed is already the permission-scoped one.
- Optional enhancement: include a short **catalog index** (title + id + summary, top N by
  recency) inline so the agent can pick without a round-trip. Gate the size with a new
  `_CATALOG_INDEX_MAX` budget mirroring `_CONTEXT_CHAR_BUDGET`.

### A.2 Skill wording

`core/skills/development/drain-dag.md` currently hydrates only `context_refs` (step 3).
Add a sub-step: *"If the task references material not in `context_refs`, you may list the
board catalog (`GET /comms/artifacts?board=&scope=`) and hydrate any section you need.
Pull narrowly."* Mirror the same note in `team/review.md` / `development/review.md`
(reviewers benefit most from pulling adjacent spec sections).

> `drain-dag.md` is intentionally **raw/unconverted** (no fragments) — edit it directly.

### A.3 Permission boundary

The `board` value passed to `list_artifacts_catalog(exposed_boards=[board])` is the
agent's tier (feature/project/global) resolved by `board_context_for`. An agent on a
feature board is handed only `board=feature&scope=<topic>`; it cannot enumerate another
feature's artifacts. **No new permission model is needed** — `exposed_boards` + `scope`
already enforce it. Verify with a scope-isolation test (see §4).

### A.4 Files touched

- `src/pathly_orchestrator/runner/comms_context.py` — new 📚 channel + existence probe +
  `_CATALOG_INDEX_MAX`.
- `src/pathly_data/core/skills/development/drain-dag.md` — pull sub-step.
- `src/pathly_data/core/skills/{development,team}/review.md` — mirror note.
- Adapter sync: `pathly-setup claude --apply --repair` + `python -m build` (core→4 adapters).

---

## 3. Solution B — DAG task-duration & context-access trail

**Goal:** "see the flow of the agent getting all relevant information" — make per-task
timing and context access visible on the Goals & Tasks view.

### B.1 Duration

`comms_messages` tasks already carry `task_status` and `claimed_by`. Add (additive
migration, nullable):

| Column | On | Meaning |
|---|---|---|
| `claimed_at` | task | timestamp when `POST /comms/tasks/claim` succeeded |
| `completed_at` | task | timestamp when `complete`/`fail` recorded |

Duration = `completed_at − claimed_at`. Populate in the existing claim/complete/fail
handlers (`blueprints/comms/tasks.py`). Surface `duration_seconds` in
`GET /comms/tasks` and render a per-task chip + a per-goal roll-up on the Studio Goals &
Tasks view. Zero behavioural change to execution — pure observability.

### B.2 Context-access trail (optional, pairs with A)

When an agent pulls from the catalog (§2), have the board log a lightweight
`context_access` status post (or a counter on the task) so the timeline shows *which*
artifacts a task pulled. This is the literal "flow of the agent getting all relevant
information from the board" the request asks for. Keep it cheap — a `type=status` post is
enough for v1; a dedicated column can come later.

### B.3 Files touched

- `src/pathly_orchestrator/db/migrations.py` — `claimed_at` / `completed_at` columns.
- `src/pathly_orchestrator/db/queries/comms.py` — set on claim/complete/fail; return
  `duration_seconds`.
- `src/pathly_orchestrator/http_server/blueprints/comms/tasks.py` — wire timestamps.
- Studio Goals & Tasks view — duration chip + roll-up.

---

## 4. Solution C — context preview / "simulation" endpoint

**Goal:** render *what an agent would see* for a task, read-only, without running it.
Directly supports reviewing governance + catalog scoping before a run.

```
POST /comms/agent-context/preview
  { board, scope, project_root, task_description, task_id? }
  → { block: "<the rendered ## Communication Board markdown>",
      channels: { governance: n, referenced: n, semantic: n, catalog: n } }
```

Thin wrapper over `board_context_for()` (no side effects) + the per-channel counts. Note
a `POST /comms/agent-context` route already exists for injection; this adds a **preview**
sibling that also returns the channel breakdown. Surface as a "Preview context" action on
a goal/task card in Studio so a human can sanity-check scoping and governance before
dispatching a goal.

> "Governance and simulation" from the request: **governance** is already fully wired (🔒
> channel, unconditional). **Simulation** = this preview endpoint — the missing half.

### 4.1 Files touched

- `src/pathly_orchestrator/http_server/blueprints/comms/` — new `agent-context/preview`
  route (own file if the domain file is near the 400-line limit, per SOLID rules).
- Studio goal/task card — "Preview context" action.

---

## 5. Housekeeping

- `pathly/plans/comms-board/STATE.json` reports a stale `current: "BUILDING"` mirror from
  2026-06-14. The feature is shipped; clear/retire the mirror so `pathly-status` and
  Studio feature-discovery stop misreporting it as in-progress.

---

## 6. Testing

| Area | Test |
|---|---|
| A — channel emission | `retrieve_board_context` emits 📚 only when catalog non-empty; byte-identical to today on empty boards. |
| A — permission boundary | feature-A agent handed `board=feature&scope=A` cannot enumerate feature-B artifacts (extends `tests/test_board_context_scope.py`). |
| A — budget | catalog index respects `_CATALOG_INDEX_MAX`; large catalog truncates with a "… N more" line. |
| B — duration | claim then complete populates `claimed_at`/`completed_at`; `duration_seconds` returned and non-negative; fail path also stamps `completed_at`. |
| C — preview | `/comms/agent-context/preview` returns the same block `board_context_for` would inject, plus correct per-channel counts, with no DB writes. |

Existing suites to extend: `tests/test_comms_context_*.py`, `tests/test_board_context_scope.py`,
`tests/test_comms_agent_context.py`.

---

## 7. Sequencing & rationale

1. **A (catalog-pull)** — cheapest, highest-leverage; closes the push-only gap and
   immediately improves agent grounding. Mostly prompt-side; backend already exists.
2. **C (preview)** — small; makes A reviewable and de-risks governance/scope mistakes.
3. **B (duration/trail)** — observability; most useful once A is generating pull traffic,
   and the lane-timing data it adds feeds directly into **P3 (parallel)**.
4. **P3 (parallel)** — the remaining large comms-board phase; unchanged by this feature,
   but better instrumented and better grounded after A–C land.

Each of A, B, C is independently shippable. None changes execution semantics except A's
additive prompt channel, which is gated to be byte-identical on empty boards.

---

## 8. Out of scope

- P3 parallel execution (lanes / worktree fan-in / fan-in consolidation) — stays in
  `parallel-fleet-part-1/` and `-part-2/`.
- A new permission/RBAC model — `exposed_boards` + `scope` already enforce the boundary.
- Multi-adapter routing / Copilot+Antigravity spawn argv — separate deferred-polish items
  in the comms-board roadmap.
