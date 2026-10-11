# SPEC — Chief Agent (one conversation that drives Pathly) + memory tiers

_Draft plan. Builds on [`role-read-policy/SPEC.md`](../role-read-policy/SPEC.md) (run token,
server-stamped provenance, one read predicate). File refs checked against `de043d4`._

> **Thesis.** Pathly already has the blackboard (comms board), role contracts with tools,
> server-side rules (fragments), depth (goal → task-DAG, FSM stages) and breadth (fan-out,
> lanes). What it lacks is **one long-lived agent the human talks to** that turns a
> conversation into goals, watches the board, and relays what needs a human. Today that seat
> is a regex (`chat_agent.py`: "Heuristic chat agent … WebLLM integration is Conv 9") and a
> stateless router (`core/agents/director.md`). This spec fills the seat, and adds the memory
> tiers the chief needs to stay useful across days without an ever-growing transcript.

---

## A. What exists today (verified)

| Piece | Where |
|---|---|
| Chat endpoint | `POST /chat` → `http_server/blueprints/ops/chat.py` → `chat_agent.handle_chat` (regex intent, no LLM) |
| Start / stop goal work | `POST /comms/goals/run`, `/comms/goals/stop`, `/comms/goals/decompose`; `GET /comms/goals` (`blueprints/comms/goals.py`, `goals_read.py`) |
| Run control | `POST /runs`, `/runs/<id>/stop`, `/runs/<id>/<action>` (`blueprints/control/runs_control.py`); `GET /runner/status` |
| Agent questions to a human | `supervisor/interactions.py` waits; `POST /runner/agent-answer` supplies the answer (`blueprints/runner/api_control.py:157`) |
| Board read / write | `/comms/post`, `/comms/search`, `GET /comms` (+ the role wall from role-read-policy) |
| Session reuse | `claude -p … --resume <session>`; reuse decision in `supervisor/orchestrator_session.py` |
| Memory raw material | `fsm_events` (`AGENT_DONE.summary`), `run_history` (`db/migrations.py:21`, `:222`) — stored, **not embedded** |
| Semantic retrieval | `runner/embeddings.py` (MiniLM) + `db/queries/comms_embeddings.py` (sqlite-vec, FTS5, hybrid RRF) — **board messages only** |
| Consolidation / promotion | `POST /comms/consolidate` (`blueprints/comms/settings.py:385`), `POST /comms/promote` — **manual only** |

## B. Goals / non-goals

**Goals**
- G1. The human can drive Pathly **only through the chief**: describe work, ask "how is it
  going", answer agent questions, approve decisions, stop runs. Studio's board stays the
  visible source of truth; the chat is a second way in, not a second state.
- G2. The chief **never executes stages**. It only calls Pathly's HTTP API (post goals,
  decompose, run, stop, answer, post decisions). The FSM / supervisor / executors stay the
  single engine.
- G3. Runs on the user's **own Claude subscription** through the unmodified `claude -p` CLI,
  like every other Pathly spawn. No OAuth token is extracted or reused by custom clients.
- G4. Explicit memory tiers by lifetime — working, episodic, semantic — all behind the
  role-read-policy predicate.
- G5. Bounded cost: a cap on chief turns per window and a lean, retrieval-built context.

**Non-goals**
- Replacing the FSM with LangGraph (or any second engine). LangGraph may host the chief's own
  loop later (§F, Q2); it never drives stages.
- JEPA-family models. A small local decision model (e.g. Laya, fine-tuned) as a cheap router
  is a later option (§F, Q3), not part of this spec.
- Multi-user. One human, one chief per project.

---

## C. Design

### C1. The chief's turn loop

```
human message ──► POST /chief/message ─┐
board event (run done, interaction     │   chief inbox (DB, per project)
asked, escalation, goal blocked) ──────┤
                                       ▼
                        one chief turn = one spawn:
                        claude -p "<composed prompt>" --resume <chief_session> --output-format json
                                       │
                        tools = curl to Pathly HTTP API (chief-* fragments, run token)
                                       ▼
                        reply posted to the chief thread (DB) ──► Studio chat panel (SSE)
```

- A turn is triggered by a human message, or by an inbox event the chief subscribes to
  (debounced: one turn per batch of events, never one per event).
- Each turn is a normal headless spawn through the existing spawn host and gate, so billing,
  concurrency caps and provider-refusal retries apply unchanged. Its `run_category` is a new
  value `chief`.
