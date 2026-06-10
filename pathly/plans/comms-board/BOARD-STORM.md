# Board-Storm — Consultation Mode Design

**Feature:** Pre-pipeline ideation through the communication board  
**Parent spec:** [SPEC.md](SPEC.md) (the comms board)  
**Status:** Design  
**Date:** 2026-06-10  
**Depends on:** Comms board Phase 1 (backend) + Phase 2 (CommsPanel)  

---

## 1. The Gap This Solves

Today Pathly has no "thinking mode." You have exactly two options:

```
Option A — You already know what to build
  → start a pipeline → 8 stages run

Option B — You are not sure
  → run STORM → one-shot storm doc → pipeline starts
  → no iteration; if the brief was incomplete the storm is wrong
  → you find out when the builder is halfway through
```

What's missing: a way to **think out loud with AI before committing to a plan**.
A structured back-and-forth that produces artefacts (questions, diagrams, specs)
rather than ephemeral chat — and that converts into a real pipeline when you're ready.

Board-storm is that mode. The user opens a blank board, posts an idea, and a
headless consultant agent responds with a **document** (not a chat message). The
user annotates or replies. The agent revises. This loops until the user is
satisfied, then one click converts the session into a pipeline-ready feature with
plan files pre-populated.

---

## 2. The Core Realization — 80% Reuse

Board-storm is not a new system. It is three things already being built plus a
thin loop:

```
┌─────────────────────────────────────────────────────────────┐
│  Board-storm  =  comms board (Phase 1)                      │
│                + headless agent invocation (ALREADY EXISTS)  │
│                + CommsPanel UI (Phase 2)                      │
│                + a small consultation loop (the only new bit)│
└─────────────────────────────────────────────────────────────┘
```

This is the entire argument for shipping it before the command center:

```
Board-storm needs:                Command center needs:
─────────────────                 ─────────────────────
✓ one board                       ✗ vector search across 100s of boards
✓ headless agent (exists)         ✗ 3-panel resizable Electron layout
✓ small thread injection          ✗ semantic top-K retrieval tuning
✓ CommsPanel (Phase 2)            ✗ collapse/reorder/drag system
✓ ~500 lines of new Python        ✗ ~4 weeks of Studio work

Board-storm FILLS boards with rich content.
The command center SEARCHES across filled boards.
You must fill before you search → build the producer first.
```

---

## 3. What Already Exists That We Lean On

| Existing component | File | How board-storm uses it |
|---|---|---|
| Headless agent invocation | `runner/invoke.py` → `invoke_agent()` | Spawns the consultant; we only change the prompt |
| Comms message store | `comms_messages` table (Phase 1) | The consultation thread lives here, `board='consult'` |
| Post endpoint | `POST /comms/post` (Phase 1) | The consultant posts artefacts through the same write path |
| SSE broadcast | `sse.py` → `_broadcast_runner` pattern | We add `_broadcast_consult` (a copy) |
| Key-value store | `app_settings` table (exists) | Holds session FSM state — no new table needed |
| Message thread UI | `CommsPanel/` (Phase 2) | The consultation view reuses it |

The only genuinely new code is the consultation loop, the conversion step, and
the consultant agent prompt.

---

## 4. Dependency Stack

```
Board-storm sits HERE ───────────────┐
                                      ▼
  Phase 5:  consult loop + convert step + consultant skill
            ▲
            │ needs a board to write to
  Phase 1:  comms_messages + POST /comms/post + SSE
            ▲
            │ needs a UI to show the thread (reuse)
  Phase 2:  CommsPanel (message thread + artefact cards)
            ▲
            │ already done
  EXISTS:   runner/invoke.py headless agent invocation
```

It needs Phase 1 and Phase 2. It does **not** need Phase 4 (vector search,
command center, cross-feature memory).

---

## 5. Build Sequence — 6 Steps With File Targets

### Step 1 — The consultant agent (a prompt, not infrastructure)

