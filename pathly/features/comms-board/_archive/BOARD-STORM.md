# Board-Storm — Multi-Agent Consultation Flow

**Feature:** Pre-pipeline ideation through the communication board — a separate FSM flow
that replaces the (always-skipped) STORM phase with an iterative, multi-agent expert panel.  
**Parent spec:** [SPEC.md](SPEC.md) (the comms board)  
**Related:** [STORM-REMOVAL.md](STORM-REMOVAL.md) (cutting STORMING from the team flow)  
**Status:** Design  
**Date:** 2026-06-10  
**Depends on:** Comms board Phase 1 (backend) + Phase 2 (CommsPanel)  

> **Evolution note (v2.0):** This doc began as a *single-consultant* design. It is now a
> *multi-agent panel*: PO + architect + designer consult the human through the board, and
> **each expert fills the plan template that matches their domain** (§15). The single-consultant
> flow in §1–§14 is the mechanical substrate; the panel in §15 is how it is actually staffed.

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

### 9.1 The editor loop ALREADY EXISTS — codebase finding (2026-06-10)

The annotation editor described above is not a thing to build. It already exists
and runs in the app today as the **file-review workflow** in
`studio/src/renderer/src/components/Editor/index.tsx`. It is used for reviewing
and revising plan/skill `.md` files with an AI agent.

**The existing loop (Editor/index.tsx), step by step:**

```
1. Open a .md file        → loads body, checks for existing <file>.draft
2. Select text in preview → CommentablePreview → handleSelectionComment → CommentModal
3. Add anchored comment   → addComment(deriveLineNumber(body, anchor), anchor, body)
4. "Send to agent"        → handleModalSendNow:
                              buildSendPrompt(path, body, unresolvedComments)
                              spawn: claude -p <prompt> --print --dangerously-skip-permissions
                              agent writes <file>.draft
5. Draft appears          → DraftDiffViewer shows diff, [Apply] / [Discard]
6. Apply                  → writes revised content to file, deletes draft
7. resolve / reopen       → per-comment verification lifecycle
```

**The comment data model** (`Editor/useComments.ts`):

```ts
interface Comment {
  id: string
  lineNumber: number    // position — RE-DERIVED from anchor text, not fixed
  lineText: string      // ← the RESILIENT anchor (the text content itself)
  body: string          // the comment
  resolved: boolean     // ← the verification lifecycle
  createdAt: string
  color: CommentColor
}
```

Comments persist to a sidecar file: `<filePath>.comments.json`.

**Resilient anchoring is already solved** (`Editor/commentUtils.ts`):

```ts
// deriveLineNumber re-finds the anchored line after the agent rewrites the file
const idx = lines.findIndex((l) => l.includes(firstLine))
return idx !== -1 ? idx + 1 : 1
```

The anchor is the TEXT, not a DOM/pixel offset — so it survives the agent
rewriting the artefact. There is even an orphan detector (`getOrphanedIds`)
for comments whose anchor text disappeared after a rewrite.

**The send-to-agent compiler already exists** (`Editor/commentUtils.ts → buildSendPrompt`):

```
"You are revising the file: <path>"
"Address each reviewer comment below. Do not change sections that have no comments."
--- REVIEWER COMMENTS ---
Line 12 ("the SSE box"): use existing SSE infra
--- CURRENT FILE CONTENT ---
<body>
"Write the complete revised content to: <path>.draft"
"After writing, briefly list which comments you addressed."
```

**Reusable components (all under `Editor/`):**

| Component | Role in board-storm |
|---|---|
| `Editor/index.tsx` | The full review loop orchestration — the template for the consult editor |
| `CommentablePreview/` | Select text → anchored comment; highlights; selection tooltip |
| `useComments.ts` | Comment CRUD + resolve/reopen lifecycle |
| `commentUtils.ts → buildSendPrompt` | The "send to agent with comments" compiler |
| `commentUtils.ts → deriveLineNumber` | Resilient re-anchoring after rewrites |
| `DraftDiffViewer/` | Diff of agent revision vs original, with Apply / Discard |
| `CommentsPanel/` + `CommentsPanelRail/` | Side panel listing comments, resolve/reopen |
| `CommentModal/` | The add-comment popover |

### 9.2 What board-storm actually is, given this

```
Board-storm  =  the EXISTING file-review loop (Editor/index.tsx)
              + a session FSM driving it (OPEN → THINKING ⇄ AWAITING → CONVERTING)
              + a "consultant" agent persona (questions/architecture/spec —
                instead of buildSendPrompt's generic "revise this file")
              + a convert-to-feature step
```

The hard 80% — anchored comments, resilient anchoring, the send-to-agent
compiler, the draft/diff/apply loop — is built. Board-storm adds orchestration.

### 9.3 Two integration paths

**Path A — file-backed (recommended for v1 and v2):**