- `--resume` keeps short-term continuity. When the CLI session gets long or is lost, the chief
  starts a fresh session and rebuilds context from the board + memory (C3), so no state lives
  only in the transcript.

### C2. Role contract and fragments

- `core/agents/support/chief.md`: role contract. Absorbs `director.md`'s routing (rigor choice,
  which executor) so the human gets one front door.
- `core/skills/fragments/chief-*.md` (un-editable layer, like every fragment):
  - `chief-tools` — the allowed API calls, each as a `curl` with the run token header
    (role-read-policy C4).
  - `chief-rules` — never edit project files; never run stages; never answer an agent's
    question or approve a decision **on the human's behalf** unless the human said so in this
    thread (the reply quotes it); confirm before stopping a run or starting a `strict` goal.
  - `chief-status` — how to summarize: read goal rollups and run summaries, cite board ids.
- Built-in read wall: the `chief` row in role-read-policy C2.

### C3. Memory tiers (by lifetime)

| Tier | Holds | Store | Written | Read |
|---|---|---|---|---|
| **Working** | the current run's / turn's scratch | the run's board scope + CLI session | during the run | that run only |
| **Episodic** | "what happened last time": one embedded summary per finished run (from `AGENT_DONE.summary`, RETRO, outcome, goal/feature) | new `memory_episodes` table + vec index | automatically at run end | `retrieve_board_context` gains an episodic section |
| **Semantic** | distilled lessons / constraints | promoted `decision`/`constraint` rows on project/global boards (existing) | consolidate + promote, **scheduled** at RETRO/DONE | existing tier retrieval |

Rules shared with role-read-policy C8:
- Every episode carries `author_role`, `author_run_id`, `author_source` from the run token.
- Every memory read ANDs `policy_predicate` before `k`. A reviewer does not get the builder's
  run summary through the episodic tier.
- Promotion to `global` requires `author_source ∈ {token, system}` and evaluator or human
  approval. Promoted rows keep provenance and can be superseded (reuse `dedupe_board`'s
  supersede pattern), so a wrong lesson can be retired.

Embedder: keep the `runner/embeddings.py` seam; make the model configurable and evaluate a
code-aware one. Out of scope to choose here.

### C4. Human-in-the-loop through the chief

- Agent questions (`interactions.py`) and pending decisions land in the chief inbox. The chief
  asks the human in chat, then calls `/runner/agent-answer` or posts the decision with the
  human's words quoted. The board still shows the question and answer, so the board view and
  the chat never disagree.
- The headless rule stays: no stage targets `human`. The chief is the relay, not a stage.

### C5. Cost and limits

- `chief.max_turns_per_hour` setting (default small), plus the existing cost cap.
- Context is rebuilt from retrieval each turn with a token budget (`context_budget.py`), not
  by growing the transcript.
- A turn the provider refuses (rate limit / quota) is shown in chat as "paused until …", never
  silently dropped.

### C6. Chief decisions reach the workers through the board

The chief never messages a builder, reviewer or tester directly. It posts to the board, and
the workers read it through the paths they already use. How that works today (verified):

- **Pending decisions are injected into every prompt.** `retrieve_board_context` puts
  `get_pending_decisions` (`type='decision' AND status='pending'`, not superseded,
  `db/queries/comms_messages.py:153`) into the governance block ("injected unconditionally",
  `runner/comms_context.py:120-135`, `:271`). Role-read-policy C1 never withholds them.
- **Other posts reach a worker only by relevance.** A `constraint`, or a decision that is no
  longer `pending`, is retrieved semantically and has to clear the tier cutoff
  (`comms_context.py:151-227`).
- **Acknowledging ends the guarantee.** `POST /comms/acknowledge` sets `status='active'` for
  the whole row (`comms_messages.py:212`), so after the first acknowledgement a decision drops
  out of the unconditional block for every role. No fragment calls it today; the UI can.
- **Timing.** Context is composed at spawn, so a worker sees a new decision on its **next**
  spawn. A worker already running sees it only if it pulls (`board-search`).
- **Write gate.** Any role may write a feature board; `chief` is not in `_PROJECT_WRITERS` /
  `_GLOBAL_WRITERS` (`http_server/blueprints/comms/_helpers.py:63-78`).

Changes this spec makes:
1. Add `chief` to `_PROJECT_WRITERS` (and `_DEFAULT_WRITE_PERMISSIONS`, kept in sync). Not to
   `_GLOBAL_WRITERS`: global writes stay with director/evaluator/human, and the chief asks the
   human.
