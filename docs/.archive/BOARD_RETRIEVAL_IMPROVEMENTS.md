# Board Retrieval Improvements

> **⚠️ Implementation note:** This document is a background reference only.
> The authoritative implementation instructions are in
> `pathly/plans/comms-board/IMPLEMENTATION_PLAN.md` (Phase 1.4a–d) and
> `pathly/plans/comms-board/CONVERSATION_PROMPTS.md` (Conv 4).
> Where this doc conflicts with those files, **the plan files take precedence**.
> Known conflicts: (1) migration method — use `_add_additive_migrations()` tuples,
> NOT standalone `ALTER TABLE` statements; (2) route auth — comms routes do NOT use
> `@require_secret`; auth is middleware-level.

**Status:** Implemented in plan as Phase 1.4 (Conv 4 — TODO)  
**Why it matters:** The comms board is Pathly's primary differentiator over
every competing framework — it gives agents governed, cross-feature, tiered
memory that survives across sessions. But the retrieval layer that delivers
that memory to agents has three correctness gaps that undermine the guarantee.
Until these are fixed, the board can make the system *less* reliable than no
board at all (injecting stale/contradictory constraints with false confidence).

This document describes three independent improvements, each shippable as its
own PR.

---

## Background: what the board does today

Every `/next_action` call runs `retrieve_board_context()`, which builds a
`## Communication Board` block injected into `agent_hint.instructions`:

```
retrieve_board_context()
    │
    ├── Path A (deterministic): get_pending_decisions()
    │     Plain SQL: type='decision' AND status='pending'
    │     Always injected, no vector search
    │
    └── Path B (semantic): search_by_embedding()
          Cosine scan, k = feature:3 / project:2 / global:1
          Top matches from each tier, recency fallback if no model
```

Both paths dump results into one `## Communication Board` block with no
label distinguishing "hard constraint you must follow" from "possibly relevant
recent context." An agent cannot tell them apart.

---

## PR 1 — `superseded_by`: fix stale decision injection

### The problem

There is no way to mark a decision as replaced by a newer one. Once a decision
is posted and an agent reads it, it cannot be retracted (`soft_delete` returns
`'locked'` once any agent has acknowledged the message). If a team reverses a
decision, the old one keeps being injected into every future agent alongside the
new one.

```
Example:
  Day 1 — decision posted: "Use PostgreSQL"   → status='pending', always injected
  Day 3 — team reverses:   "Use SQLite"       → new decision posted
  Day 4 — builder agent receives both:
    📌 Use PostgreSQL   ← stale, contradicts current intent
    📌 Use SQLite       ← current
  Agent picks one. Coin flip.
```

### The fix

Add a `superseded_by` column to `comms_messages`. When a new decision is posted
that replaces an older one, the caller can set `superseded_by = <new_message_id>`
on the old record. `get_pending_decisions()` filters `WHERE superseded_by IS NULL`
so superseded decisions are silently excluded from injection.

#### 1a. Migration — add the column

```sql
-- db/migrations.py  (add to _run_migrations after existing ALTERs)
ALTER TABLE comms_messages ADD COLUMN superseded_by TEXT REFERENCES comms_messages(id);
```

One-liner. SQLite allows `ADD COLUMN` with a default of NULL on existing tables
with no rebuild required.

#### 1b. Update `get_pending_decisions()`

```python
# db/queries/comms.py — get_pending_decisions()
# BEFORE
WHERE board IN (...) AND scope IN (...) AND type='decision'
  AND status='pending' AND deleted_at IS NULL

# AFTER  (add one clause)
WHERE board IN (...) AND scope IN (...) AND type='decision'
  AND status='pending' AND deleted_at IS NULL
  AND superseded_by IS NULL                    ← new
```

#### 1c. New route — `POST /comms/supersede`

```python
# http_server/blueprints/comms.py
@comms_bp.route("/comms/supersede", methods=["POST"])
@require_secret
def comms_supersede():
    """
    Mark an existing decision as superseded by a newer one.
    Body: { old_id: str, new_id: str, project_root: str, feature: str }
    Sets comms_messages.superseded_by = new_id WHERE id = old_id.
    Returns 409 if old_id is already superseded.
    Returns 404 if old_id is not found.
    """
```

