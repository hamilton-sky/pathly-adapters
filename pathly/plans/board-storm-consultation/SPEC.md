# Board-Storm Consultation Mode — Spec

**Feature:** `board-storm-consultation`
**Status:** Proposed (not built)
**Author:** drafted from `pathly/plans/comms-board/_archive/CONSULTATION.md` Part 4, re-grounded in the live codebase
**Supersedes:** the archived "Phase 5 / board-storm" notes — this spec replaces the "enters the team FSM at PLAN" hand-off with the **current Goals → Task-DAG → executors** model.

---

## 1. What this is

A **chat-like thinking mode** that runs *before* you commit to a pipeline. You open a blank consultation, write a rough request, and a headless **consultant agent** replies with a **document** (questions, an architecture sketch, a trade-off table, a draft spec) — not a chat bubble. You annotate the document, send it back, and the agent revises it. You loop until it converges, then **convert** the session into a real **goal** on the comms board with its artifacts attached — which then flows straight into the existing `decompose` → `run` machinery.

The unit of communication is the **artifact**, not the message.

### The distinction that drives every design decision

```
Chat:        say → reply → say → reply        (ephemeral, linear, stream of messages)
Board-storm: say → DOCUMENT → annotate →       (persistent, structured, a document evolves)
             revised DOCUMENT → annotate → …
```

Mental model to invoke in the UI: **"reviewing a document with a collaborator"** — not "chatting with an AI" and not "running a pipeline stage". The artifact is the primary visual element; the message thread is secondary; the send action reads as "Submit review," not "Send message."

### Why it fills a real gap

Today Pathly has no "think out loud before committing" step. You either already know what to build and start a pipeline, or you decompose a goal (which assumes the goal is already well-formed). There is no structured back-and-forth to *shape* a vague idea into a goal. Board-storm is that step, and — critically — it **does not dead-end**: it produces real artifacts that seed a goal, so the eventual builder starts with far more context than a cold goal gives it.

---

## 2. Scope

### MVP (this spec's must-ship)

1. "New consultation" entry point in HQ / Command Center.
2. User posts a request → headless consultant agent produces a **questions** artifact.
3. User replies (threaded reply on the artifact) → agent produces an **architecture** (or other) artifact.
4. Loop until the user is satisfied.
5. **Convert** → creates a `type=goal` board message scoped to a feature name, with the consultation artifacts attached as `comms_artifacts` + dropped into `pathly/plans/<feature>/`.

### Deferred (explicitly out of MVP)

- **Inline per-line annotation editor** — v1 uses threaded replies on the artifact message. The richer annotation path **reuses the existing comment system** (see §9) and is a fast-follow, not MVP.
- Diagram rendering beyond fenced ASCII / mermaid code blocks.
- Multiple concurrent consultant agents / panel-of-experts.
- Auto-conversion of `implementation_plan` artifact directly into a seeded task-DAG (MVP stops at "goal + artifacts"; the user then runs the normal `decompose`).

---

## 3. Architecture — reuse vs. new

The whole point is that **most of this already exists**. The consultant is a *prompt* concern, not an infrastructure concern.

### Reuses (no new infrastructure)

| Capability | Existing component |
|---|---|
| Board storage + scoping | `comms_messages` / `comms_artifacts` (`db/queries/comms.py`) |
| Headless agent invocation | `supervisor/board_run.py::start_board_run` (board-lock + skill compose + async spawn) — same path `single`/`planner` decompose uses |
| SSE to Studio | `/events/comms` (`blueprints/comms` + `sse.py::_broadcast_comms`) |
| Skill composition | `skills/compose.py` (add one `consult/*` skill to `composition.yaml`) |
| Artifact display + annotation | the **Markdown Editor** (`MarkdownEditor`), `DraftDiffViewer`, `CommentsPanel`, and the `.comments.json` sidecar format already in the working tree |
| "Send doc to a headless agent, get a file back" | the existing **prompt-action preset** pattern (`commentUtils.ts` SPLIT/ANALYZE templates → `{{FILE}}.draft` / `.analysis`) |

### New (what we actually build)

