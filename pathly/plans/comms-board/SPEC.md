# Pathly Communication Board — Full Architecture Spec

**Status:** Design  
**Author:** Claude (with Yafit)  
**Date:** 2026-06-10  

---

## 1. The Problem We Are Solving

### 1.1 Context loss across stages

Today, each agent starts almost blind. It reads the feature plan files (USER_STORIES,
IMPLEMENTATION_PLAN, CONVERSATION_PROMPTS) and the last N AGENT_DONE summaries.
But it does NOT know:

- What the human said to the builder mid-run
- What constraints the human added after planning
- What the reviewer discovered but you told it to ignore
- What architectural decisions were made in conversation

Every stage is a fresh start. Agents repeat mistakes, ask the same questions,
and don't build on each other's discoveries.

### 1.2 One-directional communication

Current tools are all point solutions in one direction:

```
Nudge file          human → agent     (agent may or may not read it)
PHASE_SUMMARY       agent → human     (no reply path)
AskUserQuestion     agent → human     (blocks the pipeline)
PTY stdin           bidirectional     (interactive mode only, ephemeral)
AGENT_DONE.summary  agent → next FSM  (no human contribution)
```

There is no **persistent, bidirectional, structured** channel.

### 1.3 No semantic memory

Everything in Pathly is local to a feature run. When you build a second feature
that touches the same subsystem, the agent has no memory of what was decided
the first time. Patterns, mistakes, decisions, and discoveries are lost.

---

## 2. Vision

The communication board is a **shared working surface** that sits between the
human and all agents across a feature's entire lifecycle.

Think of it as the whiteboard in a sprint room:
- The human writes requirements, constraints, corrections
- Agents post status, questions, discoveries, warnings
- Everything is visible to everyone
- The board persists for the life of the feature (and beyond)
- New agents get brought up to speed by reading the board

With a vector DB layer, the board becomes **organizational memory**:
- Not just a chat log — a searchable knowledge base
- Agents can query: "what did we decide about authentication?"
- Cross-feature retrieval: decisions from past features surface when relevant
- The longer you use Pathly, the smarter your agents get

---

## 3. The Three Scopes

```
┌─────────────────────────────────────────────────────────┐
│  GLOBAL BOARD  (~/.pathly/boards/global.db)             │
│  Permanent organizational knowledge                     │
│  Cross-project, cross-feature, cross-team               │
│  Examples: "We always use Zod for validation"           │
│            "Never use class components in this org"     │
├─────────────────────────────────────────────────────────┤
│  PROJECT BOARD  (project_root/.pathly/boards/project.db)│
│  Persistent project-level decisions                     │
│  Architectural choices, patterns, recurring constraints │
│  Examples: "Use shadcn/ui for all new components"       │
│            "Auth is handled by /lib/auth.ts"            │
├─────────────────────────────────────────────────────────┤
│  FEATURE BOARD  (pathly/plans/<feature>/COMMS.db)       │
│  Feature-scoped conversation thread                     │
│  Human-agent dialogue for this feature only             │
│  Archived with the feature when done                    │
│  Examples: "Skip rename detection, that's v2"           │
│            "Focus on Editor/index.tsx first"            │
└─────────────────────────────────────────────────────────┘
```

At `/next_action` time the FSM queries all three boards, retrieves the top-K
relevant messages, and injects them into `agent_hint.instructions`.

---

## 4. How It Fits Into the Pathly FSM

### 4.1 Today's `/next_action` flow

```
POST /next_action
  ├── read STATE.json          → current FSM state
  ├── read USER_STORIES.md     → acceptance criteria
  ├── read IMPLEMENTATION_PLAN → technical plan
  ├── read CONVERSATION_PROMPTS → what to build
  ├── read AGENT_DONE history  → what was done
  └── build agent_hint.instructions
```

### 4.2 With the communication board

```
POST /next_action
  ├── read STATE.json          → current FSM state
  ├── read plan files          → same as today
  ├── read AGENT_DONE history  → same as today
  ├── COMMS BOARD QUERY ←─ NEW
  │   ├── embed current task description
  │   ├── query feature board  → top-3 relevant messages
  │   ├── query project board  → top-2 relevant messages
  │   └── query global board   → top-1 relevant message
  └── build agent_hint.instructions
      (now includes ## Communication Board section)
```

### 4.3 What the agent sees

The injected block looks like this, appended to every agent's prompt:

```markdown
## Communication Board

### Decisions (from previous stages)
- [human → builder, BUILDING] Skip rename detection — that is v2 scope
- [reviewer → human ✓, REVIEWING] Noted, marked as future work in REVIEW.md

### Active (needs your attention)
- [human → *, PLANNING] Always use unified diff format for all output

### Your unread messages
- [human → builder] When you start implementing, focus on Editor/index.tsx first.
  The other files (CommentsPanel, DraftView) are already correct.
```

The agent reads this as part of its starting context. It knows what was decided,
what constraints exist, and what the human expects — before writing a single line.

### 4.4 Agent writes back to the board

During its work, the agent can call:

```bash
# Post a status update
curl -X POST http://127.0.0.1:8765/comms/post \
  -d '{"feature":"send-to-agent-diff","from":"builder","type":"status",
       "text":"Phase 1 done. DiffViewer.tsx created. Starting Phase 2."}'

# Post a question (non-blocking — doesn't stop the pipeline)
curl -X POST http://127.0.0.1:8765/comms/post \
  -d '{"feature":"send-to-agent-diff","from":"builder","type":"question",
       "text":"Found two approaches for scroll sync. Preference?",
       "options":[{"id":"a","label":"CSS scroll-snap"},{"id":"b","label":"JS IntersectionObserver"}]}'

# Acknowledge a human message
curl -X POST http://127.0.0.1:8765/comms/acknowledge \
  -d '{"feature":"send-to-agent-diff","agent":"builder","message_id":"msg-007"}'
```

---

## 5. Message Schema

```json
{
  "id": "msg-007",
  "board": "feature",
  "scope": "send-to-agent-diff",
  "from": "builder",
  "to": "*",
  "type": "question",
  "text": "Found two approaches for scroll sync. Preference?",
  "options": [
    { "id": "a", "label": "CSS scroll-snap", "description": "Simple, native" },
    { "id": "b", "label": "JS IntersectionObserver", "description": "More control" }
  ],
  "reply_to": null,
  "stage": "BUILDING",
  "conv": 3,
  "ts": "2026-06-10T10:45:00Z",
  "read_by": [],
  "acknowledged_by": [],
  "status": "pending",
  "embedding": [0.123, -0.456, ...],
  "embedding_model": "all-MiniLM-L6-v2",

  // artifact fields (null for non-artifact messages)
  "artifact_path": null,
  "artifact_type": null,
  "artifact_url": null,

  // task fields (null for non-task messages)
  "task_status": null,
  "assigned_to_stage": null,
  "assigned_to_agent": null,

  // lifecycle fields
  "deleted_at": null,
  "promoted_to": null,
  "promoted_from": null,
  "original_scope": null
}
```

### Message types

| Type | Posted by | Meaning |
|---|---|---|
| `nudge` | human | Instruction or constraint for the next agent |
| `question` | agent or human | Needs a response; shows in Studio with options |
| `answer` | human or agent | Reply to a question (links via reply_to) |
| `status` | agent | Progress update; informational only |
| `decision` | human | An explicit decision that applies going forward |
| `warning` | agent | Something suspicious — human should review |
| `discovery` | agent | Interesting finding that might affect other stages |
| `escalation` | agent | Human MUST respond before work can continue |
| `artifact` | human | Attached file, doc, image, or URL — agents read it by semantic search |
| `task` | human | A scoped instruction with a status lifecycle (pending → done / skipped) |

### Priority rules

```
escalation → blocks the pipeline (same as current HUMAN_QUESTIONS.md)
question   → non-blocking by default; agent continues and checks for answer later
             UNLESS message has "blocking": true
nudge      → immediately injected into next agent's prompt
decision   → permanently injected (never expires, shown to all future agents)
```

---

## 6. Vector DB Architecture

### 6.1 Storage choice: sqlite-vec

Pathly already uses SQLite for all state. `sqlite-vec` is a SQLite extension that
adds vector search as a virtual table — no new processes, no new dependencies,
zero configuration.

```sql
-- In the existing ~/.pathly/pathly.db schema

CREATE TABLE comms_messages (
    id          TEXT PRIMARY KEY,
    board       TEXT NOT NULL,          -- 'feature' | 'project' | 'global'
    scope       TEXT NOT NULL,          -- feature name, project root, or 'global'
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL DEFAULT '*',
    type        TEXT NOT NULL,
    text        TEXT NOT NULL,
    options     TEXT,                   -- JSON array
    reply_to    TEXT,
    stage       TEXT,
    conv        INTEGER,
    ts          TEXT NOT NULL,
    read_by     TEXT DEFAULT '[]',      -- JSON array
    acknowledged_by TEXT DEFAULT '[]',
    status      TEXT DEFAULT 'pending',
    embedding_model TEXT
);

-- sqlite-vec virtual table for semantic search
CREATE VIRTUAL TABLE comms_embeddings USING vec0(
    message_id TEXT PRIMARY KEY,
    embedding  FLOAT[384]              -- all-MiniLM-L6-v2 output dimension
);
```

### 6.2 Embedding pipeline

```
Message posted to /comms/post
    │
    ├── Store text in comms_messages (immediate)
    │
    └── Embed asynchronously (background thread)
          │
          ├── Python path:   sentence-transformers all-MiniLM-L6-v2
          │   (same model used for skill matching in Studio)
          │
          └── Store vector in comms_embeddings
```

