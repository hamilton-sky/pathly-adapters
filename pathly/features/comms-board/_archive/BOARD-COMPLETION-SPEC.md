# Board Completion Spec — what's missing for a fully functional board

**Status:** gap analysis + plan · **Date:** 2026-06-15 · **Branch:** `feat/comms-board-live`

This is a **gap-and-plan** document, not an architecture doc. It assumes the
designs already written in this folder and lists only what is *missing* to reach
a fully functional board that can launch all run modes. Reference docs:
- [`LIVE-BOARD-ARCHITECTURE.md`](LIVE-BOARD-ARCHITECTURE.md) — the live runtime
- [`DAG-SCHEDULER-ARCHITECTURE.md`](DAG-SCHEDULER-ARCHITECTURE.md) — parallel-tree scheduler
- [`BOARD-RUNTIME-SPEC.md`](BOARD-RUNTIME-SPEC.md) — board run contract
- [`FULL-FLOW-READINESS.md`](FULL-FLOW-READINESS.md) — flow readiness
- [`BOARD-INTEGRATION-GAPS.md`](BOARD-INTEGRATION-GAPS.md) — earlier gap pass

---

## 1. Definition of done — "full functional board"

The board is the launch surface. From any board (global / project / feature) the
human can start work three ways, and *see what is happening*:

| Mode | What it does | State today |
|---|---|---|
| **1. Single agent** | One configured CLI run on the board message | ✅ working (this session) |
| **2. Flow of agents** | Two engines: **2a** linear FSM pipeline (exists, runs from FlowControlBar) launched from the board; **2b** board DAG — serial first (§B3.5), parallel later (B4–B6) | ❌ not launchable from board |
| **3. Evaluator** | An agent analyzes the board → emits artifact + DAG tasks (feeds 2b) | ◑ partial (not installed) |

"Functional" also means: the user is **never blind** (live progress on the
board), runs are **controllable** (start/stop/status), and **artifacts** are
first-class enough to be useful as context.

---

## 2. Current state snapshot (verified against code)

**Done — single-agent spawn (Mode 1):**
- `supervisor/board_run.py` — `start_board_run()`, async daemon, lifecycle posts
- `supervisor/board_lock.py` — per-(board,scope) lock, 409 on busy
- `http_server/blueprints/comms.py` — `/comms/run`, `/comms/run/stop`, `/comms/agent-context`
- **Central spawn/kill channel** — `sse.py` `_spawn_clients`/`_broadcast_spawn`,
  `streams.py` `/events/spawn`, one always-on subscriber in `useHQ.tsx`
  (terminals open/kill regardless of active topic) · `tests/test_spawn_channel.py`
- **Engine selector** — Claude / Codex (the two adapters with a headless command
  in `core/adapters.yaml`); per-engine default model
- **Modal compose + "Send to agent"** — board input box is now a pure note;
  agent prompt + config live in the gear modal
- Headless / interactive mode toggle; all board content removable (force soft-delete)

**Partial / not wired:**
- **Evaluator (Mode 3)** — `core/agents/research/evaluator.md` + `core/skills/planning/evaluate.md`
  exist and `start_board_run(mode="evaluator")` defaults to them, but they are
  **not installed** (no adapter `_meta/*.yaml`), so an interactive run can't load them.
- **DAG scheduler** — queries exist (`get_ready_tasks`, `claim_task`, `fail_task`,
  `complete_task`, `reclaim_stale_claims`), plus `supervisor/isolation.py` and
  `supervisor/scheduler.py::scheduler_loop`, but `scheduler_loop` is **never
  imported** by the supervisor. It is dead code today.
- **Flow from the board (Mode 2)** — does not exist. `/comms/run` only does
  single-agent / evaluator; `/comms/agent-context` returns `has_flow: False`.

---

## 3. Gap inventory

### Part A — Single-agent spawn polish (Mode 1)

