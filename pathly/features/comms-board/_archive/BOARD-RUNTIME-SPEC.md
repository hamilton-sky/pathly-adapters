---
name: Board Runtime Spec
status: DESIGN — user stories + locked decisions + building-block backlog
date: 2026-06-15
---

# Board Runtime — Product Spec

The communication board becomes the **launch surface** for Pathly: a user drops artifacts +
text on a board (global / project / feature), classifies it, and **runs** the board — either a
single agent, a flow, or an automatic evaluator. This spec turns the vision into sequenced,
shippable building blocks, with every open gap resolved as a decision.

It builds on what already works (verified 2026-06-15): the board backend (post/get/search/tasks/
scope/permissions/SSE), the supervisor→FSM run loop (click Start → STORM→DONE), agents posting
back to the board (Gap 1), and the P2 DAG scheduler primitives.

---

## 1. Locked decisions

| # | Decision | Rationale |
|---|---|---|
| **D1 — Ownership** | **One active runner per board**, lock keyed on `(board, scope)`. **global/project = single-agent only** (no flows). **feature = one runner at a time: agent XOR flow.** | Eliminates the single-agent-vs-flow conflict by construction. Maps onto the existing one-run-per-topic model. Different levels are different boards → run independently. |
| **D2 — Evaluator output** | The evaluator posts **(a)** an analysis md artifact **and (b)** concrete `type=task` posts (or a "recommended flow" note) onto the board. The user runs them with the normal controls. **No separate "options→action" layer.** | Reuses the existing task/DAG/flow machinery; nothing new to execute the choice. |
| **D3 — File storage** | Store **path/URL in the DB**; bytes live under the project `pathly/` tree: `pathly/plans/<feature>/artifacts/` (feature), `pathly/artifacts/global\|project/` (higher levels). Preview reads bytes via the existing `readFile` IPC. | Colocated with context, git-trackable, no new blob store. |
| **D4 — Controls** | **Drop pause.** Board controls = **start / stop / ff / back**. stop=`/runner/abort` (closes agent), ff=`/runner/advance` (skip stage), back=`pathly-back` (roll a state). | "stop" halts at the last completed stage (already in STATE.json); "start" resumes. Removes mid-flow-state persistence — the hardest part. |
| **D5 — Controls live on the board** | Runner controls move **off the cards, onto the board** (board-scoped control bar). | The runner is a property of the board, not a message card. |
| **D6 — Deferred polish** | classify-grid (colored thumbnail grid + glow), multi-section project folders, worktree parallelism — **later**. | Not needed for a working V1. |

---

## 2. Execution model

The board controller is the existing **`supervisor/`** package (api → orchestrator `_loop` →
terminal PTY spawn) driven by the **FSM** (`fsm_ops`). The board adds two things on top:

```
 BOARD (global | project | feature)
   │  user: drop artifacts + text → classify → RUN
   ▼
 BOARD CONTROLLER  (thin layer over supervisor)
   ├─ acquire (board,scope) run-lock  ──► reject if already running (D1)
   ├─ mode = single-agent | flow | evaluator
   │
   ├─ single-agent ─► spawn ONE PTY agent with a configured prompt.
   │                   FSM answers in BOARD-INFO mode (board context, NO next-stage). [NEW]
   │                   Allowed at global / project / feature.
   │
   ├─ flow ─────────► supervisor runs the selected flow for this feature.
   │                   If BUILDING tasks exist → DAG scheduler drains them. [P2]
   │                   feature only.
   │
   └─ evaluator ────► spawn the evaluator agent (when no task and no flow chosen).
                       It analyzes the board, posts an analysis artifact + tasks. [NEW agent]
```

Two new behaviors, everything else reused:
- **BOARD-INFO FSM mode** — `/next_action` variant returning the injected board context with no
  flow transition (for single-agent runs).
- **The evaluator agent** — a new role + skill.

---

## 3. User stories

> Format: *As a user, I can … so that …* — each maps to building blocks in §5.

**US1 — Compose & post with artifacts.** I can attach one or more files to a board input, see
them as thumbnails (hover → "×" to remove), type text, classify the message type, and send. (V1:
basic attach; multi-thumbnail tray is a building block; classify-grid deferred.)

**US2 — Three isolated context levels.** I can read/post at global, project, or feature level,
and deleting on one level never affects another. *(Already works.)*

**US3 — Board-scoped controls.** I see start / stop / ff / back on the **board** (not the card),
and they drive the board's single active runner. *(D4, D5.)*

