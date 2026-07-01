# Architecture Proposal — unified-cli-composition

_Written: 2026-06-29. Author: architect subagent. Based on BRIEF.md, ARCHITECT_ASSESSMENT.md,
ORCHESTRATION_MODEL.md, PO_NOTES.md, and a live code audit._

---

## 1. Verdict

P0 is complete and correct. The composition seam (`POST /skills/compose`), the client
service (`skillCompose.ts`), the fragment engine (`compose.py`), the manifest
(`composition.yaml`), and both transform fragments (`client-file-output.md`,
`artifact-transform.md`) are merged and active.

The work remaining is Gate 2: two missing fragments (`board-start-context`,
`task-dag-post`) and the Decompose conversion that consumes them. Gate 3 (loop board-I/O
+ `profiles:` rename) is deferred until Gate 2 validates the model. Nothing in the
existing design needs to be revised; this document records the technical contract for
what must be built next.

---

## 2. Current state (post-P0 code audit)

| Component | Status | Location |
|---|---|---|
| `POST /skills/compose` endpoint | ✅ live | `http_server/blueprints/skills/editor_render.py:236` |
| `composeClientSkill()` TS client | ✅ live | `studio/src/renderer/src/services/skillCompose.ts` |
| `compose.py` (composition engine) | ✅ live | `src/pathly_orchestrator/skills/compose.py` |
| `composition.yaml` (manifest, ~20 skills) | ✅ live | `src/pathly_data/core/skills/composition.yaml` |
| `client-file-output.md` fragment | ✅ live | `core/skills/fragments/client-file-output.md` |
| `artifact-transform.md` fragment | ✅ live | `core/skills/fragments/artifact-transform.md` |
| `comms-post.md`, `catalog-pull.md`, `completion-report.md` | ✅ live | `core/skills/fragments/` |
| `board-start-context.md` fragment | ❌ missing | to be built (Gate 2) |
| `task-dag-post.md` fragment | ❌ missing | to be built (Gate 2) |
| Decompose conversion to composition | ❌ missing | Gate 2 |
| `profiles:` manifest rename | 🔒 deferred | Gate 3 only |
| Loop/drain board-I/O conversion | 🔒 deferred | Gate 3 only |

---

## 3. Layers touched and dependency direction

```
Renderer (TS)                  Python backend
──────────────────             ─────────────────────────────────────────────
skillCompose.ts                http_server/blueprints/skills/editor_render.py
  └─ POST /skills/compose ───▶   compose_skill()  (skills/compose.py)
                                   ├─ load_effective_manifest()
                                   ├─ adapter_caps_for()
                                   └─ fragment bodies (pathly_data/core/skills/fragments/)
                                       ├─ client-file-output.md   ✅
                                       ├─ artifact-transform.md   ✅
                                       ├─ board-start-context.md  ← Gate 2
                                       └─ task-dag-post.md        ← Gate 2

Supervisor (Python)
──────────────────
supervisor/goal_run.py
  └─ Decompose POST (hard-coded today) ← Gate 2: convert to compose_skill()
```

Layer rule: fragment bodies live in `pathly_data` (data layer); `compose.py` reads
them (orchestrator layer); blueprints call compose (HTTP layer). This direction holds
for Gate 2 — no new cross-layer violation is introduced.

---

## 4. Gate 2 — technical contract

### 4a. `board-start-context.md` fragment

**Role:** Pull-once-at-start board context preamble for goal-backed actions (governance,
active tasks, recent decisions, catalog refs). Distinct from `catalog-pull`, which is
on-demand mid-run.

**Placement in composed prompt:** Injected after the skill body and before
`comms-post`/`task-dag-post`, so the agent has board context before any write.

**Payload contract:**
```
GET /comms/retrieve?scope={scope}&goal_id={goal_id}&limit=10
```
Returns: governance lines, up to 5 recent board messages, active tasks for the goal,
catalog artifact list (names only). The fragment instructs the agent to treat this as
read-only preamble — it does not mutate the board; it only reads context before acting.