```
Artefacts ARE .md files in a consult session folder:
  pathly/plans/.consult/<session_id>/
    questions.md
    architecture.md
    draft_spec.md
    implementation_plan.md

Comments stay in sidecar files (<artefact>.comments.json).
Reuse Editor + CommentablePreview + DraftDiffViewer + buildSendPrompt VERBATIM.

Payoff: conversion becomes almost a FILE MOVE —
  draft_spec.md          → pathly/plans/<feature>/USER_STORIES.md
  implementation_plan.md → pathly/plans/<feature>/IMPLEMENTATION_PLAN.md
  all artefacts          → copied as feature board messages (one DB insert each)
```

**Path B — board-native (later, when SSE/cross-feature memory needs the comments):**

```
Comments become comms_messages rows:
  { type:'comment', reply_to:<artefact_msg_id>,
    anchor:{ kind:'line', ref:lineNumber, text:lineText }, text:body, status }
More work; do it only when the board itself must surface consultation comments.
```

The existing `Comment` model maps 1:1 onto Path B's message shape, so Path A → B
is a later migration, not a rewrite.

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
        consultant prompt = adapt buildSendPrompt's structure to produce
        questions/architecture/spec artefacts as .md files
Step 2  session state via app_settings                    (no new table)
Step 3  consult.py blueprint — 5 routes                   (http_server/blueprints/)
Step 4  consult.py loop driver — the FSM                  (supervisor/)
Step 5  consult_convert.py — artefact .md files → plan files (runner/)
        (Path A: near file-move — see §9.3)
Step 6  Consult view — REUSE the existing Editor loop      (studio/components/)
        Editor/index.tsx + CommentablePreview + DraftDiffViewer already
        provide the entire annotate → send → revise → diff → apply cycle.
        New work: a session/thread shell + "Start pipeline" button.
```

Prerequisite for the EDITOR surface: none — `Editor/index.tsx` and its comment
stack already exist and run (used for plan/skill file review).
Prerequisite for the BOARD/thread + SSE surface: comms board Phase 1 + Phase 2.

**Path A insight:** because the editor loop is file-backed today, board-storm v1
can ship on files alone — artefacts as `.md` in `pathly/plans/.consult/<session>/`,
reusing the existing Editor verbatim — before the comms board DB layer is even
built. The DB/board layer is only needed for the thread view, SSE, and
cross-feature memory.

**Phase 5 deliverable:** the user can open a blank board, discuss an idea with a
consultant agent through evolving artefacts, and convert the session into a
pipeline-ready feature with one click — its board pre-filled with everything
that was decided.

---

## 14. Open Questions

| Question | Options | Recommendation |
|---|---|---|
| How does the agent emit artefacts? | Agent calls /comms/post itself (skill) vs server parses agent stdout | Agent posts via skill — reuses comms write path |
| Editor annotation in v1? | Build it / threaded replies only | RESOLVED — the editor loop already exists (Editor/index.tsx, §9.1). Reuse it; no build needed. |
| Anchor model — survives agent rewrites? | DOM offset / line / text | RESOLVED — existing code anchors by TEXT (lineText) + re-derives line; orphan detection included (§9.1) |
| Artefact storage — files or DB? | .md files / comms_messages rows | Path A: `.md` files in `pathly/plans/.consult/<session>/` for v1 (reuses Editor verbatim); migrate to DB later (§9.3) |
| Consultant model | sonnet vs opus | opus — this is the thinking work |
| Does board-storm need its own board type? | New `board='consult'` vs reuse `board='feature'` | New `board='consult'`, scope=session_id; promoted to feature on convert |
| What if the user abandons a session? | Auto-trash after N days / keep forever | Trash after 30 days (same as comms board lifecycle) |
| Can a consultation reference existing boards? | Yes (semantic search) / No (isolated) | v1 isolated; v2 lets consultant search project/global boards |

---

---

## 15. Multi-Agent Consultation Flow

### 15.1 Why a panel, not one consultant

A single consultant has to be a generalist. Real pre-build thinking has three distinct
jobs: **what** to build (scope/requirements), **how** to build it (architecture), and
**how it should look/feel** (UX). Those are three different experts. The consult flow
staffs them as a panel — the same three voices that already exist as agents (`po`,
`architect`, `designer`) and that authored `CONSULTATION.md`.

This flow **replaces the STORM phase** entirely (see STORM-REMOVAL.md). The team flow
loses STORMING and enters at PLANNING (or later — §15.5).

### 15.2 The panel through the board

```
CONSULTING — the human talks to a panel via the board (using the `to_agent` field):

  👤 human  ──"a notification system across features"──►  consult board
       │
       ├─► 🧭 po        → fills USER_STORIES.md · EDGE_CASES.md · HAPPY_FLOW.md
       ├─► 🏛 architect  → fills ARCHITECTURE_PROPOSAL.md · IMPLEMENTATION_PLAN.md · FLOW_DIAGRAM.md
       └─► 🎨 designer   → fills DESIGN.md          (UI features only)

  Each expert posts artefacts to the board. The human reviews/annotates them in the
  editor surface (§9 — the existing comment loop) and replies. The `to_agent` field
  routes a follow-up to one named expert: "architect, reconsider the SSE choice."