Callers (Studio "Replace decision" button, or a future `/comms promote` flow)
POST to this endpoint when they know a decision has been reversed.

#### 1d. Surface in Studio

In `CommandCenter`, when a user posts a new `decision`-type message, offer an
optional "This replaces…" picker that lists existing active decisions at the same
scope. If the user selects one, POST to `/comms/supersede` after posting the new
message. No forced flow — the picker is optional.

#### What this does NOT do

This is not automatic supersession. The system cannot infer that "Use SQLite"
supersedes "Use PostgreSQL" — that requires human judgment. The mechanism gives
humans the tool to mark supersession explicitly; it does not try to detect it.

#### Files changed

| File | Change |
|---|---|
| `src/pathly_orchestrator/db/migrations.py` | Add `ALTER TABLE comms_messages ADD COLUMN superseded_by TEXT` |
| `src/pathly_orchestrator/db/queries/comms.py` | Filter `AND superseded_by IS NULL` in `get_pending_decisions()`; add `supersede_message()` helper |
| `src/pathly_orchestrator/http_server/blueprints/comms.py` | Add `POST /comms/supersede` route |
| `studio/src/renderer/src/store/commsApi.ts` | Add `supersede(oldId, newId)` API call |
| `studio/src/renderer/src/components/HQ/CommandCenter/` | "Replaces" picker in the post-decision UI |
| `tests/test_comms_supersede.py` | New test file |

---

## PR 2 — Write-time curation: stop embedding noise

### The problem

Every message posted to the board is embedded, regardless of type. A `status`
update like "Build stage started" and a `nudge` like "Remember to check the
logs" both compete for the k=3/2/1 retrieval slots alongside `decision` and
`discovery` messages that carry genuinely durable constraints.

The result: high-value messages get pushed out of the retrieval window by
conversational noise. A missed retrieval means an agent proceeds without a
constraint it should have honored.

```
Board for a busy feature (100+ messages):
  ┌─────────────────────────────────────────────────┐
  │  "Build stage started"      (status, low value) │
  │  "Remember to check logs"   (nudge, low value)  │
  │  "Use SQLite — team agreed" (decision, HIGH)    │  ← may not fit in k=3
  │  "Build complete"           (status, low value) │
  │  "Auth bug found in PR #42" (discovery, HIGH)   │  ← may not fit in k=3
  │  "Stage started"            (status, low value) │
  └─────────────────────────────────────────────────┘
  k=3 retrieval: might return 3 status messages and miss both the decision
  and the discovery entirely.
```

### The fix

At write time, only embed message types that carry durable, semantically
retrievable information. Skip transient types.

#### Embed — types worth retrieving semantically

| Type | Reason |
|---|---|
| `decision` | Hard constraint, must be findable by topic |
| `discovery` | Factual finding about the codebase, durable |
| `constraint` | Same as decision — explicit rule |
| `warning` | Active risk that future agents need to know |
| `escalation` | Human input needed — must not be missed |
| `artifact` | Named output that future agents may reference |

#### Skip embedding — transient types

| Type | Reason to skip |
|---|---|
| `status` | "Stage started/completed" — no semantic value after the fact |
| `nudge` | Conversational suggestion, not a binding constraint |
| `question` | Answered inline; the `answer` carries the resolution |
| `answer` | Typically tied to a specific question, not generally retrievable |
| `task` | Task-list item; completion state matters more than topic similarity |

#### Implementation

```python
# src/pathly_orchestrator/http_server/blueprints/comms.py

_EMBED_TYPES: frozenset[str] = frozenset({
    "decision", "discovery", "constraint", "warning", "escalation", "artifact"
})

# In comms_post() — replace the unconditional _embed_async call:
# BEFORE
_embed_async(message_id, text)

# AFTER
if msg_type in _EMBED_TYPES:
    _embed_async(message_id, text)
```

