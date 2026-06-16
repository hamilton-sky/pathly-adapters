# Comms Board — Design Consultation

**Feature:** Communication Board  
**Spec version reviewed:** 4.0  
**Date:** 2026-06-10  
**Reviewers:** Architecture · Product Owner · Designer  

---

## Part 1 — Architecture Consultation

### 1.1 What the spec gets right technically

The foundation is sound. Using sqlite-vec inside the existing `pathly.db` is the
correct call — no new processes, no new services, no operational overhead. The
embedding pipeline design (async background thread, pre-warm at startup) is
appropriate for the workload. The FSM injection point in `fsm_ops.py:build_prompt()`
is clean and additive — no existing behaviour changes.

The three-scope retrieval (`feature k=3, project k=2, global k=1`) is a
sensible starting point. It keeps the injected block small enough to not
dominate the agent's context window.

### 1.2 Concrete risks found in the actual codebase

**Risk 1 — sqlite-vec extension load (HIGH)**

The extension must be loaded on EVERY connection open because Python's sqlite3
module does not persist loaded extensions across reconnects. The current
`connection.py:get_db()` uses a connection cache (`_conn_cache`) — so the
extension only needs to be loaded once per cached connection. But:

```python
# connection.py — the place to add sqlite-vec loading
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
# ← sqlite-vec must be loaded HERE, before _run_migrations
# because migrations create the VIRTUAL TABLE which needs the extension
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)  # re-disable for security
_run_migrations(conn)
```

Critical ordering: `sqlite_vec.load(conn)` MUST happen before `_run_migrations(conn)`
because the migration that creates `comms_embeddings USING vec0(...)` requires
the extension to already be loaded.

On Windows, `enable_load_extension` may be disabled if SQLite was compiled
without it. Need a capability check on server startup with a clear fallback:

```python
try:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _VEC_AVAILABLE = True
except Exception:
    _VEC_AVAILABLE = False
    logging.warning("sqlite-vec not available — comms board uses recency-only retrieval")
```

**Risk 2 — write_state() overwrites board_scope (HIGH)**

The real `write_state()` in `db/queries/fsm_state.py` does:
```python
conn.execute(
    "INSERT OR REPLACE INTO fsm_state (project_root, feature, state_json, ...) VALUES (?, ?, ?, ?)",
    (..., json.dumps(state_dict), ...)
)
```
It serialises the entire `state_dict` it receives. If the caller doesn't include
`board_scope`, it gets silently dropped on the next write.

Fix: the FSM must read the current state, merge the `board_scope` key, and pass
the merged dict to `write_state()`. Or: store `board_scope` separately in a
dedicated `app_settings` row rather than in STATE.json. The `app_settings` table
already exists and supports arbitrary key-value pairs.

**Recommendation:** Store `board_scope` in `app_settings` keyed by
`"board_scope:{project_root}:{feature}"`. This completely avoids the merge problem.

**Risk 3 — Embedding model download on first use (MEDIUM)**

`sentence-transformers` downloads `all-MiniLM-L6-v2` (~90MB) to
`~/.cache/huggingface/hub/` on first use. This blocks the first `/comms/post`
call for 10–30 seconds on a cold machine with no warning to the user.

Fix: at server startup, background-thread the model warm-up:
```python
# In http_server/app.py, after blueprint registration:
import threading
threading.Thread(target=_warm_embedding_model, daemon=True).start()
```
If the user posts before the model is warm, store the message immediately
(available for exact-match retrieval) and queue the embedding for when the
model is ready.

**Risk 4 — vec0 CREATE VIRTUAL TABLE syntax (MEDIUM)**

The `FLOAT[384]` syntax is specific to `sqlite-vec v0.1.x`. If the extension
version changes, the migration fails silently. Pin the version in pyproject.toml:
```toml
"sqlite-vec==0.1.6",
```
Not `>=` — pin it until we can test upgrades explicitly.

**Risk 5 — /next_action latency (LOW)**

Three vector queries added per `/next_action` call. At the expected data volumes
(feature board: 20–200 msgs, project: 50–500, global: 10–100) each query takes
~5–20ms. Total added latency: ~60ms. Acceptable.