| # | Gap | Evidence | Missing work | Size |
|---|---|---|---|---|
| A1 | **Global/project terminals unverified** | central channel added; not live-tested for `board=project/global` | Confirm `project_root` + board context resolve for non-feature scopes; live smoke test | S |
| A2 | **Live progress is just started/done** | `_on_start`/`_on_done` in `comms.py` | Stream agent activity to the board (reuse `PHASE_SUMMARY`); a board run should post periodic "still working…" / phase notes, not just two bookends | M |
| A3 | **Antigravity / Gemini engine** | `core/adapters.yaml` has no `antigravity`; `resolve_command` raises | Add `antigravity` headless command + `resolve_interactive_argv` branch (`agy`); needs the real `agy` CLI flags | M |
| A4 | **System-prompt presets are fixed** | `SYSTEM_PROMPTS` const in `SingleAgentButton.tsx` | Editable / persisted presets (DB-backed) | M |
| A5 | **No spawn durability** | `wait_started(30s)`, no replay | If Studio misses `TERMINAL_SPAWN`, run dies. Add ACK + re-send, or queue unstarted spawns | M |

### Part B — Flow of agents (Mode 2) — the main gap

| # | Gap | Evidence | Missing work | Size |
|---|---|---|---|---|
| B1 | **No "start a flow" from the board** | `/comms/run` is single-agent only | New board action → `POST /runner/start` with chosen flow + rigor; board becomes the launch surface for the existing supervisor pipeline | M |
| B2 | **Flow picker UI** | only the single-agent modal exists | Board control to choose flow (team / custom) + rigor (nano/lite/standard/strict); the third "Flow" start mode | M |
| B3 | **Flow progress on the board** | pipeline emits `STAGE_CHANGE`/`STAGE_RESULT` to `/events/runner` | Render stage progress on the board itself (not only the FlowControlBar), so the board shows the running pipeline | M |
| B4 | **DAG scheduler not wired** | `scheduler.py::scheduler_loop` unused | Wire `scheduler_loop` behind a `dag` flag: read ready frontier (`get_ready_tasks`) → claim → spawn per task → complete/fail cascade. The parallel-tree vision | L |
| B5 | **Task messages → frontier → spawn loop** | `post_message(type="task")` sets `task_status='pending'`; `depends_on` stored | Close the loop: a `task` with satisfied deps becomes ready → scheduler spawns an agent → result marks complete → unblocks dependents | L |
| B6 | **Lane / worktree isolation** | `isolation.py` `LaneIsolation` + `WorktreeIsolation` stub | Finish `WorktreeIsolation` so parallel tasks don't collide on disk | L |

#### B3.5 — Serial DAG execution (the bridge between linear flow and parallel DAG)

The board-native "flow of agents": instead of a fixed stage order, the **next
task comes from the board DAG** (`get_ready_tasks`), run **one at a time**. This
is Engine 3's task model with **concurrency = 1** — it delivers dependency-ordered
execution while skipping the hard parts of parallelism (no `claim_task` races, no
`WorktreeIsolation`, no fan-in). It is the correct stepping stone to B4–B6: flip
concurrency 1 → N later and the task model + loop are already proven.

```
loop:
  ready = get_ready_tasks(boards, scopes)        # ✅ exists
  if not ready: break                            # frontier empty → done
  task = ready[0]                                # serial: take one (by priority/order)
  prompt = build_task_prompt(task)               # task.text + its comms_artifacts + dep results
  spawn ONE visible agent (reuse _run_stage_via_terminal)   # ✅ spawn infra done
  on done → complete_task(task.id)               # ✅ exists — cascade unblocks dependents
```