| Piece | Where it lives | Notes |
|---|---|---|
| `consult.flow.yaml` | `core/flows/` | minimal FSM: `OPEN → THINKING → AWAITING → … → CONVERTING → DONE` |
| `consult` agent role | `core/agents/planning/consult.md` | "senior architect; ask questions, draw diagrams, **do not write code**" |
| `consult` skill | `core/skills/planning/consult.md` (+ manifest entry) | turns request + prior artifact + annotations → next artifact |
| consultation session state | `app_settings` rows, key `consult:<session_id>` | avoids a new table (mirrors the board_scope decision in the archived arch review) |
| `/consult/*` routes | `blueprints/comms/consult.py` (new domain file, ≤400 lines) | one HTTP domain = one file, per the SOLID rules |
| Studio consultation surface | `components/HQ/Consult/` | own subfolder per component, ≤150 lines each |

> **SOLID note:** `/consult/*` is its own domain — give it `blueprints/comms/consult.py`, do **not** append to `goals.py` or `messages.py`. Supervisor/db imports go **inside** the route functions (lazy), like every other route handler.

---

## 4. Data model

No new tables. A consultation is a lightweight session plus board messages.

### Session (in `app_settings`)

Key: `consult:<session_id>` → JSON:

```json
{
  "session_id": "cns-ab12cd34",
  "board": "consult",
  "scope": "cns-ab12cd34",
  "project_root": "C:/Users/Yafit/pathly-adapters",
  "state": "AWAITING",
  "request": "I want a notification system across features",
  "artifact_ids": ["msg-...", "msg-..."],
  "created_at": "<stamped by caller, not in-script>"
}
```

- **`board: "consult"`** — a new board value distinct from `feature`/`project`/`global`, so consultation chatter never pollutes a real feature board and has its own visual skin.
- **`scope: <session_id>`** — keeps each consultation isolated and reuses all existing scope-based board queries and SSE routing unchanged.

### Artifacts (as board messages)

Each consultant turn posts a `comms_messages` row:

- `type = "artifact"` (already a known board type)
- `from_agent = "consult"`
- `text` = the artifact body (markdown)
- a metadata tag for the artifact kind — `artifact_kind ∈ {questions, architecture, tradeoffs, risks, draft_spec, implementation_plan}` (store in the message's existing metadata/extra column; do not add a column if one already serves).

Human replies are ordinary `type="note"` messages on the same scope, linked to the artifact via the existing reply/thread mechanism.

---

## 5. The consultation FSM (`consult.flow.yaml`)

A minimal machine — separate from the 8-stage team pipeline. It is **turn-based and human-gated**, not a visible-PTY auto-pipeline.

```
states: [OPEN, THINKING, AWAITING, CONVERTING, DONE]

OPEN        user posts first request → launch headless consultant → THINKING
THINKING    consultant runs (headless, non-blocking); posts an artifact → AWAITING
AWAITING    human reads / annotates / replies
              → THINKING     (reply sent: "revise / continue")
              → CONVERTING   (human clicks "Convert to goal")
CONVERTING  create goal + attach artifacts + write plan files → DONE
DONE        terminal
```

```yaml
version: 1
flow: consult
storage_path: pathly/plans/{topic}/      # topic = feature name chosen at CONVERTING
states: [OPEN, THINKING, AWAITING, CONVERTING, DONE]
transitions:
  OPEN:       [THINKING]
  THINKING:   [AWAITING]
  AWAITING:   [THINKING, CONVERTING]
  CONVERTING: [DONE]
  DONE:       []
agent_map:
  THINKING: planning/consult
role_map:
  THINKING: consult
```

Unlike `consultation.flow.yaml` (the heavy decomposer), this flow does **not** march through fixed roles. It parks in `AWAITING` until the human acts. There is no review/test/retro — just *discuss → decide → hand off*.

> **Distinguish the two flows clearly** (they will be confused):
> - `consultation.flow.yaml` — **goal decomposer**, runs PO→architect→researcher→designer→planner on an *existing* goal, visible PTYs, seeds a DAG. (Live today.)
> - `consult.flow.yaml` — **board-storm thinking mode**, headless single consultant, turn-based, produces artifacts, ends by *creating* a goal. (This spec.)

---

## 6. The consultant agent

A new role + skill. The agent operates in **"consultant mode"**: it asks questions, sketches diagrams, and analyzes trade-offs. **It must not write code or modify project files** — its only output is an artifact posted to the board.

`core/agents/planning/consult.md` (model: `opus` — this is high-leverage thinking):

> You are a senior system architect running a pre-pipeline design consultation.
> Your job is to help the human shape a vague idea into a well-scoped goal.
> You respond with exactly **one artifact** per turn — never prose chat.
> You never write or edit code or project files. You ask sharp questions,
> draw ASCII/mermaid diagrams, and lay out trade-offs.

### Artifact types it can produce

| Kind | Contents | When |
|---|---|---|
| `questions` | 5–8 clarifying questions | request is vague (usually turn 1) |
| `architecture` | ASCII/mermaid diagram + component list + data flow | technical shape needs agreeing |
| `tradeoffs` | side-by-side of 2–3 approaches | multiple valid solutions |
| `risks` | what could go wrong | before committing to a risky path |
| `draft_spec` | feature spec + user stories + acceptance criteria | design is converging |
| `implementation_plan` | phased plan with file targets | ready to hand off |

The agent picks the kind based on conversation state; the skill instructs it to **start with `questions` when the request is underspecified**.

---

## 7. HTTP endpoints (`blueprints/comms/consult.py`)

All routes lazy-import supervisor/db inside the handler.

```
POST /consult/start      { request, project_root }
  → create session (app_settings), board="consult", scope=session_id
  → start_board_run(... skill="planning/consult", agent="consult", instructions=request)
  → 200 { session_id, board, scope }

POST /consult/reply      { session_id, artifact_id, text }
  → post human note; relaunch consultant with (request + latest artifact + this reply)
  → 200 { ok, run_id }

POST /consult/convert    { session_id, feature_name }
  → create type=goal message scoped to feature_name
  → attach session artifacts (comms_artifacts) + write pathly/plans/<feature_name>/ files
  → 200 { ok, goal_id, feature: feature_name }

GET  /consult/session/:id   → session state + ordered artifacts
GET  /events/comms (existing) → already streams this scope; add a CONSULT_ARTIFACT event kind
```

`/consult/start` and `/consult/reply` are thin wrappers over `start_board_run` — the same async, board-locked spawn helper the `single` executor and `planner` decompose already use. No new spawn machinery.

### Guards (mirror the goal-run guards)

- `board_busy` (409) — a run already holds the lock for this scope.
- `not_found` (404) — unknown `session_id` on reply/convert.
- `bad_feature_name` (400) — convert needs a non-empty, filesystem-safe `feature_name`.

---

## 8. SSE

Reuse `/events/comms`. Add one event kind so Studio can react in real time:

| Event | Payload | Purpose |
|---|---|---|
| `CONSULT_ARTIFACT` | `session_id, message_id, artifact_kind, scope, phase` | a new artifact was posted; Studio renders it |

Phases (`running`/`awaiting`/`converting`/`done`) drive the "Agent thinking…" indicator, mirroring how `goal_decompose` phases already drive `markGoalRunPhase`.

---

## 9. Studio UI

New surface under `components/HQ/Consult/`. Each component its own subfolder, ≤150 lines, `.module.css` sibling, **no inline styles**, responsive to ≤200px (the standard Studio rules).

```
Consult/
  ConsultPanel/            shell: thread on the left, artifact on the right
  NewConsultButton/        HQ entry point ("New consultation")
  ConsultRequestBar/       the "Start with a request…" compose bar
  ArtifactCard/            renders one artifact (markdown), with [Reply] [Open in editor] [Convert]
  ConsultThread/           ordered request + artifacts + replies
  hooks/
    useConsultSession.ts   data: load session + subscribe to CONSULT_ARTIFACT SSE
    useConsult.ts          UI state: which artifact is selected, compose text
```

Store: extend `commsStore` (or a sibling `consultStore`) with `startConsult`, `replyConsult`, `convertConsult`, and a `consultPhase` map driven by SSE — directly mirroring the existing `decomposeGoal` / `markGoalRunPhase` pattern in `commsStore.ts`.

### Annotation loop — reuse the comment system (fast-follow, not MVP)

The richest interaction — annotate the artifact, then send the annotations back — should **not be built from scratch**. The working tree already has:

- `.comments.json` sidecars: `{ comments: [{ id, lineNumber, lineText, body, resolved, color, createdAt }] }`
- `CommentsPanel` + `DraftDiffViewer` for viewing/threading comments against a markdown file
- the **prompt-action preset** mechanism (`commentUtils.ts`) that already does *"send this markdown file to a headless agent and get a transformed file back"* (SPLIT → `.split.draft`, ANALYZE → `.analysis`)

So the annotation path is: **"Open in editor"** writes the artifact to `pathly/plans/<scope>/<artifact>.md`, the user comments on it with the existing `CommentsPanel`, and a **"Send to consultant with comments"** action compiles `artifact + .comments.json` into the next consultant invocation (a new prompt-action preset). The consultant reads "here is the doc + the human's per-line comments → produce the next artifact." This is a thin new preset over an existing pipe, not a new editor.

---

## 10. Convert-to-goal (the keystone)

`CONVERTING` is what makes this more than a chat toy. On convert:

1. **Create the goal** — a `type=goal` `comms_messages` row, `scope = feature_name`, `board = "feature"`, `text` = the converged request / `draft_spec` summary.
2. **Carry the artifacts** — attach each session artifact as a `comms_artifacts` row on the goal, and write them into `pathly/plans/<feature_name>/`:
   - `draft_spec` → `USER_STORIES.md`
   - `implementation_plan` → `IMPLEMENTATION_PLAN.md`
   - `architecture` → `ARCHITECTURE_PROPOSAL.md`
   - `questions` / `tradeoffs` / `risks` → `pathly/plans/<feature_name>/consult/` for reference
3. **Hand off to the existing machinery** — the user now has a real goal that already carries rich context. They proceed with the **normal** flow:
   - `POST /comms/goals/decompose` (`mode=planner` or `mode=consultation`) to seed the task-DAG, **or**
   - `POST /comms/goals/run` (`team` executor) if the artifacts already contain a usable plan.

This is the clean integration point: board-storm produces a goal; everything downstream is unchanged.

---

## 11. Acceptance criteria

```
GIVEN  an empty consultation
WHEN   the user posts a vague request
THEN   within one agent turn a `questions` artifact appears on the consult board
AND    the consult session state is AWAITING

GIVEN  an artifact in AWAITING
WHEN   the user replies with answers
THEN   the consultant relaunches with (request + prior artifact + reply)
AND    a new artifact appears, ordered after the reply

GIVEN  a converged session with a draft_spec artifact
WHEN   the user clicks Convert and names the feature
THEN   a type=goal message exists scoped to that feature name
AND    USER_STORIES.md / IMPLEMENTATION_PLAN.md exist under pathly/plans/<feature>/
AND    the goal is immediately eligible for /comms/goals/decompose

GIVEN  the consultant agent runs
WHEN   it produces any artifact
THEN   no project source files were created or modified (consultant is read/think-only)

GIVEN  a consult run already holds the board lock for the scope
WHEN   a second /consult/reply arrives
THEN   it returns 409 board_busy (no double-spawn)
```

---

## 12. Phasing

| Phase | Deliverable | Rough size |
|---|---|---|
| **P1** | `consult.flow.yaml` + `consult` agent/skill + `/consult/start`,`/reply`,`/session` over `start_board_run`. Testable via curl: request → questions artifact → reply → next artifact. | small (reuses board_run) |
| **P2** | `/consult/convert` → goal + plan files + `comms_artifacts`. Closes the loop into the goals model. | small |
| **P3** | Studio `Consult/` surface: thread + artifact card + reply, SSE-driven phase indicator. | medium |
| **P4** | Annotation loop via the existing `CommentsPanel` + a "send with comments" prompt-action preset. | medium |

P1+P2 deliver the entire backend value and are fully curl-testable with zero Studio work — ship them first, exactly as the comms-board backend shipped before its UI.

---

## 13. Open questions

1. **Consultant model** — `opus` for quality vs `sonnet` for cost? Default `opus`; this is low-volume, high-leverage thinking.
2. **Session GC** — when are abandoned `consult:<id>` `app_settings` rows / `consult` board messages pruned? Propose: a `mode=full` sweep in the existing `/comms/consolidate` pass.
3. **Convert target** — always `board="feature"`? Or allow converting into an existing feature's board as an additional goal? MVP: always a fresh feature scope.
4. **Diagram rendering** — MVP renders fenced ```mermaid``` / ASCII as-is in `ArtifactCard`; live mermaid rendering is a P3+ polish.
5. **Multiple artifacts per turn** — forbidden in MVP (one artifact per turn keeps the thread legible). Revisit if users want "questions + risks together."

---

*Spec v1 — board-storm consultation mode. Re-grounded against the live Goals → Task-DAG → executors model; the consultant is a prompt concern over existing board-run + comms infrastructure.*
