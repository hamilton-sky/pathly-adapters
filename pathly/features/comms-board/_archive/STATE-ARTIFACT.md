# Comms Board — State of Pathly + Board Connection

> Explorer artifact · 2026-06-16

---

## 1. Plan state (FSM)

| Field | Value |
|---|---|
| FSM state | `BUILDING` (conv 6 complete, feature backend done) |
| Conversations total / done | 6 / 5 (STATE.json) |
| Backend COMPLETE signal | ✅ emitted 2026-06-14 (EVENTS.jsonl) |
| RETRO | ✅ written |
| Next plan | `comms-board-studio` (frontend, blocked on design consultation) |

---

## 2. Backend — what is shipped

All six conversations are done. Every phase below is green.

### Core API (`src/pathly_orchestrator/http_server/blueprints/comms.py`)

| Route | Status | Notes |
|---|---|---|
| `POST /comms/post` | ✅ | Role-based write permissions; embeds decision/discovery/constraint/warning/escalation/artifact types |
| `GET /comms` | ✅ | Scoped by board tier (feature/project/global) |
| `POST /comms/search` | ✅ | Hybrid BM25+cosine (FTS5 + sqlite-vec), `mode=hybrid\|semantic\|keyword` |
| `POST /comms/acknowledge` | ✅ | Marks message handled |
| `POST /comms/answer` | ✅ | Answers a `type=question` message |
| `POST /comms/supersede` | ✅ | Marks old decision superseded_by a newer one |
| `POST /comms/attach` | ✅ | Attaches file/URL artifact to a message |
| `GET /comms/tasks` | ✅ | DAG tasks; `?ready=true` returns only unblocked |
| `POST /comms/tasks/complete` | ✅ | Marks task done, cascades newly-unblocked tasks |
| `POST /comms/tasks/claim` | ✅ | Atomic claim (pending → in_progress) |
| `POST /comms/tasks/fail` | ✅ | Marks failed; cascade-blocks dependents |
| `GET/POST /comms/scope` | ✅ | Per-feature board scope toggle (feature/project/global tiers) |
| `GET /comms/permissions` | ✅ | Resolved write-permission table per project root |
| `POST /comms/delete` | ✅ | Soft-delete (force=true for agent posts) |
| `GET /comms/trash` + `POST /comms/restore` | ✅ | Trash / restore |
| `POST /comms/run` | ✅ | Single-agent board run (US4): acquires lock, builds context, spawns PTY |
| `POST /comms/run/stop` | ✅ | TERMINAL_KILL + lock release + board status post |
| `POST /comms/agent-context` | ✅ | Board-info mode for non-FSM agents |
| `GET /events/comms` (SSE) | ✅ | Live COMMS_UPDATE stream to Studio |

### DB schema (`db/migrations.py`, `db/queries/comms.py`)

- `comms_messages` table: `id, board, scope, from_agent, to_agent, type, text, status, options, reply_to, stage, conv, deleted_at, superseded_by, artifact_path, artifact_url, artifact_type, depends_on (JSON), claimed_by`
- `comms_embeddings` (vec0 virtual table): hybrid search index; populated only for `_EMBED_TYPES` messages
- `comms_fts` (FTS5 virtual table): BM25 keyword search

### Agent injection (`runner/comms_context.py`, `fsm_ops.py`)

Every `/next_action` call injects a `## Communication Board` block into `agent_hint.instructions`:
- `### Governance` — pending decisions + open escalations
- `### Recent context` — up to 20 recent messages

Board tier selection is controlled by `board_scope` in `app_settings` (per project-root + feature-name key).

### Skills write-back (`src/pathly_data/core/skills/fragments/comms-post.md`)

The `comms-post.md` fragment is wired into: `review.md`, `test.md`, `design.md`, `explore.md`, `debug.md`, `retro.md` (both `team/*` and `development/*` families). Agents post `type=warning|decision|discovery|artifact` mid-run. Fragment was synced via `pathly-setup claude --apply --repair` (2026-06-15).

---

## 3. Board connection — four data/control flows