Embedding is async — the message is available immediately for exact-match queries.
Semantic search is available within ~200ms after posting.

### 6.3 Retrieval at /next_action

```python
def retrieve_board_context(topic, project_root, task_description, k=6):
    """
    Given what the next agent is about to do, retrieve the most
    relevant messages from all three boards.
    """
    task_embedding = embed(task_description)

    results = []
    for board, scope, limit in [
        ("feature", topic, 3),
        ("project", project_root, 2),
        ("global",  "global",   1),
    ]:
        rows = db.execute("""
            SELECT m.*, vec_distance_cosine(e.embedding, ?) as dist
            FROM comms_messages m
            JOIN comms_embeddings e ON e.message_id = m.id
            WHERE m.board = ? AND m.scope = ?
              AND m.status != 'archived'
            ORDER BY dist ASC
            LIMIT ?
        """, [task_embedding, board, scope, limit]).fetchall()
        results.extend(rows)

    # Always include: unread escalations + decisions (regardless of similarity)
    mandatory = db.execute("""
        SELECT * FROM comms_messages
        WHERE board IN ('feature','project','global')
          AND (type='escalation' OR type='decision')
          AND status = 'pending'
    """).fetchall()

    return dedupe_and_format(mandatory + results)
```

### 6.4 Agents querying the board

Agents can do semantic searches themselves during their work:

```bash
# "What did we decide about the diff format?"
curl http://127.0.0.1:8765/comms/search \
  -d '{"query":"diff format decision","feature":"send-to-agent-diff","k":3}'

# Response:
{
  "results": [
    {
      "text": "Always use unified diff format for all output",
      "from": "human", "type": "decision", "ts": "...", "score": 0.97
    }
  ]
}
```

This is the key capability: agents don't just passively receive board context — they
can actively interrogate their memory. A builder that discovers an edge case can ask:
"has this pattern come up before?" and get answers from past features.

---

## 7. Studio UI — The Comms Panel

> **⚠ Superseded by [UI-DIRECTION.md](UI-DIRECTION.md) (2026-06-11).** The standalone
> single-feature CommsPanel tab described here is **not** being shipped as its own HQ tab.
> The CommsPanel *components* are still built (and reused by the CommandCenter and Phase 5
> ConsultPanel), but they are verified standalone against the live SSE stream and then hosted
> inside the CommandCenter workspace — there is no intermediate one-board-at-a-time tab.
> §7.3 (message interactions: question cards, decision pinning, warning/escalation banners)
> still applies. Read UI-DIRECTION.md for the current layout.

### 7.1 Position in the layout

```
┌─────────────────────────────────────────────────┐
│  HQ Panel                                       │
├─────────────┬───────────────────────────────────┤
│  Chat       │  Terminal tabs                    │
│  (existing) ├───────────────────────────────────┤
│             │  Stage log (existing)             │
│             ├───────────────────────────────────┤
│             │  COMMS  ← new tab alongside log   │
└─────────────┴───────────────────────────────────┘
```

### 7.2 Comms panel anatomy

```
┌─────────────────────────────────────────────────────────┐
│ COMMS  [Feature ▾] [Project] [Global]           🔍      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  10:45  🤖 builder  BUILDING                           │
│  ┌─ question ─────────────────────────────────────┐    │
│  │ Found two scroll sync approaches. Preference?  │    │
│  │  ○ CSS scroll-snap (simple)                    │    │
│  │  ○ JS IntersectionObserver (more control)      │    │
│  │  [Answer]                               ⏳     │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  10:47  👤 you                                          │
│  ┌─ nudge ────────────────────────────────────────┐    │
│  │ Use scroll-snap. Keep it simple.               │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  10:48  🤖 builder  ✓ acknowledged                      │
│  ┌─ status ───────────────────────────────────────┐    │
│  │ Got it. Using CSS scroll-snap. Implementing... │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [ Type a message for the current agent... ]  [Send]    │
└─────────────────────────────────────────────────────────┘
```

### 7.3 Message interactions

- **Pending questions**: highlighted amber, "Answer" button expands option picker
- **Decisions**: pinned at top with a 📌 icon, never collapse
- **Warnings**: orange border, "Acknowledge" or "Block stage" buttons
- **Escalations**: red banner, blocks the pipeline until answered
- **Board scope toggle**: switch between Feature / Project / Global views
- **Search**: semantic search across all boards

---

## 8. How Messages Flow — End to End

```
FLOW 1: Human posts a nudge mid-stage

  Human types in CommsPanel: "Skip CommentsPanel, focus on Editor only"
    → POST /comms/post { type: "nudge", from: "human", text: "..." }
    → stored in comms_messages
    → embedded in background (200ms)
    → SSE COMMS_UPDATE → Studio marks message as "pending"
    → current agent: if it calls read_comms tool OR stage ends → sees it
    → NEXT /next_action: FSM retrieves it (high relevance) → injected
    → next agent opens with: "## Communication Board → human: Skip CommentsPanel..."


FLOW 2: Agent posts a non-blocking question

  Builder discovers ambiguity mid-work:
    → POST /comms/post { type: "question", from: "builder", options: [...] }
    → SSE COMMS_UPDATE → Studio shows question card with option buttons
    → agent CONTINUES WORKING (does not block)
    → human answers at any point → POST /comms/post { type: "answer", reply_to: "msg-007" }
    → SSE COMMS_UPDATE → question card shows "answered"
    → next /next_action → answer injected into next agent's prompt
    → builder (retry) or reviewer sees the decision


FLOW 3: Reviewer finds issue → human decides → forward

  Reviewer finds rename detection missing:
    → POST /comms/post { type: "warning", text: "Rename detection missing" }
    → Studio shows warning card: [Block] [Note as future work]
    → Human clicks "Note as future work"
    → POST /comms/post { type: "decision", reply_to: "warning-id",
                         text: "Rename detection is v2 scope. Do not block." }
    → Reviewer's complete_stage call returns next_state (not blocked)
    → REVIEWING advances to TESTING
    → Tester's prompt includes: "Decision: rename detection is v2, skip in tests"
    → (REVIEW_FAILURES.md is NOT created — warning resolved via board instead)


FLOW 4: Agent queries board for past decisions

  Builder encounters an auth edge case:
    → GET /comms/search { query: "authentication session handling", k: 3 }
    → vector search across feature + project + global boards
    → returns: "Project decision (3 months ago): use /lib/auth.ts, never roll custom auth"
    → builder uses /lib/auth.ts, never considers rolling its own
    → decision made once, followed forever
```

---

## 9. How REVIEW_FAILURES.md Becomes a Board Flow

Today:
```
REVIEWING → writes REVIEW_FAILURES.md → FSM sees blocked → RETRY → builder fixes → repeat
```

With the board:
```
REVIEWING → POST { type: "warning", text: "...", options: [block, note, ignore] }
          → human responds (or default applies after timeout)
          → if "block": RETRY (same as today)
          → if "note":  decision posted, REVIEWING advances, tester sees it
          → if "ignore": REVIEWING advances silently
```

This eliminates the blind 3-round feedback loop. The human is always in the loop
for review failures, and one explicit decision resolves it — no retries needed
for issues that aren't actually blockers.

---

## 10. API Endpoints

```
POST /comms/post
  Body: { feature, from, to?, type, text, options?, reply_to?, board? }
  → stores message, triggers embedding, broadcasts COMMS_UPDATE SSE

GET  /comms
  Query: feature, board?, type?, status?, limit?
  → returns messages (no embedding, text only)

POST /comms/search
  Body: { query, feature?, k?, boards? }
  → semantic search across requested boards

POST /comms/acknowledge
  Body: { message_id, agent }
  → marks message as read by agent, broadcasts update

POST /comms/answer
  Body: { question_id, answer_text, option_id? }
  → posts answer reply, resolves question, broadcasts update

GET  /events/comms?topic=X
  → SSE stream: COMMS_UPDATE events in real-time
```

---

## 11. FSM Injection Format

The board context injected into `agent_hint.instructions` is a structured markdown block:

```markdown
## Communication Board

> These are messages from your team. Decisions override your defaults.
> Read all entries. Acknowledge questions that are addressed to you.

### 📌 Decisions (always apply)
- [project] Use /lib/auth.ts for all authentication. Never roll custom.
- [feature] Rename detection is v2 scope — skip in all stages.

### 💬 Recent context
- [human → builder, BUILDING 10m ago] Focus on Editor/index.tsx first.
- [builder → *, BUILDING 8m ago] Phases 7 and 8 complete. Starting Phase 9.
- [reviewer → human ✓, REVIEWING 2m ago] Noted scroll-snap, marking as future.

### ❓ Open questions (answer if relevant to your work)
- [builder → *, msg-007] Should binary file diffs show size delta or "binary"?
  Options: a) size delta  b) "binary" label
```

---

## 12. Implementation Phases

### Phase 1 — Backend + FSM injection (no UI, high value)

1. `db/migrations.py`: add `comms_messages` + `comms_embeddings` tables
2. `db/queries/comms.py`: CRUD + semantic search helpers
3. `http_server/blueprints/comms.py`: 5 endpoints above
4. `fsm_ops.py`: call `retrieve_board_context()` in `next_action()`
5. `runner/history.py`: extend `build_pipeline_history_block()` to include decisions
6. Build and test: post messages via curl, verify injection in agent prompts

**Deliverable**: agents receive board context in their prompts. Human can steer
agents by posting to the board via curl or Studio chat (`/comms <message>`).

### Phase 2 — Studio CommsPanel