If the global board grows to 10k+ messages after years of use, add:
```sql
WHERE status NOT IN ('trashed', 'archived')
  AND board = ? AND scope = ?
LIMIT 2000  -- search space cap before vector comparison
```

### 1.3 Architecture decisions to lock before Phase 1

| Decision | Recommendation | Reason |
|---|---|---|
| Where to store board_scope | `app_settings` table, not STATE.json | Avoids write_state() merge problem |
| sqlite-vec load order | Before `_run_migrations()` in `get_db()` | Migration creates VIRTUAL TABLE — needs extension |
| Embedding module location | `runner/embeddings.py` new file | Keeps fsm_ops.py clean; easy to mock in tests |
| Board context injection | New `runner/comms_context.py` | Separate concern from history block |
| Model version pinning | `sqlite-vec==0.1.6` in pyproject.toml | Prevents silent breakage on update |
| Fallback when sqlite-vec absent | Recency-only retrieval (last N messages) | Graceful degradation, no crash |
| Global board location | Same `pathly.db`, `board='global', scope='global'` | Simplest; backup is backing up pathly.db |

### 1.4 Open architecture questions

1. **Should agents be allowed to write to the project and global boards directly?**
   The spec allows it. Risk: agents posting noise to the project board which is
   supposed to be high-signal decisions. Recommendation: agents can only write
   to their own feature board. Project/global writes require human confirmation
   (or explicit `force=true` flag).

2. **Where do consultation board sessions live?** (See Part 4 — Board-Storm.)
   They need a board type separate from feature/project/global.

3. **Embedding dimensions:** `all-MiniLM-L6-v2` → 384 dimensions. If we ever
   want to switch models, the `FLOAT[384]` column is locked in. Consider naming
   the migration version so a future migration can recreate the table at 768 or
   1536 dimensions.

---

## Part 2 — Product Owner Consultation

### 2.1 Is the problem real?

Yes. The context-loss problem is the #1 source of rework in multi-stage AI
pipelines. The specific patterns that waste the most time today:

```
Pattern A — The Repeated Constraint:
  You tell builder "skip X, it's v2 scope"
  → Reviewer flags X as missing
  → You tell reviewer "v2 scope"
  → Tester tries to test X
  → You explain again
  → Next feature, same conversation

Pattern B — The Blind Reviewer:
  Builder makes a deliberate trade-off mid-run
  → You acknowledge it in the terminal
  → Reviewer doesn't know → flags it as a bug
  → Pipeline retries unnecessarily

Pattern C — The Amnesia Loop:
  The same architectural mistake made in feature 2 that was made in feature 1
  because there's no mechanism to carry the lesson forward
```

All three are solved by the board. Pattern A and B are solved in Phase 1.
Pattern C requires Phase 4 (cross-feature memory). The value is real.

### 2.2 The minimum viable board

The smallest version that proves the concept works:

```
Phase 1-MVP (3 files changed, fully testable via curl):
  1. comms_messages table (no embeddings yet)
  2. POST /comms/post  →  stores message
  3. fsm_ops.py       →  inject last 5 messages into prompt (recency, no vector)

Test: post a nudge via curl → start next stage → verify prompt contains the nudge
```

This proves injection works. Add vector search in Phase 1.1. Ship Phase 1-MVP
first — it delivers 60% of the value with 10% of the implementation.

### 2.3 Acceptance criteria

**Phase 1 — Backend injection:**
```
GIVEN  a feature in BUILDING state with a message on the feature board
WHEN   /next_action is called
THEN   agent_hint.instructions contains a ## Communication Board section
AND    the message appears under the correct heading (Decision / Active / etc.)

GIVEN  a feature has board_scope { project: false }
WHEN   /next_action is called
THEN   no project-board messages appear in the prompt

GIVEN  a feature has 50 board messages
WHEN  /next_action is called
THEN   at most 6 messages are injected (3 feature + 2 project + 1 global)
AND   mandatory decisions are always included regardless of count
```