One conditional. Zero schema changes. No migration needed.

#### Impact on recency fallback

When sqlite-vec or sentence-transformers is unavailable, `search_by_embedding`
falls back to `ORDER BY ts DESC`. The recency fallback already returns all
message types (no embedding check), so skipping embeddings for low-value types
does not affect recency-mode retrieval.

#### Files changed

| File | Change |
|---|---|
| `src/pathly_orchestrator/http_server/blueprints/comms.py` | Add `_EMBED_TYPES` frozenset; wrap `_embed_async` call in `if msg_type in _EMBED_TYPES` |
| `tests/test_comms_embeddings.py` | New test: assert `status` / `nudge` messages are NOT embedded; assert `decision` / `discovery` ARE embedded |

---

## PR 3 — Governance vs. semantic channel: labeled injection

### The problem

The current `## Communication Board` block mixes hard governance constraints
(always-apply decisions, open escalations) with soft semantic context
(cosine-matched recent messages) in one unlabeled block. An agent reading it
cannot distinguish "this is a rule" from "this might be relevant."

```
CURRENT prompt injection:
┌──────────────────────────────────────────────────────┐
│ ## Communication Board                               │
│ > Decisions override your defaults and team norms.   │
│                                                      │
│ ### 📌 Decisions (always apply)                      │
│   • Use SQLite for all persistence [Jun 10]          │
│   • No external API calls without approval [Jun 8]   │
│                                                      │
│ ### 💬 Recent context                                │
│   • Auth bug found: session tokens expire too fast   │
│   • Builder noted: schema migration needed for comms │
│   • PR #42 is blocked on the test runner             │
└──────────────────────────────────────────────────────┘
```

This is already reasonable, but two improvements sharpen it significantly:

1. **Explicit label on the semantic channel** — "The following MAY be relevant.
   Verify before acting on it." Currently there is no such caveat, so an agent
   may treat a cosine-matched nudge as authoritatively as a pinned decision.

2. **Open escalations in the governance channel** — escalations require human
   input and should be injected unconditionally alongside decisions, not left
   to compete for k=1 in the global vector search.

### The fix

In `comms_context.py: _build_board_block()`, separate the output into two
clearly labeled sections:

```python
# PROPOSED output structure

"""
## Communication Board

### 🔒 Governance (always applies — do not override)
Active decisions, constraints, and open escalations for this feature.

**Decisions:**
  • Use SQLite for all persistence  [Jun 10]
  • No external API calls without approval  [Jun 8]

**Open escalations (human input required):**
  • Auth design needs sign-off from @team before proceeding  [Jun 11]

---

### 💡 Context (possibly relevant — verify before acting)
Semantic matches for this task. These inform but do not override governance above.

  • Auth bug: session tokens expire too fast — fixed in commit abc123  [Jun 11]
  • Schema migration needed for comms board  [Jun 10]
"""
```

#### Implementation

```python
# runner/comms_context.py — _build_board_block() (rough sketch)

def _build_board_block(decisions, escalations, context_items) -> str:
    lines = ["## Communication Board\n"]

    # --- Governance channel (deterministic, always injected) ---
    gov_lines = []
    if decisions:
        gov_lines.append("**Decisions:**")
        gov_lines.extend(f"  • {d['text']}  [{_fmt_ts(d['ts'])}]" for d in decisions)
    if escalations:
        gov_lines.append("**Open escalations (human input required):**")
        gov_lines.extend(f"  • {e['text']}  [{_fmt_ts(e['ts'])}]" for e in escalations)
    if gov_lines:
        lines.append("### 🔒 Governance (always applies — do not override)")
        lines.extend(gov_lines)
        lines.append("---")

    # --- Semantic channel (labeled as advisory) ---
    if context_items:
        lines.append("### 💡 Context (possibly relevant — verify before acting)")
        lines.extend(f"  • {c['text']}  [{_fmt_ts(c['ts'])}]" for c in context_items)

    return "\n".join(lines) if len(lines) > 1 else ""
```

Escalations are fetched the same way decisions are — via a plain SQL query with
no embedding, injected deterministically:

```python
# db/queries/comms.py — add get_active_escalations()
def get_active_escalations(conn, boards, scopes):
    """Return all unresolved escalation messages for the given scopes."""
    # WHERE type='escalation' AND status='pending' AND deleted_at IS NULL
    #   AND superseded_by IS NULL   (once PR 1 lands)
```

#### Files changed

| File | Change |
|---|---|
| `src/pathly_orchestrator/db/queries/comms.py` | Add `get_active_escalations()` |
| `src/pathly_orchestrator/runner/comms_context.py` | Fetch escalations; pass `decisions`, `escalations`, `context_items` as separate arguments to a new `_build_board_block()`; add semantic-channel caveat label |
| `tests/test_comms_context.py` | Assert governance and semantic sections appear separately; assert escalations are in governance block |

---

## PR 4 — Promotion: wire it up or remove the dead code

### The current state

`get_promotable_messages()` exists in `db/queries/comms.py` and the schema has
`promoted_to`, `promoted_from`, and `original_scope` columns — but the function
is **never called anywhere in the repo**. There is no route, no Studio button,
no FSM logic that invokes it. The schema promises cross-feature organizational
memory; the code delivers nothing.

### Option A — Wire it up (recommended for long-term)

Add a `POST /comms/promote` route and a "Promote to project" / "Promote to
global" button in Studio's CommandCenter for `decision` and `discovery` messages.

When promoted:
- Insert a copy of the message at the new scope with `original_scope` and
  `promoted_from` set.
- Set `promoted_to` on the original to prevent double-promotion.
- The copy is immediately picked up by `retrieve_board_context()` for that
  scope's retrieval (feature-scoped agents see the feature copy; project-scoped
  agents see the project copy).

This is the full "institutional memory accrual" story — a lesson learned in
feature A's review can be promoted to project scope and resurface in feature B's
build.

### Option B — Remove now, build properly later (recommended for this sprint)

The dead code is a promise the product cannot yet keep. Remove:

```
db/migrations.py        — DROP promoted_to / promoted_from / original_scope columns
                          (or leave columns, add a comment "reserved for future promotion")
db/queries/comms.py     — delete get_promotable_messages()
```

Removing it:
- Stops the schema from advertising a feature that doesn't run.
- Removes a source of confusion for developers reading the code.
- Makes the future promotion PR a clean addition rather than a partial stub.

**Recommendation:** ship Option B now as part of PR 1 (it is one function
deletion and three column comments). Schedule Option A as a follow-on feature
once PRs 1–3 are stable.

---

## Suggested shipping order

```
PR 1: superseded_by               ← correctness fix, highest urgency
      (+ dead-code cleanup from PR 4 Option B, since migration is already open)

PR 2: write-time curation filter  ← quality fix, one conditional, zero schema changes

PR 3: labeled governance/semantic ← UX improvement, no schema changes
      channels

PR 4A: promotion (wire up)        ← new capability, ship after PRs 1-3 are stable
```

PRs 1 and 2 are independent — they can be reviewed in parallel. PR 3 builds
naturally on PR 1 (it can reference `get_active_escalations()` which is added in
PR 1's companion changes).

---

## What this does NOT address

These four PRs make retrieval *correct* and *less noisy*. They do not address:

- **ANN index** — the cosine scan is still brute-force full-table. At hundreds
  of messages this is fine. When the global tier grows large (thousands of
  messages across many projects), consider switching to sqlite-vec's KNN `MATCH`
  syntax or a dedicated vector store. Track message count and revisit when the
  global tier exceeds ~5,000 rows.
- **Recency + relevance blend** — the semantic search is pure cosine with no
  recency signal. A decision from 6 months ago scores the same as one from
  yesterday. A simple `score = cosine_score * recency_decay` would help but is
  not urgent.
- **Cross-project retrieval** — the global tier uses `scope='global'` as the
  board key. Messages promoted globally are retrievable from any project, but
  there is no mechanism for a specific project to opt into another project's
  board. Out of scope for now.