```
File: src/pathly_data/core/skills/consult.md  (new)
New role: "consultant" (opus — this is the thinking work)
Add role definition: src/pathly_data/core/agents/consultant.md
```

System prompt essence:
```
You are a senior system architect in consultation mode.
Do NOT write code or modify files.
Ask clarifying questions. Draw ASCII diagrams. Compare trade-offs.
Produce exactly ONE artefact per turn by calling:
  POST /comms/post {
    board: 'consult', scope: '<session_id>',
    type: 'artifact', artifact_type: 'questions'|'architecture'|'tradeoffs'|'draft_spec'|'implementation_plan',
    text: '<the artefact content>'
  }
Then stop. The human will respond before your next turn.
```

The agent already runs headless. We only change what it is told to do.

### Step 2 — Session state (no new table)

```
app_settings key:  consult:{session_id}
value (JSON):
  {
    "state": "AWAITING",        // OPEN | THINKING | AWAITING | CONVERTING | DONE
    "request": "build a notification system",
    "project_root": "C:/Users/Yafit/pathly-adapters",
    "turn": 2,
    "created_at": "2026-06-10T..."
  }
```

Artefacts themselves do NOT go here — they live in `comms_messages`
(`board='consult'`, `scope=session_id`). This blob is just the pointer + FSM state.

### Step 3 — The consultation endpoints

```
File: http_server/blueprints/consult.py  (new, ~150 lines)
Register in: http_server/app.py

POST /consult/start    → write request to board, launch agent, state=THINKING
POST /consult/reply    → bundle thread + reply, launch agent again
POST /consult/convert  → artefacts → feature (the magic, Step 5)
GET  /consult/session/:id → current state + all artefacts
GET  /events/consult   → SSE stream (copy of _broadcast_runner pattern)
```

### Step 4 — The loop driver

```
File: supervisor/consult.py  (new, ~100 lines)

The entire state machine:

  OPEN ──user posts request──▶ THINKING
  THINKING ──agent posts artefact, exits──▶ AWAITING
  AWAITING ──user replies──▶ THINKING            (loop)
  AWAITING ──user clicks "Start pipeline"──▶ CONVERTING
  CONVERTING ──plan files written──▶ DONE
```

### Step 5 — The conversion step (the payoff)

```
File: runner/consult_convert.py  (new, ~120 lines)
```

This is what makes the consultation not dead-end. See Section 8.

### Step 6 — Studio view (reuses Phase 2)

```
The consultation UI IS the CommsPanel from Phase 2, with:
  + a "New consultation" button in HQ
  + artefact cards rendered larger (document-style — see designer note)
  + a "Start pipeline" button → POST /consult/convert
No new panel system. No command center needed.

New files:
  components/HQ/ConsultPanel/ConsultPanel.tsx     (thin wrapper over CommsPanel)
  components/HQ/ConsultPanel/ArtefactCard.tsx      (large document-style card)
  components/HQ/ConsultPanel/useConsult.ts          (SSE + start/reply/convert)
```

---

## 6. Runtime Flow — What Actually Happens

```
1. User clicks "New consultation" in HQ
   → POST /consult/start { request: "build notifications", project_root }
   → server writes request to comms_messages (board='consult', scope=sess_42)
   → server calls invoke_agent() headless with consultant prompt
   → app_settings consult:sess_42 = { state: THINKING }
   → SSE CONSULT_UPDATE → Studio shows "Consultant thinking..."

2. Agent runs headless, and as its final action:
   → POST /comms/post { board:'consult', scope:'sess_42',
                        type:'artifact', artifact_type:'questions',
                        text:'1. SSE or polled? 2. Persist? ...' }
   → agent exits
   → /runner/terminal/result fires → state=AWAITING
   → SSE CONSULT_UPDATE → Studio renders the questions artefact card

3. User replies in the board (or annotates in editor — v2):
   → POST /consult/reply { session_id:'sess_42',
                          text:'SSE yes, persist yes, agents yes' }
   → server reads ALL comms_messages for sess_42 (the whole thread)
   → formats them into the next prompt (small — a few artefacts)
   → invoke_agent() again, state=THINKING

4. Agent produces an architecture artefact → AWAITING again
   → loop until the user is satisfied

5. User clicks "Start pipeline", names it "feature-notifications"
   → POST /consult/convert { session_id:'sess_42',
                            feature_name:'feature-notifications' }
   → CONVERSION RUNS (Section 8)
   → Studio redirects to the main pipeline view
```