**Phase 2 — Studio CommsPanel:**
```
GIVEN  an agent posts a status message during a stage
WHEN   the human has the CommsPanel open
THEN   the message appears in real time (SSE delivery < 1s)

GIVEN  an agent posts a question with two options
WHEN   the human views the CommsPanel
THEN   the question shows with radio buttons for each option
AND    clicking an option posts an answer and marks the question resolved

GIVEN  the human collapses a panel in side-by-side mode
WHEN   a new message arrives
THEN   the collapsed strip shows an updated badge count
```

### 2.4 User stories (prioritised)

**Must ship in Phase 1:**
- As a human, I want to post a constraint during a run and have the NEXT agent
  read it automatically — without interrupting the current stage
- As a human, I want decisions I make during one stage to automatically inform
  the next stage, with no copy-paste from terminal output

**Should ship in Phase 2:**
- As a human, I want to see agent status in the Studio without watching terminals
- As a human, I want to answer an agent question from the UI, not the terminal
- As a human, I want to pin a decision so it applies to every future stage in
  this feature

**Could ship in Phase 3:**
- As a human, I want to attach a spec document to the project board so all
  builders in all features reference it automatically
- As an agent, I want to ask "what did we decide about X" and get an answer
  from the board without it being injected into my initial prompt

**Future / Phase 4:**
- As a human, I want to see all features' boards simultaneously in a command center
- As a human, I want decisions from past features to surface automatically in
  new features that touch the same subsystem

### 2.5 Priority warnings

**Do not let the command center block Phase 1.** The three-panel UI is large
and high-risk. The backend injection (Phase 1) can ship and deliver real value
with zero Studio changes — agents get smarter immediately.

**Do not let artifact ingestion block Phase 2.** PDF parsing, URL fetching,
and chunking are complex. Ship text-only messages and questions first. Artifacts
are Phase 4.

**The promote-before-delete flow is a nice-to-have.** Do not put it on the
critical path. Users can live without it for months.

---

## Part 3 — Designer Consultation

### 3.1 The mental model problem

The biggest UX risk is not the visual design — it's the **conceptual model**.
Users will try to use the board like a chat. When their message doesn't get an
instant reply, they will think it's broken.

The UI must communicate four things the user needs to understand:

```
1. This is not real-time chat.
   The agent reads this at the START of the next stage.

2. Decisions are permanent.
   They stay pinned at the top and affect every future agent forever.

3. The agent writes back here too.
   Status updates, questions, warnings — agents use this to communicate back.

4. The board is scoped.
   What you write here affects different sets of agents depending on the scope.
```

**Recommendation:** Add a subtitle to each board panel:
```
📁 PROJECT — pathly-adapters
"Agents read this at the start of each stage"
```

And a visual indicator on pinned decisions:
```
📌 DECISION  (permanent · applies to all future agents in this project)
```

### 3.2 Tab-as-toggle is unconventional — change the control

Standard tabs are mutually exclusive selectors. The multi-select toggle
behaviour the spec describes is correct in concept but will confuse users
if rendered as tabs.

**Use pill toggles (filter chips) instead of tabs:**

```
Instead of:
╔════════════════╦════════════════╦═════════════════╗
║  🌐 Global     ║  📁 Project  ● ║  🎯 Feature     ║
╚════════════════╩════════════════╩═════════════════╝
  looks like: click switches     (users expect mutual exclusion)

Use:
  (🌐 Global)  ●📁 Project●  (🎯 Feature)    [⊞]
  filled pill = panel open
  outline pill = panel hidden
  looks like: multi-select filter (users understand this)
```

Pill/chip toggles have established multi-select semantics in modern UIs
(Gmail filters, GitHub label filters, Figma layer toggles). Standard tabs do not.

### 3.3 Reduce message types from 10 to 5 user-visible types

Ten types is too many for a compose bar. The user will not remember the
difference between `nudge`, `note`, and `decision` under time pressure.

**Recommendation:** 5 user-facing types. The rest are system/agent-only:

```
User composes:
  📌  Decision    permanent, pinned, applies going forward
  📋  Task        has a lifecycle: pending → done / skipped
  💬  Note        informational nudge (replaces "nudge" in the UI)
  📎  Attach      file, URL, or snippet
  ❓  Question    expects a response (with optional choices)

System/agent posts (user reads, cannot create from compose bar):
  ✓  Status       progress update from agent
  ⚠  Warning      something suspicious, needs human decision
  💡  Discovery   interesting finding from agent
  🚨  Escalation  pipeline blocked until human responds
  ↩  Answer       reply to a question
```

This gives users 5 clear choices and agents 5 clear output types. No overlap.

### 3.4 The send bar — type AFTER writing, not before

Current spec shows type buttons above the text input. This forces the user to
decide the type before writing. Wrong order — people write first, categorise second.

**Recommended compose flow:**
```
┌──────────────────────────────────────────────────────────┐
│  Write a message...                                      │
└────────────────────────────────────────────────────────┬─┘
                                         [Send as Note ▾]
                                           ↳ 📌 Decision
                                           ↳ 📋 Task
                                           ↳ 📎 Attach
                                           ↳ ❓ Question
```
Default type: Note (lowest commitment). User changes it only when they mean
something more specific. The type dropdown is a refinement, not a prerequisite.

### 3.5 Collapse to strip — make the whole strip the click target

In the current spec, the `[▸]` button is the expand trigger. In a 48px strip,
that button will be too small. More importantly, there is only ONE reason to
click a collapsed strip: to expand it. There is no other affordance to put there.

**Make the entire strip a click target:**
```
┌──┐                      ┌──────────────────────────┐
│🌐│  ← click anywhere    │  🌐  GLOBAL              │
│  │     on this strip    │  ...expands to full width │
│② │     to expand        │                          │
│▸ │                      └──────────────────────────┘
└──┘
```
No need for a dedicated expand button. The cursor changes to `cursor: e-resize`
(or `cursor: col-resize`) when hovering the strip to signal it can be expanded.

### 3.6 The pending badge is the most important UI element in collapse mode

Without it, collapsed panels feel like discarded panels. The badge is what
communicates "there is something here requiring your attention."

```
Badge rules:
  No pending → no badge (panel feels settled)
  1+ pending → amber badge with count  ②
  1+ open questions → blue badge with ?  ?
  Any escalation → red pulsing badge   🔴  (overrides all others)
```

The escalation badge must be visible even on the fully collapsed strip.
A red pulsing indicator on a 48px strip is hard to miss.

### 3.7 Stacked mode — the collapse bar needs a height floor

In stacked mode, if all three panels are collapsed to bars, the user needs a
way to see all three at once without expanding any. The three header bars should
always be visible simultaneously — the layout should not collapse them off-screen.

**Stacked mode minimum layout:**
```
┌──────────────────────────────────────────────────────┐  ← 40px bar
├──────────────────────────────────────────────────────┤  ← 40px bar
│  Full height panel (one expanded at a time)          │
│  ...                                                 │
├──────────────────────────────────────────────────────┤  ← 40px bar
└──────────────────────────────────────────────────────┘
```
Three bars always visible; expanded panel fills remaining height. The user
clicks a bar to swap which panel is expanded.

---

## Part 4 — Board-Storm: A New Proposal

### 4.1 The gap this solves

The current Pathly storm phase is a one-shot operation:
```
User writes a brief → agent runs storm → produces storm doc → pipeline starts
```

There is no iteration. If the brief was incomplete, the storm doc is wrong,
and you don't find out until the builder is halfway through implementation.

What's missing: a way to **think out loud with AI before committing to a plan**,
without starting a full 8-stage pipeline. A structured back-and-forth ideation
session that produces artefacts (diagrams, questions, specs) rather than chat messages.

### 4.2 The concept

The user opens a blank board with no feature yet. They write a request. A headless
"consultant" agent responds with an **artefact** — not a chat message. The user
annotates or replies to the artefact. The agent reads the annotations and produces
a revised artefact. This continues until the user is satisfied, then converts the
session into a real Pathly feature with one click.

The key distinction from chat:
```
Chat:         user says something → agent replies → user replies → repeat
              (stream of messages, ephemeral, linear)

Board-storm:  user says something → agent produces a DOCUMENT
              (questions doc / architecture diagram / draft spec)
              user annotates the document → agent revises it
              (document evolves, persistent, structured)
```

