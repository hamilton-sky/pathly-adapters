---
name: Flow Diagram
---
# Comms Board (Phase 1 — Backend Core) — Flow Diagram

## Happy Path: post a message → injected into the next agent

```
human / agent
      │  POST /comms/post {feature,from,type,text}
      ▼
blueprints/comms.py
      │  db.post_message()  ───────────►  comms_messages (status=pending)
      │  embed_async(id,text)
      │  _broadcast_comms(scope)  ─────►  /events/comms subscribers (COMMS_UPDATE)
      ▼
runner/embeddings.py  (daemon thread)
      │  embed(text) → 384-dim vector
      │  db.store_embedding()  ────────►  comms_embeddings (vec0)
      ▼
        [message now semantically searchable ~200ms after post]


next stage begins
      │  POST /next_action {flow,topic,project_root}
      ▼
fsm_ops.build_prompt()
      │  ## Current task         (existing)
      │  ## Pipeline History     (existing)
      │  get_board_scope(root,feature)
      │       │
      │       ▼
      │  runner/comms_context.retrieve_board_context()
      │       │  embed(task_description)
      │       ├─ feature board  k=3 ─┐
      │       ├─ project board  k=2 ─┤ search_by_embedding()
      │       ├─ global  board  k=1 ─┘
      │       └─ + pending decisions / escalations (always)
      │       ▼
      │  ## Communication Board   (NEW — appended when non-empty)
      ▼
agent_hint.instructions  ──►  the next agent starts already knowing the board
```

## Fallback / Error Flow

```
sqlite-vec extension cannot load
      │
      └─ get_db(): _VEC_AVAILABLE = False  (warn once, server still starts)
              │
              ├─ migrations: skip the vec0 virtual table
              │
              └─ search_by_embedding(): ORDER BY ts DESC LIMIT k
                        │
                        └─ recency-ranked board context (less smart, never down)
```

```
board_scope = {feature:false, project:false, global:false}
      │
      └─ retrieve_board_context() returns ""
              │
              └─ no block appended → prompt identical to today (no error)
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `blueprints/comms.py` | HTTP routes — post / get / search / acknowledge / answer / trash / restore |
| `runner/embeddings.py` | all-MiniLM-L6-v2 embedding worker (lazy-loaded, warmed at startup) |
| `comms_messages` | message rows (text + lifecycle + artifact/task fields) |
| `comms_embeddings` | sqlite-vec vec0 virtual table, `FLOAT[384]` vectors |
| `retrieve_board_context()` | embeds the task, queries enabled boards, builds the markdown block |
| `_VEC_AVAILABLE` | module flag — true = vector search, false = recency fallback |
| `## Communication Board` | the block injected into agent_hint.instructions |