**Capability gate:** Requires `goal_id` in spawn context. If `goal_id` is absent, the
fragment is a no-op (skip silently). This gate is enforced in `compose_skill()` via
`adapter_caps`; the fragment body must open with a guard comment stating the gate
condition.

**Error behavior:** If the board is unreachable (connection refused), the fragment
emits a brief "board context unavailable" note and the agent continues without it.
Never blocks execution.

### 4b. `task-dag-post.md` fragment

**Role:** Declarative task-tree writing. Instructs the agent to post structured task
records to `/comms/tasks` after completing its reasoning. Consumed by Decompose
(planner) and future DAG-posting agents.

**Payload shape (per task posted):**
```json
{
  "title": "string",
  "description": "string",
  "goal_id": "<from spawn context>",
  "parent_id": "<parent task id or null>",
  "depends_on": ["<task-id>", ...],
  "executor": "single|loop|team",
  "kind": "task"
}
```

**API:** `POST /comms/tasks` (existing route). The fragment provides the call
instruction; the agent fills the fields from its reasoning output.

**Constraint (from PO_NOTES):** this fragment is NOT composed into Summary/Analyze/Split
(standalone transforms). It is goal-backed only and requires `goal_id`.

### 4c. Decompose conversion

**Current state:** `supervisor/goal_run.py` hard-codes a `POST /comms/tasks` call with
a Python-built prompt and parses the response inline.

**Target state:** Decompose calls `compose_skill("planning/plan", adapter_caps,
manifest)` to assemble `skill body + board-start-context + task-dag-post + comms-post`.
The composed prompt is passed to the CLI engine headlessly; result is captured via
`AGENT_DONE.summary` (the standard file-based path, not stdout parsing).

**Migration steps:**
1. Extend the existing `planning/plan` entry in `composition.yaml` with the two new Gate 2 fragments (it already carries `completion-report`).
2. Replace the hard-coded Python POST in `goal_run.py` with `compose_skill()` + a
   standard headless spawn.
3. Remove the inline response parser; the agent's `AGENT_DONE.summary` is the
   authoritative result.
4. Verify: `AGENT_DONE` contains the posted task IDs so the supervisor can record them
   without re-querying the board.

**Acceptance:** a goal Decompose run produces a populated task DAG on the board without
any Python-side task-payload construction.

---

## 5. Profile selection — implementation contract

The spawn context object (`{ goal_id?, scope, executor, kind }`) is the switch.
`compose_skill()` receives `adapter_caps` which includes these context fields.
The selection logic (no new branching — declarative fragment gating):

```python
# inside compose.py adapter_caps construction (existing pattern)
adapter_caps["goal_id"] = ctx.get("goal_id")          # None for standalone
adapter_caps["executor"] = ctx.get("executor", "single")
adapter_caps["kind"] = ctx.get("kind", "agent")

# in composition.yaml, each fragment entry:
# { name: board-start-context, requires: goal_id }
# { name: task-dag-post,       requires: goal_id }
# { name: client-file-output,  requires: "!goal_id" }  # standalone only
```

This keeps the `requires:` gating pattern that already exists for `can_spawn`. No new
Python branching needed.

**Inspectability constraint (from PO_NOTES §2):** `goal_id`, `executor`, and `kind`
must be logged in the spawn event so the board can show what profile was selected. The
`PHASE_START` record is the natural place — add them as metadata keys.

---

## 6. Error normalization (P0-blocking for Gate 2)

**Requirement:** `ERROR:` file outputs must flow through the same pill/error path for
all converted actions before Gate 2 ships.

**Current gap:** Gate 1 defined the `ERROR:` file naming contract in the
`client-file-output` fragment. The UI normalization (reading that file and rendering it
in the ActionPill/RunPill as an error state) must be complete before Decompose ships.

**Contract:** If the CLI engine writes a file matching `*.error` or containing the
`ERROR:` prefix, the renderer reads it and surfaces the error in the same pill that
started the action. This is a renderer-side change in `skillCompose.ts` or the
ActionPill component; no new Python work needed.