2. **Standing directives.** A chief decision is posted as `type='decision'` with a new
   `binding=1` flag and an optional `to_agent` (role or `*`). The governance query injects
   `binding=1` rows while not superseded, **whatever their `status`**, filtered by `to_agent`
   against the reader's role. Acknowledgement records who saw it; it no longer hides it.
   A directive is retired only by superseding it (the existing `superseded_by` column), so the
   board shows its history.
3. **Mid-run delivery.** When a binding decision targets a role that has a run in flight, the
   supervisor also sends it as a nudge to that run (or, if the run cannot take a nudge, marks
   the current stage for re-check). Without this, a builder halfway through a stage finishes on
   the old decision.
4. **Provenance.** `binding=1` is accepted only from a run token whose role is `chief` or from
   the UI token (role-read-policy C4). A builder cannot post a "binding" decision to steer the
   reviewer.

---

## D. Phases (each → one board task)

Prerequisite: role-read-policy P1–P3 (run token, `author_role`, predicate).

| # | Phase | Priority | Risk | Done when |
|---|---|---|---|---|
| P1 | `chief.md` contract + `chief-*` fragments + `chief` read-wall row | P0 | Low | composed chief prompt has the tool list and rules; fragment tests pass |
| P2 | Chief thread + inbox tables, `POST /chief/message`, `GET /chief/thread` (new `blueprints/chief/` domain); spawn one turn via the spawn host with `--resume` | P0 | Med | a human message produces one spawned turn and a reply in the thread; billing row has `category=chief` |
| P3 | Inbox subscriptions (run done, interaction asked, escalation, goal blocked) with debounce; relay answers via `/runner/agent-answer` | P0 | Med | an agent question reaches chat, the human's answer unblocks the run, the board shows both |
| P3b | Standing directives (C6): `chief` write permission, `binding`/`to_agent` on decisions, governance query injects binding rows regardless of `status`, binding accepted only from chief/UI token, mid-run nudge | P0 | Med | a chief decision "use Postgres, not SQLite" appears in the next builder, reviewer and tester prompts, still after an acknowledgement; a builder-token post with `binding=1` is refused |
| P4 | Studio chat panel talks to `/chief/*`; `POST /chat` delegates to the chief (keep `chat_agent.py` as a no-LLM fallback when the chief is off) | P0 | Low | Studio chat drives a goal end-to-end without touching the board UI |
| P5 | Episodic tier: `memory_episodes` + embedding at run end + retrieval section, behind `policy_predicate` | P1 | Med | a new run on the same feature sees last run's summary; a reviewer does not see the builder's |
| P6 | Scheduled consolidate + promote at RETRO/DONE with the provenance gate | P1 | Med | lessons appear on project board after DONE; unverified rows are never promoted to global |
| P7 | Turn cap, refusal display, session rebuild from memory | P1 | Low | cap enforced; a lost session resumes with correct state |

## E. Tests

- Chief never calls a stage-executing route outside the allow-list (fragment + server check).
- A chief answer to an agent question without a quoted human message is rejected.
- Episode read for `role=reviewer` withholds builder-authored episodes; `role=chief` sees them.
- Promotion of a `legacy`/`none` row to global is refused.
- Debounce: ten events in one second → one chief turn.
- Directive targeting: `to_agent='reviewer'` reaches the reviewer prompt and not the builder's;
  `to_agent='*'` reaches all; a superseded directive reaches none.
- Session loss: fresh session reconstructs goal status from board + memory only.

Tests go in the matching `tests/` domain folder with unique basenames; rerun
`scripts/gen_test_index.py`.

## F. Open questions

1. **Subscription terms.** One human driving their own `claude -p` is ordinary individual use;
   an always-on chief plus parallel workers is heavy automated use and may hit plan limits.
   Keep the turn cap conservative and re-check Anthropic's current terms before shipping P3's
   event-triggered turns.
2. **LangGraph for the chief loop.** Its checkpointer and interrupts fit C1, but each node would
   be a `claude -p` black box, so most of its value is lost. Start with a plain Python loop;
   revisit only if the loop grows branches.
3. **Cheap router.** A fine-tuned local decision model (Laya-style) or Haiku could decide
   "does this event need a chief turn at all", cutting turns. Measure turn volume in P3 first.
4. **Does the chief replace `director.md` or call it?** Default: absorb. Keep `director` for the
   interactive `/pathly` path until the chief is proven.