| # | Piece | Status | Missing work | Size |
|---|---|---|---|---|
| B3.5a | **The serial loop** | not written; `get_ready_tasks` + `complete_task` cascade exist | A `serial_dag_loop` (≈ `scheduler_loop` with concurrency 1) that walks the frontier, spawning one agent per ready task via the existing terminal spawner | M |
| B3.5b | **Per-task prompt builder** | `comms_context` is board-wide | Build a narrow prompt: `task.text` + that task's `comms_artifacts` (its file set) + its dependencies' results — not the full governance+semantic block | M |
| B3.5c | **A way to start it** | only single-agent / (linear) flow | A `dag-serial` run mode on the board — sibling to single-agent and linear-flow start | S |
| B3.5d | **Who creates the DAG** | evaluator exists, not installed (C1) | A planner/evaluator decomposes work into `task` messages with `depends_on` + per-task artifacts. This is **Mode 3 (evaluator)** — so **C1 unlocks this whole path** | M |

**Dependency chain:** C1 (install evaluator) → evaluator emits the task DAG → B3.5a/b walk it serially → later B4–B6 flip to parallel.

### Part C — Cross-cutting (both modes)

| # | Gap | Evidence | Missing work | Size |
|---|---|---|---|---|
| C1 | **Evaluator not installable** | no `_meta` for evaluator/evaluate | Add adapter `_meta/*.yaml`; run `pathly-setup <host> --apply --repair`; then Mode 3 works interactively | S |
| C2 | **Artifacts are second-class** | `artifact_path/type/url` columns on a message; no title/summary | Artifacts view (Tickets ⇄ Artifacts toggle), context-aware search, artifact cards w/ metadata. See §4 | M |
| C3 | **Context is frozen at spawn (push)** | `comms_context.retrieve_board_context` runs once | Long runs can't see board updates mid-run. Acceptable now; a limit for live DAG. Document, revisit later | — |
| C4 | **Embeddings fail silently** | `embeddings.py` returns None if lib missing | Surface "semantic search unavailable (recency only)" to the user instead of silent fallback | S |

---

## 4. Artifacts as first-class (C2 detail)

Ship in two steps so value lands early.

**Decision — the summary is authored by the creating agent, not generated later.**
When an agent creates an artifact it writes the summary as part of the same
action (the `comms-post` / attach payload carries `summary`). There is no
separate summarization pass. The human can edit it afterward (which updates the
edit metadata below).

**Card metadata (the artifact card shows):**
- `scope` — which board: global id / project id / feature id
- `created_at` + `created_by` (agent or user)
- **`last_edit_at`** + **`last_edit_by`** — `agent | user` (who last touched it)
- `type` + file size + **`token_count`** (token size of the artifact body)
- `summary` — agent-authored at creation (see decision above)
- `linked_message` — the post the artifact came from (provenance)
- `version` / `supersedes` — artifacts evolve; reuse the supersede model
- click → preview pane + full metadata + **"Edit in MD editor"** (editing sets
  `last_edit_at` / `last_edit_by = user`)

**Decision — many artifacts per message/task (one-to-many).** A single message
or task can carry multiple files (a task often needs a set of paths, not one).
The current single `artifact_path/type/url` columns can't model this, so artifacts
become their own rows in a dedicated **`comms_artifacts`** table with a FK to the
owning message. This supersedes the "three columns on a message" model.

```
comms_artifacts
  id            TEXT PK
  message_id    TEXT FK → comms_messages.id   -- owning message/task (many per message)
  path          TEXT                          -- file path or URL
  type          TEXT                          -- md|code|pdf|image|json|url|snippet
  title         TEXT
  summary       TEXT                          -- agent-authored at creation
  token_count   INTEGER                       -- token size of the body
  created_at    TEXT
  created_by    TEXT                          -- agent | user
  last_edit_at  TEXT
  last_edit_by  TEXT                          -- agent | user
  version       INTEGER
  supersedes    TEXT FK → comms_artifacts.id  -- artifacts evolve
```

The artifact's **board / scope** (global / project / feature id) are NOT stored on
the row — they come from the owning message via `message_id` (which already has
`board` + `scope`). The card shows them through that join; duplicating them on the
artifact would risk drift. Index `message_id` for the per-task file-set lookup that
the serial-DAG prompt builder (§B3.5b) does.