**Gate:** Gate 2 is blocked on this being proven correct for at least one of
Summary/Analyze/Split before Decompose ships.

---

## 7. Risks and mitigations

### Profile selection drift (main risk)
If `adapter_caps` construction becomes inconsistent between the HTTP path (renderer →
`POST /skills/compose`) and the supervisor path (`goal_run.py` → `compose_skill()`
in-process), the two paths will silently compose different profiles for the same skill.

**Mitigation:** Extract a single `build_adapter_caps(ctx)` helper in `compose.py` used
by both paths. Never construct `adapter_caps` inline at the call site.

### Two composition APIs
The renderer calls via HTTP; the supervisor calls in-process. Both call `compose_skill()`
but the HTTP path additionally handles dash-safety and transform variable injection
in `editor_render.py`.

**Mitigation:** Any logic added to `editor_render.py::skills_compose()` that is not
renderer-specific (e.g., context enrichment, profile resolution) must be pushed into
`compose_skill()` so the supervisor path picks it up automatically. Reviewer checklist
item for every Gate 2 PR.

### Decompose regression
The existing hard-coded decompose path is tested through normal goal runs. Replacing it
with the composition path changes prompt delivery, variable injection order, and result
capture.

**Mitigation:** Before cutting over, run a side-by-side: old path vs. composed path on
the same goal, compare the task DAG produced. Only cut over when the DAGs are
equivalent.

### Gate 3 scope creep
`profiles:` rename + loop board-I/O conversion are significant and must not bleed into
Gate 2. Any PR that touches `composition.yaml`'s `blocks:` key at Gate 2 is a
violation.

**Mitigation:** Hard rule: no `blocks:` → `profiles:` rename until Gate 2 is deployed
and validated. Reviewers reject any Gate 2 PR that touches that key.

---

## 8. Sequencing (Gate 2 only)

The correct build order within Gate 2 is:

1. **Error normalization UI** — prove the ActionPill/RunPill error path for
   Summary/Analyze/Split. Unblocks the rest.
2. **`board-start-context.md` fragment** — write and add to `composition.yaml` for
   `planning/plan`; test via a manual `POST /skills/compose` call with `goal_id` present
   vs. absent.
3. **`task-dag-post.md` fragment** — same pattern; verify the POST payload against
   `/comms/tasks` schema.
4. **`planning/plan` manifest entry** — add the two new fragments under the `planning/plan`
   skill in `composition.yaml`.
5. **Decompose conversion** — replace hard-coded Python in `goal_run.py`; verify DAG
   equivalence.
6. **`build_adapter_caps()` helper** — extract from both call sites to close the drift risk.

Do not start step 5 until steps 2 and 3 are validated in isolation.

---

## 9. What this does NOT change

- The fragment engine (`compose.py`) needs no structural changes for Gate 2 — only the
  addition of the two fragment files and two manifest entries.
- `composition.yaml`'s `blocks:` key is not renamed (Gate 3 only).
- The loop executor (`_run_loop` frontier) is not touched (Gate 3 only).
- `model/Brightsky/websocket` split is a separate deferred plan; nothing here touches it.
- Raw board skills (`team/architect`, `team/research`) remain raw (P3).

---

## 10. Acceptance criteria (Gate 2 done when)

1. A goal Decompose run assembles its prompt through `compose_skill("planning/plan")`
   with `board-start-context` and `task-dag-post` fragments composed in; no Python-built
   prompt string at the call site.
2. The composed prompt includes a board-context preamble when `goal_id` is present and
   skips it cleanly when absent.
3. The produced task DAG on the board is equivalent to what the old hard-coded path
   produced.
4. `AGENT_DONE.summary` is the authoritative Decompose result; no stdout parsing at the
   supervisor.
5. A developer can add a new fragment to the Decompose profile by editing
   `composition.yaml` — no Python code change required.
6. Error normalization: an `ERROR:` output from any converted action renders as an error
   state in its pill; no silent swallow.
7. `goal_id`, `executor`, and `kind` appear in the `PHASE_START` event for every
   Decompose run.