**US4 — Run a single agent on any board.** I click a board's "single agent" button, configure its
prompt (reusing the Monitor's config modal), and it spawns one visible agent with the board
context injected. The FSM gives it board info, not a flow. Works at all three levels. *(D1 allows
this everywhere.)*

**US5 — Run a flow on a feature board.** On a feature board I select a flow and run it; agents
execute the flow's phases, each posting its artifact to the board. If the planner has posted
BUILDING tasks, the DAG scheduler runs them. *(feature only, D1.)*

**US6 — Auto / fast mode.** I can run a flow fully automatically until DONE, and stop it at any
time (resume by starting again). *(Reuses early-advance + abort; no pause.)*

**US7 — Evaluate a board with one click.** If I run a board that has no task and I haven't picked
a flow, the system spawns the **evaluator**: it analyzes the board's info, classifies it
(code / research), optionally scouts, then posts (a) an analysis artifact and (b) concrete tasks
or a recommended flow — which I then run. *(D2.)*

**US8 — Tasks drive the work.** A `type=task` on a board is a unit of work with a lifecycle state
(`pending → in_progress → done/failed/blocked`). Running the board executes ready tasks per the
selected flow; I can delete a task anytime (removes it from the DB for that board).

**US9 — Human-in-the-loop consult.** When an agent needs clarification it surfaces a concern on
the board: a short summary + an artifact + options to choose. *(Reuses `type=question`/escalate.)*

**US10 — Inspect an artifact.** I click an artifact and see a modal with a large preview
(image / md / pdf); for md there's a "notebook" action. *(Preview via `readFile` IPC.)*

---

## 4. Concurrency & ownership (resolves the conflict)

- The board holds **one run-lock per `(board, scope)`**. RUN acquires it; stop/abort/finish
  releases it. A second RUN on a locked board is rejected with a clear message.
- **global / project**: only the single-agent mode can acquire the lock (no flows).
- **feature**: agent XOR flow — whichever acquires the lock owns the board until it ends.
- Distinct levels never share a lock, so a global single-agent and a feature flow run in parallel
  without interaction (beyond reading each other's injected board context — which is the point).

---

## 5. Building-block backlog (sequenced, small, shippable)

Each block is independently verifiable. Phases are ordered so the **earliest blocks deliver a
runnable board with the least machinery** (single-agent first — it needs no flow). ✅ reuse · 🆕 new.

### Phase A — Foundation (tiny, unblocks everything)
- **A1** ✅ Fix `post_message` to set `task_status='pending'` for `type=task` (today `?ready=true`
  returns 0 — verified). *Done when:* posting a dep-free task makes it appear in `GET /comms/tasks?ready=true`. **S**
- **A2** 🆕 Per-board **run-lock** in the supervisor keyed on `(board, scope)`; RUN acquires,
  end releases; 409 on contention. *Done when:* a second RUN on a busy board is rejected. **S**
- **A3** 🆕 Artifact storage convention: write uploaded bytes to `pathly/.../artifacts/`, store the
  relative path on the message (reuse `artifact_path`). *Done when:* an attached file lands on disk
  and the row carries its path. **S–M**

### Phase B — Board controls (make the board the control surface)
- **B1** 🆕 Board control bar (start / stop / ff / back), board-scoped, replacing the card controls.
  Wires to `/runner/start`, `/runner/abort`, `/runner/advance`, `pathly-back`. *Done when:* the four
  controls drive a run from the board. **M**

### Phase C — Single-agent mode (the MVP "run" — no flow needed)
- **C1** 🆕 FSM **BOARD-INFO mode**: a `/next_action` variant (or flag) that returns the injected
  board context with **no** flow transition. *Done when:* a call returns board context + a "no-flow"
  marker. **M**
- **C2** 🆕 "Single agent" button on every board + prompt-config modal (reuse `ConfigurePhaseModal`).
  Spawns one PTY agent with the configured prompt + board context, holding the run-lock. *Done when:*
  clicking it runs one agent against the board at any level. **M**

### Phase D — Flow mode on a feature board
- **D1** 🆕 Flow selector on the feature board → RUN starts the chosen flow via `/runner/start`.
  *Done when:* selecting a flow + RUN drives that flow. **M**
- **D2** ✅ Wire the **P2 DAG scheduler** into BUILDING (behind the existing `dag` flag) so a feature
  flow with posted tasks drains them. *(This is the Phase-2b work, to be redone carefully.)* *Done
  when:* a feature with a task DAG builds all tasks then advances. **M–L**

### Phase E — Evaluator
- **E1** 🆕 Create the `evaluator` agent (role contract) + skill: analyze board → classify
  code/research → (optional) scout → post an analysis artifact + `type=task` posts / recommended
  flow. *Done when:* running a no-task board posts an analysis + actionable tasks. **M**
- **E2** 🆕 RUN routing: no task + no flow chosen → spawn evaluator (single-agent BOARD-INFO mode).
  *Done when:* the evaluator path triggers automatically. **S**

### Phase F — Artifact UX
- **F1** 🆕 Multi-attach thumbnail tray in the input (hover-"×", up to N). *Done when:* several files
  attach and render as removable thumbnails. **M**
- **F2** 🆕 Artifact preview modal (image / md / pdf) via `readFile` IPC + a "notebook" action for md.
  *Done when:* clicking an artifact opens a previewing modal. **M**

### Phase G — Human-in-the-loop consult
- **G1** ✅ Consult surface: an agent posts `type=question` with options + a summary + an artifact;
  the user answers on the board. *(Mostly reuse; wire answer → run.)* *Done when:* an agent question
  with options renders and the answer reaches the run. **M**

### Deferred (D6)
classify-grid + glow banner · multi-section project folders · worktree (same-lane) parallelism ·
pause/resume.

---

## 6. What's reused vs new (at a glance)

**Reused:** board CRUD/search/tasks/scope/permissions/SSE, supervisor→FSM loop, agents-post-to-board,
DAG primitives + scheduler core, ConfigurePhaseModal, `readFile` IPC, start/abort/advance/back,
rigor levels, `type=question`/escalate.

**New:** run-lock (A2), board control bar (B1), FSM board-info mode (C1), single-agent board button
(C2), flow selector (D1), DAG wiring (D2), evaluator agent+skill (E1/E2), multi-attach tray (F1),
artifact preview modal (F2).

---

## 7. Coverage check

The story now covers: the three start modes (single-agent / flow / evaluator), the three levels with
ownership rules, board-scoped controls, artifacts (store + preview), tasks-as-state, and consult.
**Resolved gaps:** ownership (D1), evaluator bridge (D2), file storage (D3), controls (D4/D5).
**Deliberately out of scope (V1):** classify-grid, multi-section folders, worktree parallelism, pause.