7. `CommsPanel/CommsPanel.tsx` + CSS module
8. `store/commsStore.ts`: message list, optimistic updates
9. SSE handler in `useHQ.tsx`: `COMMS_UPDATE` → store
10. Pending question cards with option picker
11. Decision pinning + warning banners
12. Board scope tabs (Feature / Project / Global)

**Deliverable**: full visual board in Studio. Human can post, answer questions,
see agent status in real time.

### Phase 3 — Agent skill integration

13. Update `build.md`: read board at start, post status + questions
14. Update `review.md`: post warnings as questions, not as REVIEW_FAILURES.md blocks
15. Update `test.md`: read board decisions before writing test plan
16. Add `comms-query` skill: agents can call `/comms/search` from tools
17. Update all skill exit contracts: post AGENT_DONE equivalent to board

**Deliverable**: agents actively participate in the board. REVIEW_FAILURES.md
feedback loop replaced by board-based resolution.

### Phase 4 — Cross-feature memory

18. Project board: persist architectural decisions across features
19. Global board: org-wide patterns and conventions
20. Board search in Studio: search across all features' history
21. Onboarding: when a new feature starts, seed its board with relevant
    project decisions (retrieved by similarity to the feature description)

**Deliverable**: the longer you use Pathly, the smarter your agents get.

---

## 13. Open Questions / Decisions Needed

| Question | Options | Recommendation |
|---|---|---|
| Embedding model | sentence-transformers (Python) vs @xenova/transformers (Studio) | sentence-transformers — already on server side |
| Embedding dimension | 384 (MiniLM) vs 768 (mpnet) vs 1536 (OpenAI) | 384 — fast, good quality, no API cost |
| Default timeout for unanswered questions | 10min / 30min / never | 30min then auto-convert to nudge |
| REVIEW_FAILURES.md: replace or coexist? | Replace entirely / coexist during migration | Coexist first, replace in Phase 3 |
| Board persistence after archive | Delete / keep in .archive | Keep in .archive for cross-feature search |
| Project board location | project_root/.pathly/boards/ | Yes — keeps it local to the project |

---

## 14. Why This Changes Everything

The communication board turns Pathly from a **pipeline runner** into a
**collaborative agent system**:

```
Before:  Human → clicks buttons → agents run → human reads output → repeat

After:   Human and agents share a working surface.
         Agents surface discoveries, ask questions, flag risks.
         Human steers, decides, constrains — at any point.
         Every decision is remembered and applied to all future work.
         The system gets smarter the longer you use it.
```

The FSM state machine stays exactly as it is. The board is additive — a new
context source that makes every agent smarter without changing how the pipeline
flows.

---

---

## 15. Board Lifecycle — Deletion, Archive, and Promote-Before-Delete

### 15.1 The three deletion paths

When a user deletes or archives a feature or project, its board goes through one of three paths:

**Option A — Silent soft delete**  
User deletes a feature with no promotable messages (or explicitly skips the prompt).  
Board moves to TRASH → persists 30 days → auto-erased.

**Option B — Archive with board preserved**  
Feature reaches DONE and is archived. Board is preserved in `.archive/<feature>/COMMS.db`
and remains searchable for cross-feature memory (Phase 4).  
Never permanently deleted unless the archive itself is deleted.

**Option C — Promote-before-delete**  
User deletes a feature whose board contains `decision`, `discovery`, or `warning` messages
that haven't yet been promoted to a wider scope. Pathly scans the board and surfaces a
promotion dialog before the delete proceeds.

### 15.2 Option C — Promote-Before-Delete flow

```
User clicks "Delete feature"
  │
  ├── FSM scans feature board for promotable messages
  │   Types:  decision, discovery, warning
  │   Filter: board = 'feature'  (not already at project/global scope)
  │   Rank:   type priority (decision > discovery > warning) + recency
  │
  ├── If NO promotable messages → skip to soft delete  (Option A)
  │
  └── If promotable messages found → show dialog:

      ┌──────────────────────────────────────────────────────────┐
      │  Before deleting "send-to-agent-diff"                    │
      │                                                          │
      │  3 messages might be worth keeping:                      │
      │                                                          │
      │  ☑ [decision] Use unified diff format for all output     │
      │    → Promote to: [Project ▼]                             │
      │                                                          │
      │  ☑ [discovery] Virtual scroll needed when diff > 500 ln  │
      │    → Promote to: [Project ▼]                             │
      │                                                          │
      │  ☐ [decision] Skip rename detection — v2 scope           │
      │    feature-specific, skip recommended                    │
      │                                                          │
      │  [Promote checked → then delete]  [Skip all → delete]    │
      └──────────────────────────────────────────────────────────┘
  │
  ├── Promoted messages are CLONED to the target board
  │   with origin metadata:  { promoted_from: "send-to-agent-diff" }
  │
  └── Soft delete proceeds on the feature board
```

### 15.3 Soft delete / 30-day trash

Any deletion (after Option A or after Option C promotion) triggers soft delete:

```sql
-- On delete
UPDATE comms_messages
SET status     = 'trashed',
    deleted_at = CURRENT_TIMESTAMP
WHERE scope = '<feature>';
```

**30-day retention rule:**  
A background job (on startup + nightly) checks:
```sql
DELETE FROM comms_messages
WHERE status = 'trashed'
  AND deleted_at < datetime('now', '-30 days');

DELETE FROM comms_embeddings
WHERE message_id NOT IN (SELECT id FROM comms_messages);
```

After erasure, logs a `BOARD_ERASED` event to `EVENTS.jsonl`.

**Restore from trash (any time within 30 days):**
```bash
# List trashed messages for a scope
GET /comms/trash?scope=send-to-agent-diff

# Restore specific messages
POST /comms/restore  { "message_ids": ["msg-001", "msg-002"] }

# Restore all messages for a scope at once
POST /comms/restore?scope=send-to-agent-diff
```

**Trash view in Studio:**
- Trash icon in the sidebar with a badge count
- Per-item: "Deleted 3 days ago · Expires in 27 days"
- Per-item buttons: `[Restore]`  `[Delete now]`
- Bulk: `[Empty Trash]`

### 15.4 Message schema additions for lifecycle

```json
{
  "status": "pending | read | acknowledged | archived | trashed | promoted",
  "deleted_at": null,
  "promoted_to": null,
  "promoted_from": null,
  "original_scope": null
}
```

### 15.5 Project-level delete cascades

When a **project** is deleted:
1. Option C scan runs across ALL features in the project simultaneously
2. A single consolidated dialog: "8 messages across 4 features might be worth keeping globally"
3. User promotes what they want → messages cloned to global board
4. All feature boards → trashed (30-day clock per feature)
5. Project board → trashed
6. After 30 days → permanent erasure of all records + physical `.db` files

---

## 16. Three-Panel Command Center — Session Mode