The artefact is the unit of communication, not the message.

### 4.3 What the consultant agent produces

The agent operates in "consultant mode" — it asks questions, draws diagrams,
and analyses trade-offs. It does NOT write code or modify files.

**Artefact types the consultant produces:**

| Artefact | Contents | When used |
|---|---|---|
| `questions` | 5–8 clarifying questions before committing to a design | Early in session when the request is vague |
| `architecture` | ASCII system diagram + component list + data flow | When technical shape needs to be agreed |
| `tradeoffs` | Side-by-side comparison of 2–3 approaches | When multiple valid solutions exist |
| `risks` | List of things that could go wrong | Before committing to a risky approach |
| `draft_spec` | Feature spec with user stories + acceptance criteria | When the design is converging |
| `implementation_plan` | Phased plan with file targets | When ready to hand off to the pipeline |

### 4.4 The back-and-forth flow

```
Step 1 — User opens a blank board
  HQ shows a "New consultation" button
  User clicks → blank board opens with a "Start with a request..." prompt

Step 2 — User posts their request
  "I want to build a notification system that works across features"
  → POST /consult/start  { request: "..." }
  → Server launches headless claude with consultant prompt
  → Board shows "Agent thinking..." indicator

Step 3 — Agent responds with an artefact
  Agent produces a questions artefact:
  ┌─ artefact: questions ──────────────────────────────────────────┐
  │  Before I design this, I need to understand:                  │
  │                                                                │
  │  1. Should notifications be real-time (SSE) or polled?        │
  │  2. Do notifications need to persist across app restarts?     │
  │  3. Should agents be able to trigger notifications?           │
  │  4. Is there a notification centre (inbox) or just toasts?    │
  │  5. Do different notification types need different routing?    │
  └────────────────────────────────────────────────────────────────┘
  [Reply to this]  [Open in editor]

Step 4 — User replies to the artefact
  Either: inline reply in the board thread
    "SSE yes · persist yes · agents yes · both inbox+toast · yes routing"
  Or: open in editor panel → annotate each question individually
    [Open in editor] → editor panel shows artefact + annotation tool

Step 5 — Agent reads reply + produces revised artefact
  System launches another headless agent with:
    original request + original questions artefact + human's answers
  Agent produces architecture artefact:
  ┌─ artefact: architecture ───────────────────────────────────────┐
  │  Proposed: Three-layer notification system                    │
  │                                                                │
  │  ┌──────────┐    ┌──────────────┐    ┌─────────────────────┐  │
  │  │  Agents  │───▶│  HTTP POST   │───▶│  notifications.db   │  │
  │  │  Humans  │    │  /notify     │    │  (per-feature rows)  │  │
  │  └──────────┘    └──────────────┘    └──────┬──────────────┘  │
  │                                             │ SSE broadcast    │
  │                                      ┌──────▼──────────────┐  │
  │                                      │  Studio NotifPanel  │  │
  │                                      │  + Toast system     │  │
  │                                      └─────────────────────┘  │
  └────────────────────────────────────────────────────────────────┘
  [Looks good → continue]  [I want changes]  [Reply]

Step 6 — User approves or requests changes
  → Loop continues until user clicks "Start pipeline"

Step 7 — Convert to feature pipeline
  User names the feature: "feature-notifications"
  → All consultation artefacts become the feature's initial board messages
  → draft_spec artefact becomes the basis for USER_STORIES.md
  → implementation_plan artefact becomes IMPLEMENTATION_PLAN.md
  → Feature enters main Pathly FSM at PLAN state (storm is already done)
```

### 4.5 The editor panel (annotation mode)

When the user clicks `[Open in editor]` on an artefact, the right side of the
board opens an annotation view:

```
┌───────────────────────────┬────────────────────────────────────────┐
│  BOARD THREAD             │  EDITOR — questions artefact           │
│  ─────────────────────    │  ─────────────────────────────────     │
│                           │  1. Should notifications be real-time  │
│  User: "I want to build   │     (SSE) or polled?                   │
│  a notification system"   │     ┌─ comment ─────────────────────┐  │
│                           │     │ → SSE. We already have SSE    │  │
│  Agent: [questions] ←─── │     │    infrastructure.            │  │
│  selected                 │     └──────────────────────────────┘  │
│                           │                                        │
│                           │  2. Do notifications need to persist   │
│                           │     across app restarts?               │
│                           │     [+ add comment]                    │
│                           │                                        │
│                           │  3. Should agents be able to trigger?  │
│                           │     ┌─ comment ─────────────────────┐  │
│                           │     │ → Yes. POST /notify from       │  │
│                           │     │    inside agent skills.        │  │
│                           │     └──────────────────────────────┘  │
│                           │                                        │
│  ─────────────────────    │  ──────────────────────────────────    │
│  [Reply]  [Open editor]   │  [Send to agent with comments]         │
└───────────────────────────┴────────────────────────────────────────┘
```

The annotation model (v1): each numbered item in the artefact gets a comment
thread. Comments are attached to the item number. When the user clicks
"Send to agent with comments", the system compiles:
```
Original artefact + attached comments → new agent invocation
```

The agent reads: "Here is the original questions doc. Here are the user's
annotations per item. Produce the next artefact."

### 4.6 The consultation FSM

A new minimal state machine — separate from the 8-stage team pipeline:

```
States: OPEN → THINKING → AWAITING → THINKING → AWAITING → ... → CONVERTING → DONE

OPEN
  Trigger: user posts first request
  Action: launch headless consultant agent
  → THINKING

THINKING
  Agent runs (headless, non-blocking)
  Agent posts artefact to board via /consult/artifact
  → AWAITING

AWAITING
  Human reads artefact, optionally opens editor
  Human replies OR annotates+sends
  → THINKING  (if more discussion needed)
  → CONVERTING  (if human clicks "Start pipeline")

CONVERTING
  Human provides feature name
  System:
    → creates feature plan files from artefacts
    → promotes artefacts to feature board messages
    → registers feature in main FSM
  → DONE  (feature enters team pipeline at PLAN state)
```

No review, no testing, no retro. Just: discuss → decide → hand off.

### 4.7 New endpoints needed for consultation

```
POST /consult/start         { request, project_root }
  → creates consultation session, launches headless agent
  → returns { session_id, board_scope }

POST /consult/artifact      { session_id, type, content, agent }
  → agent posts an artefact to the consultation board
  → broadcasts CONSULT_ARTIFACT SSE

POST /consult/reply         { session_id, artifact_id, text, comments[] }
  → human sends reply or annotated comments back
  → launches next agent turn

POST /consult/convert       { session_id, feature_name }
  → converts session to a named feature
  → generates plan files from artefacts
  → returns { feature, redirect_to: "team pipeline" }

GET  /consult/session/:id   → current session state + all artefacts
GET  /events/consult?session_id=X  → SSE stream for real-time updates
```

### 4.8 Architecture assessment of the board-storm idea

**What's new vs what reuses existing infrastructure:**

```
Reuses (no new code needed):
  ✓ Board storage (comms_messages + comms_embeddings)
  ✓ Headless agent invocation (runner/invoke.py already exists)
  ✓ SSE broadcast system (same pattern as _broadcast_runner)
  ✓ commsStore and CommsPanel (Phase 2 already builds these)

New infrastructure needed:
  + Consultation session state (a new table or app_settings entries)
  + Consultant agent prompt (a new "consult" role + skill)
  + Plan file generation from artefacts (converts artefact content → USER_STORIES.md)
  + Editor annotation UI in Studio (the inline comment panel)
  + /consult/* endpoint set (5 new routes)
```

The consultant agent is a PROMPT concern, not an infrastructure concern. The
existing headless agent invocation mechanism works. You just need a different
system prompt: "you are a senior system architect. Ask clarifying questions.
Draw diagrams. Do not write code."

**The annotation editor is the hardest part.** Inline comments on a structured
document in Electron requires a custom renderer. The v1 simplification: skip
the editor panel initially. Instead, the user just replies to the artefact as a
threaded message in the board. The v2 editor panel is a Phase 4 enhancement.