```

The `to_agent` field already in the message schema (SPEC §5) was built for exactly this.

### 15.3 Per-expert template ownership ⭐

The core refinement: the planner no longer authors everything alone. **Each expert is
handed the plan template that matches their domain and fills it.** The planner runs last
as the *integrator*.

| Expert | Owns these templates | Why |
|---|---|---|
| 🧭 **po** | `USER_STORIES.md`, `EDGE_CASES.md`, `HAPPY_FLOW.md` | the what / why / user journey |
| 🏛 **architect** | `ARCHITECTURE_PROPOSAL.md`, `IMPLEMENTATION_PLAN.md`, `FLOW_DIAGRAM.md` | the how / phases / file targets |
| 🎨 **designer** | `DESIGN.md` (UI features only) | the look / UX system (design subsystem already emits this) |
| 🗂 **planner** | `FEATURE_INDEX.md`, `PROGRESS.md`, `CONVERSATION_PROMPTS.md` | **integrate + slice + track** |

The planner **never invents architecture**. It reads the architect's `IMPLEMENTATION_PLAN.md`,
slices the phases into ≤4 conversations, and writes the index/progress/prompts that stitch
everyone's output into a buildable plan — exactly what a PM does.

### 15.4 Template-native artefacts = the file-move conversion

Because each expert fills their **actual template** during consultation (not free-form text
that is converted later), the consultation artefact *is* the plan file:

```
po's artefact            IS   USER_STORIES.md          (no lossy conversion)
human annotates          →    the real USER_STORIES.md via the editor comment loop (§9)
conversion               =    move files → pathly/plans/<feature>/   (Path A — §9.3)
```

This is why Path A (file-backed, §9.3) is the right substrate: artefacts live as `.md`
files in `pathly/plans/.consult/<session>/`, get annotated by the existing editor, and
convert by moving into the feature folder.

### 15.5 What's left for the team flow — entry point

If PO + architect + designer + planner fill **all** the plan and design templates during
consultation, then PLAN and DESIGN are already done at conversion. The team flow shrinks:

```
consult flow (PO + architect + designer + planner — fills every template)
    │  convert = move files
    ▼
team flow:  PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE
            └─ pre-filled ─┘   └────────── pure execution ──────────┘
```

**Recommendation:** enter the team flow at **PLANNING**, where the planner does a fast
integration/validation pass over the pre-filled files — keeping one checkpoint before BUILD.
Entering directly at **BUILDING** is where this logically ends up (PLAN+DESIGN fully done in
consult), but keep the PLAN checkpoint until the consult flow is proven in practice.

### 15.6 Panel orchestration — hybrid

```
Default choreography (a relay — each expert builds on the prior one's template):
  PO scopes  →  architect designs against that scope  →  designer styles that design
                                                      →  planner integrates all

The human can interject at any point (board to_agent routing makes this natural):
  "go back to PO, the scope is wrong"
  "skip designer — backend only"
  "architect, give me a second option"
```

Rigor scales the panel:

| Rigor | Panel | Rounds |
|---|---|---|
| `nano` | PO only | 1 |
| `lite` | PO + architect | 1–2 |
| `standard` | PO + architect (+ designer if UI) | a few |
| `strict` | full panel, `risks` artefact required | multiple |

**Designer is conditional** — invoked only when the feature has a UI surface. A pure-backend
feature (e.g. comms-board Phase 1) skips designer and skips `DESIGN.md`.

### 15.7 Consultation FSM (revised for the panel)

```
OPEN → CONSULTING ⇄ AWAITING → CONVERTING → DONE

CONSULTING   the active expert (po/architect/designer/planner) runs headless, fills its
             template artefact, posts to the board, exits.
AWAITING     human reviews/annotates the template in the editor; replies or redirects
             (to_agent picks the next/same expert).
             → CONSULTING  (next expert or another round)
             → CONVERTING  (human: "Start pipeline")
CONVERTING   move the filled template files → pathly/plans/<feature>/ ; register the
             feature in the team flow at PLANNING.
DONE
```

The substrate is unchanged from §7 — it is the same single-agent loop, just invoked once
per expert with `to_agent` selecting who runs.

### 15.8 Reuses existing primitives

| Need | Already exists |
|---|---|
| PO expert | `po` agent + `pathly-po` skill (interactive requirements) |
| Architect expert | `architect` agent |
| Designer expert | `designer` agent + `pathly-design` + the design subsystem (emits `DESIGN.md`) |
| Planner integrator | `planner` agent + the plan skill (already template-driven) |
| Multi-agent discussion | `pathly-meet` skill (candidate primitive) |
| Templates | `core/templates/plan/*.template.md` — already one per file |
| Editor annotation loop | `Editor/index.tsx` + comment stack (§9.1) |

Nothing new to build at the agent layer — the consult flow *orchestrates* existing experts
through the board, handing each the template it owns.

---

*Board-storm design v2.0 — generalized to a multi-agent consultation flow: PO + architect +
designer panel via board `to_agent` routing; per-expert template ownership (planner integrates
last); template-native artefacts make conversion a file-move; replaces the removed STORM phase
(see STORM-REMOVAL.md); team flow enters at PLANNING pre-filled. Single-consultant substrate
(§1–§14) unchanged — the panel is how it is staffed.*
