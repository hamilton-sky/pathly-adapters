# Flow Diagram — unified-cli-composition (Gate 2)

---

## Current state (post-Gate 1, pre-Gate 2)

```
Renderer                               Python backend
────────                               ──────────────
skillCompose.ts                        http_server/blueprints/skills/editor_render.py
  POST /skills/compose ─────────────▶   compose_skill()       [compose.py]
    skill: "editor/analyze"               ├─ load_effective_manifest()
    skill: "editor/split"                 ├─ adapter_caps_for()  [inline dict]
    skill: "artifact/summarize"           └─ fragment bodies
                                              ├─ client-file-output.md   ✅
                                              └─ artifact-transform.md   ✅

                                       [STANDALONE TRANSFORMS — composed path]

goal_decomposer.py
  _decompose_planner()  ──────────────  inline Python prompt string  ❌ raw
  _decompose_plan()     ──────────────  inline Python prompt string  ❌ raw
  _decompose_consultation()             FSM path — leave alone
```

```
Error surface (post-Gate 1)
────────────────────────────
Analyze: ERROR: prefix → ActionPill error state   ✅
Split:   ERROR: prefix → ActionPill error state   ✅
Summary: ERROR: prefix → toast only               ❌ (no pill error state)
```

---

## Target state (Gate 2 complete)

```
Renderer                               Python backend
────────                               ──────────────
skillCompose.ts                        http_server/blueprints/skills/editor_render.py
  POST /skills/compose ─────────────▶   compose_skill()       [compose.py]
    skill: "editor/analyze"               ├─ load_effective_manifest()
    skill: "editor/split"                 ├─ build_adapter_caps(ctx)  ← NEW helper
    skill: "artifact/summarize"           └─ fragment bodies
    skill: "planning/plan"  ← NEW          ├─ client-file-output.md   ✅
                                           ├─ artifact-transform.md   ✅
                                           ├─ board-start-context.md  ← NEW (requires goal_id)
                                           └─ task-dag-post.md        ← NEW (requires goal_id)

goal_decomposer.py
  _decompose_planner()  ──────────────  compose_skill("planning/plan", ...)  ✅
  _decompose_plan()     ──────────────  compose_skill("planning/plan", ...)  ✅
  _decompose_consultation()             FSM path — unchanged

supervisor (goal_run.py)
  PHASE_START event ──────────────────  {goal_id, executor, kind}  ← NEW metadata fields
  result capture    ──────────────────  AGENT_DONE.summary in EVENTS.jsonl  ✅ (no stdout parse)
```

```
Error surface (Gate 2)
────────────────────────────
Analyze: ERROR: prefix → ActionPill error state   ✅
Split:   ERROR: prefix → ActionPill error state   ✅
Summary: ERROR: prefix → ActionPill error state   ✅ (Gate 2 fix)
```

---

## Fragment gating logic (Gate 2 additions)

```
compose_skill("planning/plan", adapter_caps, manifest)

adapter_caps["goal_id"] present?
├─ YES → include board-start-context + task-dag-post
└─ NO  → skip both (standalone-transform profile)

adapter_caps["can_spawn"] present and True?
├─ YES → include spawn-rules
└─ NO  → skip spawn-rules
```

---

## Component interaction map (Gate 2 changes only)

```
Files added:
  src/pathly_data/core/skills/fragments/board-start-context.md
  src/pathly_data/core/skills/fragments/task-dag-post.md

Files modified:
  src/pathly_data/core/skills/composition.yaml
    + planning/plan entry (board-start-context + task-dag-post, both gated on goal_id)

  src/pathly_orchestrator/skills/compose.py
    + goal_id added to _KNOWN_CAPABILITIES
    + adapter_caps_for() updated to propagate goal_id
    + build_adapter_caps(ctx) helper extracted (used by both call paths)

  src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py
    + inline adapter_caps dict → build_adapter_caps(ctx) call

  src/pathly_orchestrator/supervisor/goal_decomposer.py
    + _decompose_planner(): inline prompt → compose_skill("planning/plan", ...)
    + _decompose_plan(): inline prompt → compose_skill("planning/plan", ...)
    + PHASE_START event enriched with goal_id, executor, kind
    + result capture: stdout parse removed → AGENT_DONE.summary read
    (no changes to _decompose_consultation)

  studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts  (or skillCompose.ts)
    + Summary error path: check ERROR: prefix → set pill state='error'
```

---

## Data flow: Decompose result capture (before vs after)

```
BEFORE (hard-coded path):
  goal_decomposer.py
    → build inline Python prompt string
    → spawn CLI headlessly
    → read stdout tail / result.text
    → parse task payload inline in Python
    → POST /comms/tasks (Python-built payload)

AFTER (composition path):
  goal_decomposer.py
    → compose_skill("planning/plan", build_adapter_caps(ctx), manifest)
    → spawn CLI headlessly (composed prompt as argv, _dash_safe_prompt applied)
    → [agent] reads board-start-context → GET /comms/retrieve
    → [agent] reasons about goal, produces task tree
    → [agent] POST /comms/post with type="task" for each task (task-dag-post fragment)
    → [agent] writes AGENT_DONE to EVENTS.jsonl with summary (task IDs + narrative)
    → CLI exits
    → supervisor reads AGENT_DONE.summary (authoritative result)
    → no Python-side task payload construction
```

---

## Layer dependency check (no violations introduced)

```
pathly_data/   → (nothing internal — data layer, no imports)
compose.py     → pathly_data/ (reads fragment files)  ✅
goal_decomposer.py → compose.py  ✅ (orchestrator → skills, same layer)
editor_render.py   → compose.py  ✅ (HTTP → skills, upward allowed via lazy import)
skillCompose.ts    → POST /skills/compose  ✅ (renderer → HTTP, cross-process boundary)
```