### 4.9 PO assessment — should we build this?

**Yes. And it fills a real gap.**

Today there is no "thinking mode" in Pathly. You either know what to build and
start a pipeline, or you start a storm which is one-shot. There is no way to
iterate on a plan before committing.

The board-storm solves:
- "I have a vague idea — help me scope it before I commit to a pipeline"
- "I want a senior engineer to ask me the right questions before I start building"
- "I want to see an architecture diagram before I decide on the approach"

The conversion to pipeline is the key feature — the consultation doesn't dead-end.
It produces real artefacts that seed the feature's plan files. The builder starts
with more context than any current Pathly pipeline gives it.

**MVP for board-storm (Phase 5 scope):**
```
1. "New consultation" button in HQ
2. User types request → headless agent produces questions artefact
3. User replies → agent produces architecture artefact
4. "Start pipeline" button converts to a real feature
No editor panel in v1. Just threaded replies on board messages.
```

### 4.10 Designer assessment — should it feel like storm or like chat?

**Neither. It should feel like a document review.**

The mental model to invoke:
```
NOT: "I'm chatting with an AI"
     (implies ephemeral, informal, back-and-forth dialogue)

NOT: "I'm running a pipeline stage"
     (implies automated, hands-off, I wait for it to finish)

YES: "I'm reviewing a document with a collaborator"
     (implies: document exists, I mark it up, collaborator revises, we converge)
```

This means the visual design should feel closer to a code review interface than
to a chat. The artefact should be the primary visual element — large, readable,
prominent. The message thread is secondary. The "Send to agent" action should
feel like "Submit review" not "Send message".

The consultation board should have a different visual skin than the main comms
board to signal "this is pre-pipeline ideation, not an active pipeline."

---

## Part 5 — My Assessment (Synthesis)

After reviewing the spec, the codebase, and the new board-storm idea together:

### What this system fundamentally is

Most AI development tools treat memory as a technical problem ("how do we store
and retrieve context?"). Pathly's board treats it as a **collaboration problem**
("how do humans and agents develop shared understanding over time?").

The difference matters. Technical solutions give you RAG over conversation history.
Collaboration solutions give you a shared working surface where human intent is
explicit, agent findings are structured, and decisions are permanent.

No AI development tool in the current market has built this well. LangChain and
CrewAI have memory modules. They are opt-in, flat, extraction-based, and
single-scope. They do not model the human as an intentional author of memory.
Pathly's type system (decision vs nudge vs discovery vs warning) is the key
innovation — it gives memory structure that extraction alone cannot produce.

### The board-storm makes this system complete

Without board-storm, the comms board is a feature of the pipeline. With it, the
comms board IS the pipeline entrypoint. The user's entire relationship with
Pathly starts at the board: they write an idea, they discuss it with a consultant
agent, they see it converted into a real pipeline. The board is not a side panel —
it is the primary interface.

### The three-panel command center is a year away

The spec is correct in the design. The implementation effort for a properly
resizable, collapsible, multi-scope command center in Electron is 3–4 weeks of
focused Studio work. Don't start it until Phase 1 and Phase 2 are shipped and
validated. The backend injection is the proof of concept. The Studio is the
polish layer.

### Phase ordering recommendation

```
Phase 1    Backend injection only (3 weeks)
           Post nudges via curl → verify in agent prompts
           Zero Studio changes

Phase 2    Studio CommsPanel for one feature at a time (2 weeks)
           Message thread · question cards · SSE updates

Phase 3    Skill integration (1 week)
           Agents post status/warnings · build.md reads board

Phase 5    Board-storm consultation mode (4 weeks)
           New consultation flow · consultant agent · convert to pipeline
           (before Phase 4 — more user-facing value)

Phase 4    Cross-feature memory + command center (6 weeks)
           Three-panel layout · global board seeding · artifacts
```

Board-storm (Phase 5) before cross-feature memory (Phase 4) because the
consultation mode creates the rich board content that makes cross-feature
retrieval valuable. You need to fill the boards before you need to search across them.

---

*Consultation version 1.0 — Architecture · PO · Designer · Board-Storm proposal*