**No vector search anywhere in this flow.** The thread is small enough to inject
whole. That is why it does not need Phase 4.

---

## 7. The Consultation FSM

A new minimal state machine, separate from the 8-stage team pipeline:

```
States: OPEN → THINKING → AWAITING → THINKING → ... → CONVERTING → DONE

OPEN
  Trigger: user posts first request
  Action:  launch headless consultant agent
  → THINKING

THINKING
  Agent runs headless, non-blocking
  Agent posts an artefact via /comms/post
  Agent exits
  → AWAITING

AWAITING
  Human reads artefact, optionally opens editor
  Human replies OR annotates+sends
  → THINKING     (more discussion needed)
  → CONVERTING   (human clicks "Start pipeline")

CONVERTING
  Human provides feature name
  System: creates plan files, promotes artefacts to feature board,
          registers feature in main FSM
  → DONE  (feature enters team pipeline at PLAN state)
```

No review, no testing, no retro. Just: discuss → decide → hand off.

---

## 8. The Conversion Magic — Discussion Becomes a Feature

The single most important piece. It is what makes board-storm worth building.

```
POST /consult/convert  reads all artefacts for the session and does:

  draft_spec artefact ───────────▶ pathly/plans/feature-notifications/USER_STORIES.md
  implementation_plan artefact ──▶ pathly/plans/feature-notifications/IMPLEMENTATION_PLAN.md
  ALL artefacts (questions,    ──▶ comms_messages copied as
    architecture, tradeoffs)        board='feature', scope='feature-notifications'
                                     (the feature board STARTS pre-filled)
  write STATE.json ──────────────▶ { current: "PLAN", board_scope: {...} }
                                     (storm already done — skip STORM state)
  register in main FSM ──────────▶ feature enters the team pipeline
```

What the builder sees later:

```
When the builder finally runs, its ## Communication Board block already contains:
  📌 [decision]    SSE for notifications — we have the infra
  📎 [architecture] <the diagram the consultant drew>
  📌 [decision]    Notifications persist across restarts
  💡 [tradeoff]    Chose inbox+toast over toast-only because...

The builder starts knowing everything you discussed.
No current Pathly pipeline gives an agent this much context.
```

This is the closed loop: the consultation output IS the feature input.

---

## 9. The Editor Panel — Annotation Mode (v2)

When the user clicks `[Open in editor]` on an artefact, the right side opens an
annotation view (deferred to v2 — v1 uses threaded board replies):

```
┌───────────────────────────┬────────────────────────────────────────┐
│  BOARD THREAD             │  EDITOR — questions artefact           │
│  ─────────────────────    │  ─────────────────────────────────     │
│                           │  1. Should notifications be real-time  │
│  User: "I want to build   │     (SSE) or polled?                   │
│  a notification system"   │     ┌─ comment ─────────────────────┐  │
│                           │     │ → SSE. We already have SSE    │  │
│  Agent: [questions] ◀──── │     │    infrastructure.            │  │
│  selected                 │     └──────────────────────────────┘  │
│                           │                                        │
│                           │  2. Do notifications persist across    │
│                           │     app restarts?                      │
│                           │     [+ add comment]                    │
│                           │                                        │
│  ─────────────────────    │  ──────────────────────────────────    │
│  [Reply]  [Open editor]   │  [Send to agent with comments]         │
└───────────────────────────┴────────────────────────────────────────┘
```

