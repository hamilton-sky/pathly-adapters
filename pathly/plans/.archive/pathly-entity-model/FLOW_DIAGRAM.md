# Flow Diagrams — pathly-entity-model

_Last updated: 2026-06-29_

---

## 1. Phase delivery chain

```
┌─────────────────────────────────────────────────────────┐
│  Phase 0 — GUARD                                        │
│  _safe_topic (raises) + slug column + UNIQUE index      │
└─────────────────────┬───────────────────────────────────┘
                      │  gate: test_fsm_ops.py passes
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1 — BUG FIX                                      │
│  ensure_goal_slug · topic=slug at all 10+ sites         │
│  goals/ probe · terminal.py split · RESERVED extended   │
└──────────────┬──────────────────┬───────────────────────┘
               │                  │
               │ gate: real e2e   │ no shared code →
               │ consultation     │ parallel OK
               │ decompose passes │
               ▼                  ▼
┌─────────────────────┐  ┌────────────────────────────────┐
│  Phase 2 — ARTIFACT │  │  Phase 3 — SIDEBAR             │
│  ATOMIC commit      │  │  loadCards · CardSidebar       │
│  7 files in 1 commit│  │  behind flag · FeatureSidebar  │
│  + adapter sync     │  │  fallback                      │
└─────────────────────┘  └────────────────────────────────┘
```

---

## 2. The bug path (current — before Phase 1)

```
goal created
│   scope = "C:/Users/Yafit/pathly-adapters"  (absolute path)
│
│  goal_decomposer.py:246
│  _decompose_consultation()
│       topic = scope     ← raw absolute path passed as FSM topic
│
│  fsm_ops.py:68
│  _resolve_storage_path(topic="C:/Users/Yafit/pathly-adapters")
│       Path(root) / "pathly" / topic
│                              │
│                              └── pathlib: right operand is absolute
│                                  DISCARDS left operands entirely
│                                  result = "C:/Users/Yafit/pathly-adapters"
│                                  (the project root itself)
│
│  FSM writes PO_NOTES.md to:
│       C:/Users/Yafit/pathly-adapters/PO_NOTES.md
│
│  Gate check:
│       stat("C:/Users/Yafit/pathly-adapters/PO_NOTES.md")
│       file NEVER exists at this path (PO writes to a goals/ subdir)
│
└──► PO_DISCUSSING state → gate misses → re-spawn PO → ∞ loop
```

---

## 3. The fix path (after Phase 1)

```
goal created  (goal_id = "3f9a1c22...", goal_text = "fix the loop")
│
│  supervisor/slug.py
│  ensure_goal_slug(conn, goal_id)
│       SELECT slug FROM comms_messages WHERE id = goal_id
│       slug is NULL → generate: "fix-the-loop-3f9a1c22"
│       UPDATE comms_messages SET slug = "fix-the-loop-3f9a1c22"
│       return "fix-the-loop-3f9a1c22"
│
│  _safe_topic("fix-the-loop-3f9a1c22") ── no separator, not abs ──► OK
│
│  goal_decomposer.py:246
│  _decompose_consultation()
│       topic = slug = "fix-the-loop-3f9a1c22"    ← clean slug
│
│  fsm_ops.py:68
│  _resolve_storage_path(topic="fix-the-loop-3f9a1c22")
│       probe 1: Path(root)/"pathly"/"plans"/"fix-the-loop-3f9a1c22" → not found
│       probe 2: Path(root)/"pathly"/"goals"/"fix-the-loop-3f9a1c22" → mkdir + use
│       result = "<root>/pathly/goals/fix-the-loop-3f9a1c22/"
│
│  FSM writes PO_NOTES.md to:
│       <root>/pathly/goals/fix-the-loop-3f9a1c22/PO_NOTES.md   ✓
│
│  Gate check:
│       stat("<root>/pathly/goals/fix-the-loop-3f9a1c22/PO_NOTES.md")
│       file EXISTS
│
└──► FSM advances past PO_DISCUSSING  ✓  consultation completes
```

---

## 4. Artifact guarantee path (Phase 2)

```
Two paths both converge on ensure_attached:

PATH A — FSM-gated runs (complete_stage called)
─────────────────────────────────────────────
agent writes artifact to <storage_path>/<file>
│
│  agent appends ARTIFACTS.jsonl line {role, path, type, title, summary, ts}
│  agent does advisory board POST (skip if unreachable)
│
│  PTY exits  →  supervisor calls complete_stage
│
│  fsm.py:/complete_stage
│       stat(<storage_path>/<file>)  ← gate check
│       file present → advance FSM
│       call ensure_attached(slug, board, scope, artifact_path, role)
│
│  db/queries/comms_artifacts.py
│  ensure_attached()
│       SELECT id WHERE scope=? AND path=?
│       not found → INSERT comms_artifacts row
│                 → SSE artifact_attached fires
│       found     → skip (idempotent)
│       return True/False
│
└──► comms_artifacts row exists  ·  SSE fires  ·  board catalog updated

PATH B — non-FSM runs (complete_stage NOT called)
─────────────────────────────────────────────────
PTY exits  →  supervisor post-PTY handler fires
│
│  read <storage_path>/ARTIFACTS.jsonl line by line
│  for each line: call ensure_attached(slug, board, scope, line.path, line.role)
│
│  JSONL absent (bootstrapping window):
│       look up role in artifact-manifest.yaml → get {file, gate}
│       stat(<storage_path>/<file>)
│       present → call ensure_attached
│       absent  → skip silently
│
└──► same outcome: comms_artifacts row exists  ·  SSE fires
```

---

## 5. Sidebar data flow (Phase 3)

```
disk scan
─────────────────────────────────────────────────────────────
pathly/
  plans/<slug>/       → kind='feature'  (STATE.json present)
  goals/<slug>/       → kind='goal'     (RESERVED guards against phantom)
  lessons/            → kind='lesson'   (flat LESSONS.md, one card total)
  explorations/<slug>/→ kind='exploration'

commsStore.ts
─────────────────────────────────────────────────────────────
loadCards()
│  scan pathly/  →  filter by RESERVED  →  classify by parent dir name
│  RESERVED = {plans, .archive, goals, lessons, explorations,
│              debugs, pipeline-walkthrough}
│  goals/ and others in RESERVED → NOT surfaced as phantom features
│
│  build cards[] = [
│    {kind:'feature',     name:'unified-cli', ...},
│    {kind:'goal',        name:'fix-loop',    goalId: '...'},
│    {kind:'lesson',      name:'Lessons',     path:'pathly/lessons/LESSONS.md'},
│    {kind:'exploration', name:'spawn-probe', ...},
│  ]
│
│  set({ cards })               ← authoritative slice
│
│  get features() {             ← derived getter, NOT a separate set()
│    return this.cards.filter(c => c.kind === 'feature')
│  }

CardSidebar
─────────────────────────────────────────────────────────────
receives cards[]
│
│  group by kind  →  4 sections
│  empty section  →  hidden (not rendered)
│
│  Features section:   [unified-cli] [pathly-entity-model] ...
│  Goals section:      [fix-loop ▶ Decompose ▶ Run]
│  Lessons section:    [Lessons →  opens LESSONS.md in MarkdownEditor]
│  Explorations section: [spawn-probe] ...
│
│  collapsed rail (48px):
│    ● ● ●   (feature dots, up to 5, then +N)
│    ●       (goal dots)
│    ●       (lesson dot)
│
│  state: collapse/expand per kind  →  localStorage key per kind
│
└──► rendered sidebar  ·  TypeScript clean  ·  FeatureSidebar fallback when flag=false
```