```
WRITE PATH  (agent → board)                          [SHIPPED]
  agent (comms-post.md fragment)
    │  curl POST /comms/post  {feature, from, type, text, board, stage}
    ▼
  blueprints/comms.py:comms_post
    ├─► db/queries/comms.py:post_message  (INSERT comms_messages)
    ├─► runner/embeddings.py:embed_async  (for _EMBED_TYPES)
    └─► sse.py:_broadcast_comms(scope, COMMS_UPDATE)  → Studio SSE

READ PATH  (board → agent prompt)                    [SHIPPED]
  runner/comms_context.py:retrieve_board_context
    └─► injected into agent_hint.instructions on every /next_action

HUMAN-ACTION PATH  (human → board → FSM)             [CODE COMPLETE, not smoke-tested]
  Studio CommsMsgCard resolve buttons (Block/Note/Ignore)
    │  commsStore.resolve(key, id, mode)
    ├─► POST /comms/acknowledge
    ├─► POST /comms/post  (type=decision, only for mode='note')
    └─► POST /runner/decision  {topic, decision}
          guard: only when runnerStore.topic === key AND status==='awaiting_decision'

BOARD RUN PATH  (human → single-agent run)           [SHIPPED]
  Studio runSingleAgent(key, opts)
    │  POST /comms/run  {board, scope, mode:'single-agent', adapter, model, ...}
    ▼
  supervisor/board_run.py:start_board_run
    ├─► board_lock.acquire(board, scope, run_id)  [409 if busy]
    ├─► _build_context → _format_board_info      [governance + recent msgs]
    ├─► _compose_skill_body(skill, adapter)
    ├─► assembles full prompt (skill + system_prompt + agent role + instructions + context)
    └─► threading.Thread → _default_spawn → supervisor/terminal.py:_run_stage_via_terminal
              └─► TERMINAL_SPAWN SSE → Studio opens PTY tab
                  PTY exits → POST /runner/terminal/result
                  on_done → _board_post("✅ {label} finished …", phase='done')
```

---

## 4. Studio frontend (what is wired)

### Store: `store/commsStore.ts`
- `loadBoard(scope, key, projectRoot)` — fetches messages from `GET /comms`
- `post(key, type, text, stage)` — optimistic post + `POST /comms/post`
- `resolve(key, id, mode)` — ack + FSM decision (Gap 2, code complete)
- `runSearch(key, query)` — `POST /comms/search` → `searchResults` overlay (Gap 4, code complete)
- `supersede(key, oldId, newId)` — `POST /comms/supersede` (Gap 4, code complete)
- `attach(key, msgId, path, atype)` — `POST /comms/attach` (Gap 4, code complete)
- `runSingleAgent(key, opts)` — `POST /comms/run` → board run; sets `activeTopic` so terminal opens
- `markBoardRunPhase(key, phase)` — reacts to SSE `board_run` phase (`running/done/stopped`)
- `stopBoard(key)` — `POST /comms/run/stop`

### Component: `components/CommandCenter/BoardSection/BoardSection.tsx`
Renders a scoped `CommsPanel` for a given tier (feature/project/global). The `CommandCenter` canvas can show all three tiers as parallel columns.

### Component: `components/HQ/CommsPanel/CommsPanel.tsx`
Full message list (search overlay, task list, warning resolve buttons, artifact attach, supersede menu). Drives `useCommsStore`.

---

## 5. What is NOT yet done

| Item | Status | Blocking? |
|---|---|---|
| Live Studio smoke test (warning resolve → FSM, search, supersede, attach) | ⚠️ Pending | P1 gate before declaring "live" |
| Studio frontend plan (`comms-board-studio`) | Not started | Blocked on design consultation |
| Rich artifact compose tray (ArtifactBubble, 5-thumbnail tray, `artifacts[]` column) | Not built | P1.5 follow-up |
| Async question loop Part B (answer → `/runner/agent-answer`) | Deferred | Low priority; fire-and-check is V1 |
| DAG scheduler P2/P3 (supervisor-owned frontier loop, worktree-per-task fan-in) | Future | Finish P1 interactive board first |

---

## 6. How to verify the backend is healthy

```bash
# All comms tests
python -m pytest tests/ -q -k comms

# Smoke: post + retrieve round-trip
pathly-fsm-call comms-post --feature comms-board --from explorer \
  --type discovery --text "board is healthy"

curl -s "http://127.0.0.1:8765/comms?feature=comms-board&board=feature&scope=comms-board" | python -m json.tool | head -30

# SSE stream (stays open)
curl -N "http://127.0.0.1:8765/events/comms?scope=comms-board"
```