**Step 1 — filtered view (uses current single-artifact columns):**
- Per-board **Tickets ⇄ Artifacts** toggle. Search bar is context-aware
  (messages when Tickets, artifacts when Artifacts).
- Artifacts view = messages that have an artifact, rendered as cards
  (grid / stacked) using whatever metadata already exists. Ships before the table.

**Step 2 — promote to first-class (`comms_artifacts` table):**
- Migrate to the table above; back-fill existing `artifact_*` columns as one row each.
- `/comms/attach` accepts a list of artifacts; the `comms-post` skill fragment
  carries `summary` (+ title) so the agent populates them at creation time.
- A task message references its file set via its `comms_artifacts` rows — this is
  what the serial-DAG per-task prompt builder (§B3.5) reads.
- Enables artifact versioning, cross-board reference, "used-by-run" counts.

---

## 5. Recommended sequencing

```
NOW   ─ A1 verify global/project terminals (live smoke test)   [unblocks confidence]
        C1 install evaluator (Mode 3 becomes real)             [unlocks the DAG path]

NEXT  ─ A2 live progress on board   +   B3 flow progress on board
        C2 step 1: artifacts filtered view

THEN  ─ B3.5 serial DAG: evaluator emits task DAG → serial_dag_loop walks it
              one agent at a time (board-native flow, Mode 2b)
        (B1 + B2 linear-flow launch can land here too — reuse /runner/start)

LATER ─ B4 + B5 + B6: flip serial → parallel DAG scheduler   [the big one]
        C2 step 2: first-class comms_artifacts table (many-per-task)
        A3 antigravity · A4 editable prompts · A5 spawn durability · C4 embed signal
```

Rationale: finish making **what exists** trustworthy and visible (single-agent +
evaluator + progress + artifacts view) first. Then **flow launch (B1/B2) is NOT a
new engine** — the supervisor pipeline already exists and runs today from the
FlowControlBar Start button; B1/B2 just point the board at the same
`/runner/start`. The genuinely **new engine is the DAG scheduler (B4–B6)** —
`scheduler_loop` is written but dead. Do not wire the DAG until plain flow launch
(reusing the existing pipeline) is proven — same lesson as the reverted Phase 2b.

---

## 6. Open decisions

1. **Flow launch reuse vs new path** — does board "Start flow" call the existing
   `/runner/start` supervisor pipeline (recommended: reuse), or a board-specific
   runner?
2. **Artifacts: filtered view first, or jump to first-class table?**
   (recommended: filtered view first.)
3. **DAG default-on or behind a flag?** (recommended: `dag` flag until proven.)
4. **Antigravity** — interactive-only (`agy` + prompt inject) now, or wait for the
   full headless `agy` syntax?

---

## 7. Acceptance criteria for "full functional board"

- [ ] From a feature **and** a project/global board: single agent runs, terminal
      opens, agent replies on the board, Stop kills it. (Mode 1)
- [ ] From a board: choose a flow + rigor, Start → the FSM pipeline runs with
      visible per-stage terminals and **stage progress shown on the board**. (Mode 2)
- [ ] From a board: Evaluator analyzes the board → posts an artifact + spawns
      `task` messages with `depends_on` + per-task artifacts. (Mode 3)
- [ ] **Serial DAG:** ready tasks run one at a time in dependency order, each
      agent gets its own task text + file set, completing a task unblocks
      dependents. (Mode 2b — serial)
- [ ] **Parallel DAG:** independent ready tasks run concurrently with isolation,
      fan-in on completion. (Mode 2b — parallel; B4–B6)
- [ ] Live progress: every run streams more than started/done to the board.
- [ ] Artifacts have their own view with searchable, metadata-rich cards.
- [ ] No silent failures: spawn drops retry; embedding-unavailable is surfaced.