Annotation model (v2): each numbered item in the artefact gets a comment thread.
"Send to agent with comments" compiles `original artefact + per-item comments`
into the next agent invocation.

**v1 simplification:** skip the editor entirely. The user replies to the artefact
as a threaded board message. The editor panel is a v2 enhancement.

---

## 10. Designer Note — It Should Feel Like a Document Review

The mental model to invoke is neither chat nor pipeline:

```
NOT: "I'm chatting with an AI"      (ephemeral, informal, linear dialogue)
NOT: "I'm running a pipeline stage" (automated, hands-off, I wait)
YES: "I'm reviewing a document with a collaborator"
     (document exists, I mark it up, collaborator revises, we converge)
```

Implications:
- The artefact is the primary visual element — large, readable, prominent
- The message thread is secondary
- The action button says "Send to agent" / "Submit", not "Send message"
- The consultation board has a different visual skin than the active comms board,
  to signal "this is pre-pipeline ideation, not a running pipeline"

---

## 11. Artefact Types the Consultant Produces

The agent operates in consultant mode — it asks, draws, and analyses. It does
NOT write code or modify files.

| Artefact | Contents | When used |
|---|---|---|
| `questions` | 5–8 clarifying questions before committing | Request is vague |
| `architecture` | ASCII system diagram + components + data flow | Technical shape needs agreement |
| `tradeoffs` | Side-by-side comparison of 2–3 approaches | Multiple valid solutions exist |
| `risks` | List of what could go wrong | Before a risky approach |
| `draft_spec` | Feature spec: user stories + acceptance criteria | Design converging |
| `implementation_plan` | Phased plan with file targets | Ready to hand off |

---

## 12. New Endpoints

```
POST /consult/start         { request, project_root }
  → creates session, launches headless consultant agent
  → returns { session_id }

POST /consult/reply         { session_id, text, comments?[] }
  → bundles thread + reply, launches next agent turn

POST /consult/convert       { session_id, feature_name }
  → converts session to a named feature
  → generates plan files from artefacts
  → promotes artefacts to feature board
  → returns { feature, redirect_to: "team pipeline" }

GET  /consult/session/:id   → current session state + all artefacts
GET  /events/consult?session_id=X  → SSE stream for real-time updates
```

---

## 13. Implementation Plan (Phase 5)

```
Step 1  consult.md skill + consultant agent role          (src/pathly_data/)
Step 2  session state via app_settings                    (no new table)
Step 3  consult.py blueprint — 5 routes                   (http_server/blueprints/)
Step 4  consult.py loop driver — the FSM                  (supervisor/)
Step 5  consult_convert.py — artefacts → plan files       (runner/)
Step 6  ConsultPanel — reuse CommsPanel + artefact cards  (studio/components/HQ/)
```

Prerequisite: comms board Phase 1 (backend) + Phase 2 (CommsPanel) shipped.

**Phase 5 deliverable:** the user can open a blank board, discuss an idea with a
consultant agent through evolving artefacts, and convert the session into a
pipeline-ready feature with one click — its board pre-filled with everything
that was decided.

---

## 14. Open Questions

| Question | Options | Recommendation |
|---|---|---|
| How does the agent emit artefacts? | Agent calls /comms/post itself (skill) vs server parses agent stdout | Agent posts via skill — reuses comms write path |
| Editor annotation in v1? | Build it / threaded replies only | Threaded replies only; editor is v2 |
| Consultant model | sonnet vs opus | opus — this is the thinking work |
| Does board-storm need its own board type? | New `board='consult'` vs reuse `board='feature'` | New `board='consult'`, scope=session_id; promoted to feature on convert |
| What if the user abandons a session? | Auto-trash after N days / keep forever | Trash after 30 days (same as comms board lifecycle) |
| Can a consultation reference existing boards? | Yes (semantic search) / No (isolated) | v1 isolated; v2 lets consultant search project/global boards |

---

*Board-storm design v1.0 — consultation mode over the comms board*