> **⚠ Layout revised by [UI-DIRECTION.md](UI-DIRECTION.md) (2026-06-11) — three-up and
> stacked are KEPT.** What stays: showing 1, 2, or **3 board sections side-by-side**, OR
> **stacked** (the `[⊞ side by side] ↔ [☰ stacked]` toggle), all resizable. What changes: the
> third equal column here was the **Features *list***; that list moves to a resizable left
> **sidebar** (per the user's request). So the three side-by-side sections are now the three
> board *scopes* — Global \| Project \| Feature *thread* — with the feature list in the sidebar,
> reachable as the "Board view" preset. Asymmetric widths (Feature 50 / Project 30 / Global 20)
> are just the preset's *default* — drag to equal if you want. A "Set as main feature" swap
> action connects the sidebar to the Feature Board section. Behaviors below still apply — §16.4
> (per-feature `board_scope` read toggles) and §16.5 (cross-scope task dispatch / broadcast).

### 16.1 What session mode is

The CommsPanel (Section 7) shows communication for **one feature** at a time.  
Session Mode is a different UX layer: a **multi-scope command center** where the human
can simultaneously communicate with agents at all three levels without switching context.

```
Single-feature view  →  chat window for one active feature (existing HQ)
Session mode         →  mission control — see everything, act at any scope, simultaneously
```

The user opens Session Mode and sees three panels side by side. They can post a
global constraint, watch it propagate, answer a question in a specific feature, and
check the project-wide status — all without navigating away.

### 16.2 Three-panel layout

```
┌────────────────────────────────────────────────────────────────────────┐
│  COMMAND CENTER                              [Session Mode]  [Exit]    │
├───────────────────┬────────────────────┬──────────────────────────────┤
│  🌐 GLOBAL        │  📁 PROJECT        │  🎯 FEATURES                 │
│  ─────────────    │  pathly-adapters   │  [4 active ▾]                │
│                   │  ─────────────     │                              │
│  📌 Decisions     │  📌 Decisions      │  ● send-to-agent-diff        │
│  · Use Zod for    │  · shadcn/ui only  │    BUILDING conv 3           │
│    all schemas    │  · /lib/auth.ts    │    builder: phases 7-9...    │
│  · No class       │  · TypeScript      │    💬 1 question pending     │
│    components     │    strict mode     │                              │
│                   │                    │  ○ comms-board               │
│  💬 Recent        │  💬 Activity       │    PLANNING                  │
│  [you] Audit all  │  builder: scroll   │    architect: schema...      │
│  features for XSS │  sync complete     │                              │
│                   │  reviewer: found   │  ⚠ event-phase-summary      │
│                   │  2 issues...       │    REVIEWING (blocked)       │
│                   │                    │    reviewer: 3 failures      │
│                   │  ─────────────     │    [Unblock] [Skip to test]  │
│  ──────────────── │  Type project...   │                              │
│  Type global...   │  [Send]            │  ─────────────────────────── │
│  [Send]           │                    │  Send to:                    │
│                   │                    │  ○ All features              │
│                   │                    │  ● send-to-agent-diff only   │
│                   │                    │  [Send]                      │
└───────────────────┴────────────────────┴──────────────────────────────┘
```

### 16.3 What each panel does

**Global panel (left)**

- Shows org-wide `decision` messages — permanent, injected into EVERY agent forever
- Shows recent global-scope activity
- Input: post constraints that apply across all projects and features  
  _Examples: "Use ES modules only", "All user-facing errors must include an error code"_
- These are low-volume, high-signal. Use sparingly — they are permanent.

**Project panel (middle)**

- Shows `decision` messages for the current open project
- Live health summary: "4 features active · 2 running · 1 blocked · 1 done"
- Input: post project-level decisions or broadcast to all features in the project  
  _Examples: "Use shadcn/ui for all new components", "We're migrating to pnpm"_
- Aggregated PHASE_SUMMARY activity from all features (firehose view)

**Feature panel (right)**

- Shows ALL active features as mini-cards:
  - Status indicator (running / blocked / idle / done)
  - Current stage + agent name
  - Last PHASE_SUMMARY line from that agent
  - Pending question count (badge)
  - Quick actions: `[Unblock]` `[Skip]` `[Pause]`
- User **selects** one or more feature cards to target
- Input below sends to the selected feature board(s) only
- `[Send to all]` broadcasts to ALL feature boards simultaneously
- Clicking a feature card expands it to a full-thread view (the existing CommsPanel)

### 16.4 Per-feature board scope selection

Each feature independently declares which boards it reads from.
Stored in `STATE.json`:

```json
{
  "feature": "send-to-agent-diff",
  "state": "BUILDING",
  "board_scope": {
    "feature": true,
    "project": true,
    "global": true
  }
}
```

**What disabling each scope means:**

| Scope disabled | Effect |
|---|---|
| `feature: false` | Agents in this feature ignore their own feature board. "Clean run" — no prior steering. |
| `project: false` | Agents ignore project decisions for this feature. Use when feature intentionally deviates from project norms. |
| `global: false` | Agents ignore global constraints. Use only for spike/prototype features. |

**Default:** all three enabled.

**UI in the Feature panel card:**

```
send-to-agent-diff  ⚙
  Reads from:  ☑ Feature  ☑ Project  ☑ Global
```

Small toggle row at the bottom of each feature card.
Changes take effect at the next `/next_action` — the current stage is NOT interrupted.

The FSM reads `board_scope` from `STATE.json` and filters the retrieval query in
`retrieve_board_context()`:

```python
scope_cfg = state.get("board_scope", {"feature": True, "project": True, "global": True})
boards_to_query = [b for b, enabled in scope_cfg.items() if enabled]
```

### 16.5 Task dispatch at different levels

Each panel can post **tasks** in addition to plain messages.  
A task is a message with `"type": "task"` and an optional target:

```json
{
  "type": "task",
  "text": "Add JSDoc to all new exports",
  "assigned_to_stage": "BUILDING",
  "assigned_to_agent": "builder",
  "task_status": "pending | in_progress | done | skipped"
}
```

**Task propagation:**

```
Global task: "Audit all features for XSS"
  → message at global scope
  → every feature's next /next_action injects it
  → agent decides: does this apply to my current work?
  → addresses it → posts result back to board
  → or: acknowledges + skips (task_status = 'skipped')

Project task: "Update all package.json scripts to use pnpm"
  → message at project scope
  → only features in this project see it

Feature task: "After conv 3, add JSDoc to all new exports"
  → message at feature scope, targeting builder
  → builder reads it at next stage boundary
  → treats it as an additional requirement
```

### 16.6 Session mode UI options

**v1 — Full overlay (recommended)**
```
User clicks [Session Mode] in HQ header
  → three-panel overlay covers the terminal area
  → terminals continue running in background
  → [Exit Session Mode] returns to terminal view
```

**v2 — Sidebar expansion (stretch)**
```
The left HQ panel expands to three columns
  → terminals shrink to 40% width
  → full visibility of both terminals and session panels
```

**v3 — Separate window (stretch)**
```
Session mode opens in a second Electron window
  → main window keeps all terminals
  → command center in second window
```

---

## 17. Complete Communication Picture

Pathly now has five distinct communication modes. They are complementary — not competing:

```
┌──────────────────┬──────────────────────────────────────────────────┐
│  Mode            │  Description                                     │
├──────────────────┼──────────────────────────────────────────────────┤
│  Session         │  Real-time PTY stdin to a RUNNING agent.         │
│  (live)          │  Immediate, ephemeral. Interactive mode only.    │
├──────────────────┼──────────────────────────────────────────────────┤
│  Nudge           │  Write NUDGE.md → injected at next stage start.  │
│  (async inject)  │  One-way. Works in headless and interactive.     │
├──────────────────┼──────────────────────────────────────────────────┤
│  Board           │  Post to the communication board (3 scopes).     │
│  (persistent)    │  Bidirectional, searchable, survives restarts.   │
│                  │  Agents read at /next_action. Always works.      │
├──────────────────┼──────────────────────────────────────────────────┤
│  Question        │  AskUserQuestion — agent BLOCKS awaiting answer. │
│  (blocking)      │  Critical decisions only. Interactive mode only. │
├──────────────────┼──────────────────────────────────────────────────┤
│  Command Center  │  Three-panel session mode.                       │
│  (multi-scope)   │  Post at global / project / feature scope.       │
│                  │  See all agents at once. Dispatch cross-scope    │
│                  │  tasks. The UI shell around the board.           │
└──────────────────┴──────────────────────────────────────────────────┘
```

The **board** is the storage and retrieval layer.  
The **command center** is the UI for interacting with the board at all three scopes simultaneously.  
They are the same system — one backend, two views (single-feature CommsPanel + three-panel session mode).

---

---

## 18. Artifacts — Attaching Files to Boards

### 18.1 What an artifact is

An artifact is a file, document, image, URL, or code snippet attached directly to a
board. It behaves like any other message — it is embedded, stored in `comms_embeddings`,
and retrieved by semantic similarity at `/next_action` time.

The difference from a plain message: the content comes from an external source (a file
on disk, a URL, an uploaded PDF) rather than typed text.

### 18.2 Supported artifact types

| Type | Source | Text extraction | Best used for |
|---|---|---|---|
| `pdf` | uploaded file | pdfminer / pdfplumber | specs, design docs, requirements |
| `md` | file on disk | read as-is | CLAUDE.md, READMEs, plans |
| `code` | file on disk | read as-is | reference implementations, patterns |
| `image` | uploaded file | human writes description | wireframes, mockups, screenshots |
| `json` | file on disk | serialized + embedded | configs, schemas, API contracts |
| `url` | external link | fetched + stripped | external docs, GitHub issues, Figma |
| `snippet` | typed in Studio | embedded as-is | one-off code examples, SQL queries |

### 18.3 Embedding pipeline for artifacts

```
Human attaches design-spec.pdf to project board
    │
    ├── Text extraction (background thread)
    │   pdf  → pdfminer → plain text
    │   code → read verbatim
    │   url  → fetch → strip HTML → plain text
    │   image → human-supplied description string
    │
    ├── If content > 2000 tokens → chunk into overlapping segments
    │   Each chunk gets its own embedding + its own row in comms_embeddings
    │   All chunks share the same parent message_id
    │
    └── Store:
        comms_messages  → type='artifact', text=excerpt, artifact_path=...
        comms_embeddings → one row per chunk, all point to same message_id
```

The agent retrieves artifact chunks exactly like messages — the most relevant
chunk surfaces, along with the source file name and full path so the agent can
read the whole file if needed.

### 18.4 SQL additions

```sql
-- Extra columns on comms_messages
ALTER TABLE comms_messages ADD COLUMN artifact_path TEXT;
ALTER TABLE comms_messages ADD COLUMN artifact_type TEXT;
ALTER TABLE comms_messages ADD COLUMN artifact_url  TEXT;

-- Chunk tracking (one parent message → many embedding rows)
ALTER TABLE comms_embeddings ADD COLUMN chunk_index INTEGER DEFAULT 0;
ALTER TABLE comms_embeddings ADD COLUMN chunk_text  TEXT;
```

### 18.5 How an artifact looks in the board UI

```
10:30  👤 you  [attached to project board]
╔═ artifact ══════════════════════════════════════════════════════╗
║  📄  design-spec.pdf                            [project scope] ║
║  ─────────────────────────────────────────────────────────────  ║
║  "The editor must support side-by-side diff view with           ║
║   syntax highlighting. Line numbers must stay in sync           ║
║   when either panel is scrolled..."  [excerpt — 3 of 14 pages]  ║
║                                                                 ║
║  🔍 Agents can query this by content                            ║
╚═════════════════════════════════════════════════════════════════╝

10:31  👤 you  [attached to global board]
╔═ artifact ══════════════════════════════════════════════════════╗
║  📝  auth-pattern.ts                            [global scope]  ║
║  ─────────────────────────────────────────────────────────────  ║
║  export async function withAuth(req: Request) {                 ║
║    // Always use this pattern for authenticated routes...       ║
║  }                                                              ║
║  🔍 Agents can query this by content                            ║
╚═════════════════════════════════════════════════════════════════╝
```

### 18.6 What the agent sees

When an artifact chunk is retrieved at `/next_action`, it is injected like any
other board message but with the source path included:

```markdown
### 📎 Attached references
- [project / design-spec.pdf, chunk 2] "The editor must support side-by-side
  diff view with syntax highlighting. Line numbers must stay in sync..."
  → full file at: C:/Users/Yafit/pathly-adapters/docs/design-spec.pdf

- [global / auth-pattern.ts] "export async function withAuth(req: Request) {
  // Always use this pattern for authenticated routes..."
  → full file at: C:/Users/Yafit/pathly-adapters/lib/auth.ts
```

The agent can then Read the full file if it needs more than the retrieved chunk.

### 18.7 Power use cases

```
Attach to global board:
  → auth-pattern.ts       every agent forever uses this auth pattern
  → error-format.md       every agent formats errors consistently
  → eslint rules.json     every builder knows the lint rules

Attach to project board:
  → wireframes.pdf        every UI builder in every feature references the design
  → architecture.md       every agent knows the system design decisions
  → api-contract.json     every agent knows the API shape

Attach to feature board:
  → failing-test.log      next agent knows exactly what's broken
  → screenshot.png        visual context for the bug to fix
  → prior-attempt.ts      "don't repeat this approach — it failed because..."
```

### 18.8 New endpoint

```
POST /comms/attach
  Body: { feature, board, file_path?, url?, snippet?, artifact_type, description? }
  → extracts text, chunks if needed, embeds, stores
  → broadcasts COMMS_UPDATE SSE
  → returns { message_id, chunks_created, status }
```

---

## 19. Flexible Panel Layout

> **⚠ Superseded by [UI-DIRECTION.md](UI-DIRECTION.md) (2026-06-11).** The equal-panel
> add/remove/resize model here is replaced by full-area **board sections** plus a separate
> resizable **left sidebar** for All-Features navigation. The multi-select tab bar (§19.1) and
> resize/collapse mechanics (§19.4–19.5) carry over conceptually, but they now toggle and size
> *sections* and the *sidebar* — not co-equal panels. `commandCenterStore` (§19.6) gains
> `sidebarWidth`, `sidebarCollapsed`, and `mainFeature`; `PanelSlot`/`usePanelResize` become
> `BoardSection` + `FeatureSidebar`. See UI-DIRECTION.md §7 for the revised store + components.

### 19.1 Tab bar — multi-select toggles

The three board tabs at the top are **multi-select toggles**, not radio buttons.
Each click adds or removes that board's panel. The order the user clicks them
determines the left-to-right (or top-to-bottom) display order.

```
[🌐 Global ○]  [📁 Project ●]  [🎯 Feature ○]    [⊞ side by side]
  ↑ filled = panel visible           ↑ empty = board hidden
  click to add · click again to remove
  click order = panel order
```

### 19.2 Step-by-step interaction

**Step 1 — user clicks Project → 1-panel view**
```
[🌐 Global ○]  [📁 Project ●]  [🎯 Feature ○]    [⊞]

┌──────────────────────────────────────────────────────┐
│  📁  PROJECT — pathly-adapters                       │
│  📌 shadcn/ui · /lib/auth.ts · TS strict             │
│  ...                                                 │
│  [ Project decision... ]  [Send]                     │
└──────────────────────────────────────────────────────┘
```

**Step 2 — user also clicks Feature → 2-panel side by side**
```
[🌐 Global ○]  [📁 Project ●]  [🎯 Feature ●]    [⊞]

┌───────────────────────────┬──────────────────────────┐
│  📁  PROJECT              │  🎯  FEATURE             │
│  ...                      │  send-to-agent-diff      │
│  [ Project msg... ] [Send]│  [ Feature msg... ][Send]│
└───────────────────────────┴──────────────────────────┘
  (clicked 1st)               (clicked 2nd = rightmost)
```

**Step 3 — user also clicks Global → 3-panel side by side**
```
[🌐 Global ●]  [📁 Project ●]  [🎯 Feature ●]    [⊞]

┌─────────────┬────────────────┬──────────────────────┐
│  📁 PROJECT │  🎯 FEATURE    │  🌐 GLOBAL           │
│  ...        │  ...           │  ...                 │
│  [Send]     │  [Send]        │  [Send]              │
└─────────────┴────────────────┴──────────────────────┘
 (click 1)     (click 2)         (click 3 = rightmost)
```

**Step 4 — user clicks Project again → removes that panel, gap closes**
```
[🌐 Global ●]  [📁 Project ○]  [🎯 Feature ●]    [⊞]

┌──────────────────────────┬───────────────────────────┐
│  🎯  FEATURE             │  🌐  GLOBAL               │
│  ...                     │  ...                      │
│  [Send]                  │  [Send]                   │
└──────────────────────────┴───────────────────────────┘
  remaining panels expand to fill the freed space
```

### 19.3 Layout direction toggle — side by side ↔ stacked

The `[⊞]` button toggles between two layout directions.
Its icon and label flip to show the current state:

**`[⊞ side by side]` — panels are columns (horizontal)**
```
[🌐 Global ●]  [📁 Project ●]  [🎯 Feature ●]    [⊞ side by side]

┌─────────────┬─────────────────┬──────────────────────┐
│  🌐 GLOBAL  │  📁 PROJECT     │  🎯 FEATURE          │
│  ...        │  ...            │  ...                 │
│  [Send]     │  [Send]         │  [Send]              │
└─────────────┴─────────────────┴──────────────────────┘
          ↑ drag handles between columns to resize
```

**`[☰ stacked]` — panels are rows (vertical)**
```
[🌐 Global ●]  [📁 Project ●]  [🎯 Feature ●]    [☰ stacked]

┌──────────────────────────────────────────────────────┐
│  🌐  GLOBAL                                          │
│  ...                                                 │
│  [ Global policy... ]  [Send]                        │
├──────────────────────────────────────────────────────┤  ← drag to resize row
│  📁  PROJECT — pathly-adapters                       │
│  ...                                                 │
│  [ Project decision... ]  [Send]                     │
├──────────────────────────────────────────────────────┤  ← drag to resize row
│  🎯  FEATURE — send-to-agent-diff                    │
│  ...                                                 │
│  [ Feature message... ]  [Send]                      │
└──────────────────────────────────────────────────────┘
```

### 19.4 Collapsing panels — works in both layout modes

Every panel can be collapsed regardless of layout direction.
The visual form of the collapsed state matches the layout direction:

```
                Side by side          Stacked
                ─────────────         ──────────────
Full panel      full width column     full height row
Collapsed       ~48px vertical strip  ~40px horizontal bar
Badge           shown on strip        shown inline on bar
Re-expand       click anywhere        click anywhere
Toggle button   [▸] at strip bottom   [▸] at bar right edge
```

**Stacked mode — collapsed panels become thin horizontal bars:**

```
┌──────────────────────────────────────────────────────┐
│  🌐  GLOBAL                       [2 decisions] [▸]  │  ← thin bar
├──────────────────────────────────────────────────────┤
│  📁  PROJECT — pathly-adapters                 [▾]   │
│  ...full thread visible...                           │
│  [Send]                                              │
├──────────────────────────────────────────────────────┤
│  🎯  FEATURE — send-to-agent-diff   [1 question][▸]  │  ← thin bar
└──────────────────────────────────────────────────────┘
```

**Side-by-side mode — collapsed panels become thin vertical strips (~48px):**

```
┌──┬──────────────────┬──────────────────────────────────────────┐
│🌐│  📁 PROJECT  [▾] │  🎯 FEATURE                          [▾] │
│  │                  │                                          │
│② │  📌 Decisions    │  ...full thread, more space now...       │
│  │  ...             │                                          │
│d │  [Send]          │  [Send]                                  │
│e │                  │                                          │
│c │                  │                                          │
│▸ │                  │                                          │
└──┴──────────────────┴──────────────────────────────────────────┘
↑ ~48px strip — icon + badge + [▸] at bottom
  click anywhere on strip to expand
```

**Two panels collapsed — one panel takes all available space:**

```
┌──┬──────────────────────────────────────────────────────────┬──┐
│🌐│  📁 PROJECT                                          [▾] │🎯│
│  │                                                          │  │
│② │  ...full thread with lots of room...                     │①│
│  │                                                          │  │
│d │  [ Project decision... ]  [Send]                         │? │
│e │                                                          │p │
│c │                                                          │e │
│  │                                                          │n │
│▸ │                                                          │▸ │
└──┴──────────────────────────────────────────────────────────┴──┘
  expanded panel fills all freed space automatically
```

The collapsed strip shows: board icon + pending/unread badge count.
Clicking anywhere on the strip (not just `[▸]`) re-expands it to its last saved width.

### 19.5 Resizing

- **Side-by-side**: drag the vertical handle between columns. Minimum width **280px** per panel.
- **Stacked**: drag the horizontal handle between rows. Minimum height **160px** per panel.
- Dragging past the minimum snaps to it — panels never disappear from a resize.
- When the total window width is too narrow for all visible panels at 280px,
  the rightmost panel collapses to an icon strip until the window is widened.

### 19.6 Panel config stored in Studio

```ts
// store/commandCenterStore.ts
interface PanelConfig {
  // order reflects click order = display order
  panels: Array<'feature' | 'project' | 'global'>
  direction: 'row' | 'column'          // side-by-side vs stacked
  sizes: Partial<Record<string, number>> // px width (row) or px height (column)
  collapsed: Partial<Record<string, boolean>> // stacked-mode collapse state
  minSize: 280                          // px, not user-configurable
}

const DEFAULT: PanelConfig = {
  panels: [],          // nothing selected until user clicks a tab
  direction: 'row',
  sizes: {},
  collapsed: {},
  minSize: 280,
}
```

Persisted to `localStorage` under `pathly-command-center-layout`.

### 19.7 Panel header anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│  📁 PROJECT — pathly-adapters            [⊕ attach]  [▾]  [×]  │
│                                               ↑        ↑    ↑   │
│                                          attach file  collapse  remove
│                                          or URL       row      panel
└──────────────────────────────────────────────────────────────────┘
```

- **[⊕ attach]** — opens file picker / URL input to attach an artifact to this board
- **[▾] / [▸]** — collapse / expand (stacked mode only)
- **[×]** — deselects this panel (same as clicking the tab again); board data is not deleted

---

## 20. Understanding Summary

```
┌────────────────────────────────────────────────────────────────────┐
│  THE COMPLETE MENTAL MODEL                                         │
│                                                                    │
│  Board = sqlite-vec vector DB at one scope                        │
│  Panel = a resizable window into one board                        │
│  Session mode = 1, 2, or 3 panels, any order, any width           │
│                                                                    │
│  Each feature defines board_scope:                                │
│    which boards its agents READ from at /next_action              │
│    { feature: true, project: true, global: true }                 │
│                                                                    │
│  Human writes to boards via:                                      │
│    messages (nudge / decision / task / question)                  │
│    artifacts (pdf / code / image / url → embedded + chunked)      │
│                                                                    │
│  Agents write to boards via:                                      │
│    status / question / discovery / warning / escalation           │
│    POST /comms/post  during their work                            │
│                                                                    │
│  At /next_action → FSM:                                           │
│    1. embeds the next task description                            │
│    2. queries all enabled boards by vector similarity             │
│    3. retrieves top-K messages + artifact chunks                  │
│    4. injects into agent_hint.instructions                        │
│                                                                    │
│  Result: every agent starts with the most relevant               │
│  organizational memory — from this feature, this project,         │
│  and the whole org — without you having to repeat yourself.       │
└────────────────────────────────────────────────────────────────────┘
```

---

---

## 21. Implementation Assessment — Codebase Audit (2026-06-10)

This section records exactly what exists in the codebase today versus what needs
to be built. Every component of the communication board is absent — nothing has
been started. The audit below gives precise file paths so each task can be picked
up without further exploration.

### 21.1 Database layer

| Component | Status | Notes |
|---|---|---|
| `comms_messages` table | ❌ MISSING | Not in `db/migrations.py` |
| `comms_embeddings` virtual table (sqlite-vec) | ❌ MISSING | Not in `db/migrations.py` |
| All other tables (14 total) | ✅ EXISTS | fsm_events, fsm_state, runner_state, agent_invocations, feedback_items, etc. |

**What is already in `src/pathly_orchestrator/db/migrations.py`:**
The migration system exists and is clean. Adding the two comms tables is a
straightforward append to the existing migration block. No schema changes to
existing tables are needed.

**What needs to be added:**
```sql
-- comms_messages: one row per message
CREATE TABLE IF NOT EXISTS comms_messages (
    id               TEXT PRIMARY KEY,
    board            TEXT NOT NULL,      -- 'feature' | 'project' | 'global'
    scope            TEXT NOT NULL,      -- feature name, project root, or 'global'
    from_agent       TEXT NOT NULL,
    to_agent         TEXT NOT NULL DEFAULT '*',
    type             TEXT NOT NULL,      -- nudge/question/answer/status/decision/...
    text             TEXT NOT NULL,
    options          TEXT,               -- JSON array (for question type)
    reply_to         TEXT,
    stage            TEXT,
    conv             INTEGER,
    ts               TEXT NOT NULL,
    read_by          TEXT DEFAULT '[]',
    acknowledged_by  TEXT DEFAULT '[]',
    status           TEXT DEFAULT 'pending',
    deleted_at       TEXT,
    promoted_to      TEXT,
    promoted_from    TEXT,
    original_scope   TEXT,
    artifact_path    TEXT,
    artifact_type    TEXT,
    artifact_url     TEXT,
    task_status      TEXT,
    assigned_to_stage TEXT,
    assigned_to_agent TEXT,
    embedding_model  TEXT
);

-- comms_embeddings: sqlite-vec virtual table (requires sqlite-vec extension)
CREATE VIRTUAL TABLE IF NOT EXISTS comms_embeddings USING vec0(
    message_id TEXT PRIMARY KEY,
    embedding  FLOAT[384],
    chunk_index INTEGER DEFAULT 0,
    chunk_text  TEXT
);
```

### 21.2 DB query module

| Component | Status | File |
|---|---|---|
| `comms.py` query module | ❌ MISSING | `src/pathly_orchestrator/db/queries/comms.py` |
| All other query modules (15 files) | ✅ EXISTS | fsm_events.py, fsm_state.py, runner_state.py, etc. |

**What needs to be created — `db/queries/comms.py`:**
```python
# Functions needed:
post_message(board, scope, from_agent, to_agent, type, text, ...)  → str (message_id)
get_messages(board, scope, type=None, status=None, limit=50)        → list[dict]
acknowledge_message(message_id, agent)                              → None
answer_question(question_id, answer_text, option_id=None)          → str (answer message_id)
store_embedding(message_id, embedding, chunk_index, chunk_text)    → None
search_by_embedding(embedding, boards, scopes, k=6)                 → list[dict]
get_pending_decisions(boards, scopes)                               → list[dict]
get_trash(scope)                                                    → list[dict]
restore_messages(message_ids)                                       → None
purge_expired_trash(days=30)                                        → int (count purged)
get_promotable_messages(scope)                                      → list[dict]
```

### 21.3 HTTP blueprint

| Component | Status | File |
|---|---|---|
| `comms.py` blueprint | ❌ MISSING | `src/pathly_orchestrator/http_server/blueprints/comms.py` |
| All other blueprints (11 files) | ✅ EXISTS | runner.py, fsm.py, health.py, telemetry.py, etc. |

**What needs to be created — routes:**
```
POST /comms/post        → post a message to a board
GET  /comms             → fetch messages (filterable)
POST /comms/search      → semantic search across boards
POST /comms/acknowledge → mark message read by agent
POST /comms/answer      → answer a question
POST /comms/attach      → attach a file/url artifact
GET  /comms/trash       → list trashed messages for a scope
POST /comms/restore     → restore trashed messages
```

Blueprint must be registered in `src/pathly_orchestrator/http_server/app.py`
(same pattern as all other blueprints — one line: `app.register_blueprint(comms_bp)`).

### 21.4 SSE system

| Component | Status | File |
|---|---|---|
| `_comms_clients` registry | ❌ MISSING | `src/pathly_orchestrator/http_server/sse.py` |
| `COMMS_UPDATE` broadcast function | ❌ MISSING | `src/pathly_orchestrator/http_server/sse.py` |
| `GET /events/comms` SSE stream endpoint | ❌ MISSING | `src/pathly_orchestrator/http_server/blueprints/streams.py` |
| Existing runner SSE (`_runner_clients`, `_broadcast_runner`) | ✅ EXISTS | `sse.py` |

**What needs to be added to `sse.py`:**
```python
_comms_clients: dict[str, list] = {}   # scope → list of SSE queues

def _broadcast_comms(scope: str, event: dict) -> None:
    """Broadcast a COMMS_UPDATE event to all Studio clients watching this scope."""
    ...
```

**What needs to be added to `streams.py`:**
```python
@bp.route('/events/comms')
def comms_stream():
    scope = request.args.get('scope', 'global')
    # SSE generator — same pattern as /events/runner
    ...
```

### 21.5 FSM context injection

| Component | Status | File / Location |
|---|---|---|
| `## Communication Board` block in prompt | ❌ MISSING | `src/pathly_orchestrator/fsm_ops.py` |
| `retrieve_board_context()` function | ❌ MISSING | Needs to be written |
| `build_prompt()` injection point | ✅ EXISTS | `fsm_ops.py:158–199` |
| `## Current task` block | ✅ EXISTS | `fsm_ops.py` |
| `## Pipeline History` block | ✅ EXISTS | `runner/history.py` → `build_pipeline_history_block()` |

**What the current `build_prompt()` injects (lines 158–199):**
```
## Current task
Feature: {feature_name}
State: {state_name}
Storage path: {storage_path}

## Pipeline History
- **{agent} (conv {conv_num})**: {summary}
```

**What needs to be added after `## Pipeline History`:**
```python
# In fsm_ops.py build_prompt():
board_context = retrieve_board_context(topic, project_root, task_description)
if board_context:
    prompt += "\n\n" + board_context   # appends ## Communication Board block
```

`retrieve_board_context()` needs to be a new function in `fsm_ops.py` (or a
separate `runner/comms_context.py` module) that embeds the task description,
queries all enabled boards, and formats the markdown block.

### 21.6 STATE.json schema

| Component | Status | Notes |
|---|---|---|
| `board_scope` field | ❌ MISSING | Not present in any STATE.json |
| Existing STATE.json fields | ✅ EXISTS | convs_total, convs_done, current, updated_at, conv_start_sha, build_baseline |

**What needs to be added** (defaulted by the FSM if absent):
```json
{
  "board_scope": {
    "feature": true,
    "project": true,
    "global": true
  }
}
```

`write_state()` in `db/queries/fsm_state.py` already exists — it just needs to
preserve `board_scope` when it writes (currently it only writes the fields it
knows about). Or the FSM reads it separately before calling write_state.

### 21.7 Python dependencies

| Dependency | Status | Needed for |
|---|---|---|
| `sqlite-vec` | ❌ MISSING | Vector similarity search |
| `sentence-transformers` | ❌ MISSING | Generating message embeddings |
| `pyyaml>=6.0,<7` | ✅ EXISTS | Already in pyproject.toml |
| `flask>=2.3,<4` | ✅ EXISTS | Already in pyproject.toml |

**Note on sqlite-vec:** The extension must be loaded at DB connection time:
```python
import sqlite_vec
conn.enable_load_extension(True)
sqlite_vec.load(conn)
```
This needs to be added to `db/connection.py` where `get_db()` creates connections.

**Note on sentence-transformers:** Loading the model takes ~1–2s on first use.
The embedding worker should load it once at server startup and keep it in memory.

**What needs to be added to `pyproject.toml`:**
```toml
[project]
dependencies = [
    "pyyaml>=6.0,<7",
    "flask>=2.3,<4",
    "sqlite-vec>=0.1.6",
    "sentence-transformers>=2.7.0",
]
```

### 21.8 Studio stores

| Component | Status | File |
|---|---|---|
| `commsStore.ts` | ❌ MISSING | `studio/src/renderer/src/store/commsStore.ts` |
| `commandCenterStore.ts` | ❌ MISSING | `studio/src/renderer/src/store/commandCenterStore.ts` |
| `runnerStore.ts` | ✅ EXISTS | Has PhaseSummaryEntry, appendPhaseSummary, etc. |
| `terminalStore.ts` | ✅ EXISTS | Tab registry, openTab, addTab |
| `chatStore.ts` | ✅ EXISTS | Existing HQ chat — good pattern reference for commsStore |
| `notificationStore.ts` | ✅ EXISTS | Toast categories incl. phase_summary |
| `toastStore.ts` | ✅ EXISTS | push() helper |

**`commsStore.ts` needs to manage:**
```ts
messages: CommsMessage[]          // current board thread
board: 'feature' | 'project' | 'global'
scope: string                     // feature name / project root / 'global'
pendingCount: number              // unread/pending badge
appendMessage(msg: CommsMessage): void
markRead(messageId: string): void
setBoard(board, scope): void
```

**`commandCenterStore.ts` needs to manage:**
```ts
panels: Array<'feature' | 'project' | 'global'>  // visible panels + order
direction: 'row' | 'column'                       // side-by-side vs stacked
sizes: Record<string, number>                     // saved widths/heights
collapsed: Record<string, boolean>               // per-panel collapse state
```

### 21.9 Studio components

| Component | Status | Location |
|---|---|---|
| `CommsPanel/` | ❌ MISSING | `studio/src/renderer/src/components/HQ/CommsPanel/` |
| `CommandCenter/` | ❌ MISSING | `studio/src/renderer/src/components/HQ/CommandCenter/` |
| `HQ/` folder (44 files) | ✅ EXISTS | All existing panels, cards, and controls |
| `RunnerLogCard/` | ✅ EXISTS | Good pattern reference for a log-style panel |
| `AgentQuestionCard/` | ✅ EXISTS | Good pattern reference for question + options UI |
| `ChatPanel/` + `MessageList/` | ✅ EXISTS | Good pattern reference for message thread |

**`CommsPanel/` sub-components needed:**
```
CommsPanel/
  CommsPanel.tsx          ← outer shell: scope selector, tabs, send bar
  CommsPanel.module.css
  CommsMsgList.tsx        ← message thread (reuse pattern from MessageList)
  CommsMsgList.module.css
  CommsMsgCard.tsx        ← individual message card with type-specific rendering
  CommsMsgCard.module.css
  CommsInput.tsx          ← message compose bar with type picker
  CommsInput.module.css
  useCommsPanel.ts        ← SSE subscription, send handlers, pending count
```

**`CommandCenter/` sub-components needed:**
```
CommandCenter/
  CommandCenter.tsx       ← outer shell: tab toggles, layout toggle, panel grid
  CommandCenter.module.css
  PanelSlot.tsx           ← one resizable, collapsible slot holding a CommsPanel
  PanelSlot.module.css
  usePanelResize.ts       ← drag-to-resize logic (width/height per slot)
  useCommandCenter.ts     ← panel state: which boards visible, order, direction
```

### 21.10 Skills

| Skill | Status | Notes |
|---|---|---|
| `comms-query.md` | ❌ MISSING | Agent skill to query the board mid-work |
| `log-board-message.md` | ❌ MISSING | Agent skill to post status/discovery |
| Board reading in `build.md` | ❌ MISSING | `build.md` has no reference to boards |
| Board reading in `review.md` | ❌ MISSING | `review.md` has no reference to boards |
| `log-agent-done.md` | ✅ EXISTS | Writes AGENT_DONE to DB — similar pattern needed for board |
| `log-phase.md` | ✅ EXISTS | Phase summary logging — good pattern reference |

---

## 22. Revised Implementation Phases (with precise file targets)

### Phase 1 — Backend core (no UI, fully testable via curl)

**Step 1 — Dependencies**
- File: `pyproject.toml`
- Add: `sqlite-vec>=0.1.6`, `sentence-transformers>=2.7.0`
- Run: `pip install sqlite-vec sentence-transformers` to verify

**Step 2 — DB connection: load sqlite-vec extension**
- File: `src/pathly_orchestrator/db/connection.py`
- Add: `import sqlite_vec` + `sqlite_vec.load(conn)` in `get_db()`
- Test: `from pathly_orchestrator.db.connection import get_db; get_db()`

**Step 3 — DB migrations: add comms tables**
- File: `src/pathly_orchestrator/db/migrations.py`
- Add: `comms_messages` table + `comms_embeddings` virtual table (see §21.1)
- Run: `python -m pathly_orchestrator.db.migrations` to verify

**Step 4 — DB queries**
- File: `src/pathly_orchestrator/db/queries/comms.py` (new file)
- Implement all 11 functions listed in §21.2
- Export from `db/queries/__init__.py`

**Step 5 — Embedding worker**
- File: `src/pathly_orchestrator/runner/embeddings.py` (new file)
- `embed(text: str) → list[float]` — loads `all-MiniLM-L6-v2` once, cached
- `embed_async(message_id, text)` — background thread wrapper
- Called by `/comms/post` after storing the message

**Step 6 — SSE: add comms channel**
- File: `src/pathly_orchestrator/http_server/sse.py`
- Add `_comms_clients` dict + `_broadcast_comms(scope, event)` function

**Step 7 — HTTP blueprint**
- File: `src/pathly_orchestrator/http_server/blueprints/comms.py` (new file)
- Implement 8 routes (see §21.3)
- Register in: `src/pathly_orchestrator/http_server/app.py`

**Step 8 — SSE stream endpoint**
- File: `src/pathly_orchestrator/http_server/blueprints/streams.py`
- Add `GET /events/comms?scope=<scope>` route

**Step 9 — FSM injection**
- File: `src/pathly_orchestrator/runner/comms_context.py` (new file)
- `retrieve_board_context(topic, project_root, task_desc, board_scope) → str`
- File: `src/pathly_orchestrator/fsm_ops.py` lines ~195–199
- Add call to `retrieve_board_context()` + append result to prompt

**Step 10 — STATE.json: board_scope default**
- File: `src/pathly_orchestrator/db/queries/fsm_state.py`
- When reading STATE.json, default `board_scope` to `{feature:true, project:true, global:true}` if absent

**Phase 1 deliverable:** Post messages via curl → verify they appear in next
agent's prompt. Zero Studio changes needed.

---

### Phase 2 — Studio CommsPanel components (standalone)

> **Revised 2026-06-11 — see [UI-DIRECTION.md](UI-DIRECTION.md).** No standalone single-feature
> CommsPanel HQ tab ships. Phase 2 builds and verifies the **reusable CommsPanel component
> library** against the live SSE stream; Phase 4 then hosts it in the CommandCenter workspace.
> Phase 2 and Phase 4 merge at the UI layer — there is no intermediate one-board-at-a-time tab.

**Step 11 — commsStore.ts**
- File: `studio/src/renderer/src/store/commsStore.ts` (new file)
- Pattern reference: `chatStore.ts` (same message list pattern)

**Step 12 — SSE handler**
- File: `studio/src/renderer/src/components/HQ/useHQ.tsx`
- Add `COMMS_UPDATE` event handler → `commsStore.appendMessage()`
- Add `comms_update` to `NotifCategory` in `notificationStore.ts`

**Step 13 — CommsPanel component library (no HQ tab wiring)**
- Folder: `studio/src/renderer/src/components/HQ/CommsPanel/`
- Pattern references: `MessageList/` (thread), `AgentQuestionCard/` (options), `ChatInput/` (compose bar)
- 5 files: CommsPanel, CommsMsgList, CommsMsgCard, CommsInput, useCommsPanel

**Phase 2 deliverable:** Verified CommsPanel component library — message thread,
question cards, decision pinning, compose bar — driven by the live `/events/comms`
SSE stream. Reused as-is by the CommandCenter (Phase 4) and ConsultPanel (Phase 5).

> **Note:** `commandCenterStore.ts` and the CommandCenter component (formerly steps
> 12 and 15 here) move to **Phase 4** below — they belong to the workspace, not the
> standalone component library. The workspace uses `BoardSection` + `FeatureSidebar`,
> **not** the `PanelSlot`/`usePanelResize` equal-panel model. See UI-DIRECTION.md §7.

---

### Phase 3 — Agent skill integration

**Step 16 — comms-query skill**
- File: `src/pathly_data/core/skills/comms-query.md` (new file)
- Agents use `GET /comms/search` to query board mid-work

**Step 17 — log-board-message skill**
- File: `src/pathly_data/core/skills/log-board-message.md` (new file)
- Agents use `POST /comms/post` to post status/discovery/warning

**Step 18 — Update build.md**
- File: `src/pathly_data/core/skills/team/build.md` (and `development/build.md`)
- Add: read board at start (via context already injected), post status at key milestones

**Step 19 — Update review.md**
- File: `src/pathly_data/core/skills/team/review.md`
- Add: post warnings as board messages, not only as REVIEW_FAILURES.md blocks

---

### Phase 4 — Command center + cross-feature memory & artifacts

> **Revised 2026-06-11 — see [UI-DIRECTION.md](UI-DIRECTION.md).** The CommandCenter
> workspace (full-screen canvas: resizable left **FeatureSidebar** for All-Features
> navigation + full-area **BoardSection**s for content + `[Presets ▾]`) lands here, hosting the
> Phase 2 CommsPanel library. It replaces the equal-panel `PanelSlot` model from SPEC §16/§19.

**Step 20a — commandCenterStore.ts**
- File: `studio/src/renderer/src/store/commandCenterStore.ts` (new file)
- State: `sections[]`, order, `sizes`, `preset`, `sidebarWidth`, `sidebarCollapsed`, `mainFeature`
- Persists to `localStorage` under `pathly-command-center-layout`

**Step 20b — CommandCenter workspace**
- Folder: `studio/src/renderer/src/components/HQ/CommandCenter/`
- Files: `CommandCenter.tsx`, `FeatureSidebar.tsx` (left nav, accordion, "Set as main ↗"),
  `BoardSection.tsx` (full-area section hosting a CommsPanel), `useSectionResize.ts`,
  `useCommandCenter.ts`, CSS modules
- **Not** `PanelSlot`/`usePanelResize` — see UI-DIRECTION.md §7

**Step 20 — Artifact ingestion**
- File: `src/pathly_orchestrator/runner/artifacts_ingestion.py` (new file)
- PDF text extraction, URL fetch, code file reading, chunking
- Called by `POST /comms/attach`

**Step 21 — Project + Global board seeding**
- When a new feature starts, seed its board with relevant project/global decisions
- Retrieved by similarity to the feature description

**Step 22 — Promote-before-delete**
- Studio: show promotion dialog when a feature is deleted
- Backend: `GET /comms/promotable?scope=<feature>` + `POST /comms/promote`

**Step 23 — Trash + auto-purge**
- Nightly cron (or on-startup check): `purge_expired_trash(days=30)`
- Studio: Trash view in sidebar

---

---

## 23. Phase 5 — Board-Storm (Consultation Mode)

> Full design in [BOARD-STORM.md](BOARD-STORM.md). Summarised here for the spec record.

### 23.1 What it is

A pre-pipeline "thinking mode." The user opens a blank board, posts an idea, and
a headless consultant agent responds with an **artefact** (questions, architecture
diagram, trade-off analysis) instead of a chat message. The user replies or
annotates; the agent revises. This loops until the user is satisfied, then one
click converts the session into a pipeline-ready feature with plan files
pre-populated.

```
Chat:         message → reply → message  (ephemeral, linear)
Board-storm:  request → ARTEFACT → annotate → revised ARTEFACT  (persistent, structured)
              The artefact is the unit of communication, not the message.
```

### 23.2 Why it ships before the command center (Phase 4)

```
Board-storm FILLS boards with rich content.
The command center SEARCHES across filled boards.
You must fill before you search → build the producer first.

Board-storm needs:  one board + headless agent (exists) + CommsPanel (Phase 2)
                    → ~500 lines of new Python
Command center needs: vector search across 100s of boards + 3-panel Electron layout
                    → ~4 weeks of Studio work
```

### 23.3 It is 80% reuse

```
Board-storm  =  comms board (Phase 1)
              + headless agent invocation (runner/invoke.py — ALREADY EXISTS)
              + CommsPanel UI (Phase 2)
              + a small consultation loop (the only new bit)
```

### 23.4 The consultation FSM (separate from the 8-stage pipeline)

```
OPEN ──user posts request──▶ THINKING ──agent posts artefact──▶ AWAITING
AWAITING ──user replies──▶ THINKING                              (loop)
AWAITING ──"Start pipeline"──▶ CONVERTING ──plan files──▶ DONE
```

### 23.5 The conversion step — discussion becomes a feature

```
draft_spec artefact ───────────▶ USER_STORIES.md
implementation_plan artefact ──▶ IMPLEMENTATION_PLAN.md
all artefacts ─────────────────▶ feature board messages (pre-filled)
STATE.json ────────────────────▶ { current: "PLAN" }  (storm already done)
register in main FSM ──────────▶ feature enters the team pipeline
```

The builder later starts with a `## Communication Board` block already full of
everything the consultation decided — more context than any current Pathly
pipeline gives an agent.

### 23.6 Build steps (file targets)

```
1. src/pathly_data/core/skills/consult.md          consultant skill (new)
2. src/pathly_data/core/agents/consultant.md        consultant role (new, opus)
3. app_settings key consult:{session_id}            session state (no new table)
4. http_server/blueprints/consult.py                5 routes (new)
5. supervisor/consult.py                            FSM loop driver (new)
6. runner/consult_convert.py                        artefacts → plan files (new)
7. studio/components/HQ/ConsultPanel/               reuses CommsPanel (new)
```

Prerequisite: comms board Phase 1 + Phase 2 shipped.

---

## 24. Final Phase Ordering

```
Phase 1    Backend injection only                          ~3 weeks
           Post nudges via curl → verify in agent prompts; zero Studio changes

Phase 2    Studio CommsPanel (one feature at a time)        ~2 weeks
           Message thread · question cards · SSE updates

Phase 3    Skill integration                                ~1 week
           Agents post status/warnings · build.md reads board

Phase 5    Board-Storm consultation mode                    ~4 weeks
           New consultation flow · consultant agent · convert to pipeline
           ↑ before Phase 4 — fills boards with content, more user-facing value

Phase 4    Cross-feature memory + command center            ~6 weeks
           Three-panel layout · global seeding · artifacts · vector search at scale
           ↑ last — searches across the boards that Phase 5 filled
```

Board-storm (Phase 5) intentionally precedes cross-feature memory (Phase 4):
the consultation mode creates the rich board content that makes cross-feature
retrieval valuable. You need to fill the boards before you need to search across them.

---

---

## 25. Flow Architecture Change — STORM Removed, Consult Flow Added

> Detail in [STORM-REMOVAL.md](STORM-REMOVAL.md) (audit + removal plan) and
> [BOARD-STORM.md](BOARD-STORM.md) §15 (the multi-agent consultation flow).

### 25.1 The change

The always-skipped STORM phase is removed from the team flow. A separate **consult flow**
(the multi-agent panel) replaces it. The board is what powers that flow, which is why the
board backend (Phase 1) ships first.

```
BEFORE
  team:  STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE
          ↑ one-shot, always skipped

AFTER
  consult:  OPEN → CONSULTING ⇄ AWAITING → CONVERTING → DONE
            (PO + architect + designer + planner — each fills its own template)
                │  convert = move filled template files into pathly/plans/<feature>/
                ▼
  team:     PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE
            (enters at PLAN, pre-filled; PLAN is a fast integration/validation pass)
```

### 25.2 Per-expert template ownership

The consult flow distributes plan-template authoring across the panel; the planner
integrates last (full table in BOARD-STORM.md §15.3):

| Expert | Templates |
|---|---|
| po | `USER_STORIES.md`, `EDGE_CASES.md`, `HAPPY_FLOW.md` |
| architect | `ARCHITECTURE_PROPOSAL.md`, `IMPLEMENTATION_PLAN.md`, `FLOW_DIAGRAM.md` |
| designer | `DESIGN.md` (UI only) |
| planner | `FEATURE_INDEX.md`, `PROGRESS.md`, `CONVERSATION_PROMPTS.md` |

### 25.3 Removal surface (summary)

Mandatory to remove the state: **Tier 1** (`team.flow.yaml`, `test.flow.yaml`,
`fsm_ops.py`, `blueprints/skills.py`) + **Tier 2** (≈7 Studio state-list files) +
a `STORMING→PLANNING` recovery shim for in-flight features. The FSM has no hardcoded
state enum in Python — states are data-driven from the flow YAML — so the backend surface
is small. Skill/agent/doc rewiring (Tiers 3–6) follows as the consult flow lands; telemetry
keeps `storm` valid for back-compat (Tier 7). Full tier table in STORM-REMOVAL.md.

### 25.4 Sequencing vs the comms-board phases

```
comms-board Phase 1   board backend (this plan folder)        ← powers everything below
        ▼
STORM-REMOVAL Steps 1–3   cut STORMING from pipeline + UI + recovery shim  (independent, can land early)
        ▼
comms-board Phase 5   consult flow = the multi-agent panel over the board
        │             (PO + architect + designer + planner, per-expert templates)
        ▼
team flow             now enters at PLAN, pre-filled by the consult flow
```

---

*Spec version 6.1 — UI direction revised (see [UI-DIRECTION.md](UI-DIRECTION.md)): §7
(standalone CommsPanel tab), §16 (three-equal-panel command center), and §19 (flexible
panel layout) superseded by a full-screen workspace — resizable left sidebar for All-Features
navigation + full-area board sections + "Set as main feature" swap + asymmetric widths.
§22 Phase 2/4 build steps revised (CommsPanel components standalone → CommandCenter hosts them;
PanelSlot → BoardSection + FeatureSidebar). Prior: v6.0 — Flow architecture change: STORM
removed from the team flow (audit in STORM-REMOVAL.md), replaced by the multi-agent
consultation flow (BOARD-STORM.md §15) with per-expert template ownership; team flow enters at
PLAN pre-filled. v5.0 folded Board-Storm in as Phase 5 with phase ordering 1→2→3→5→4.*
