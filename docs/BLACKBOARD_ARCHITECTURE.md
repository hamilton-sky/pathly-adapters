# The Blackboard Architecture — the research, and how Pathly implements it

_Written 2026-07-22, from an assessment produced by an agent that spent a full session working
**inside** Pathly's own cadence (the `state-one-authority` dogfood: 3 goals / 10 board tasks,
grounded per-task via board context + code intel, statuses posted back to the board). The
evidence claims below are first-hand._

---

## 1. Where the idea comes from

The blackboard metaphor is usually credited to Allen Newell (1962): imagine a group of
specialists standing around a physical blackboard, solving a problem none of them can solve
alone. Each watches the board; when a specialist sees something they can contribute to, they
walk up and write their partial result; that new writing lets a *different* specialist see
their next move. Nobody talks to anyone directly. The solution assembles itself **on the
board**, incrementally and opportunistically.

The architecture was made real in a line of systems:

| System | Years | Domain | What it contributed |
|---|---|---|---|
| **Hearsay-II** (CMU — Erman, Hayes-Roth, Lesser, Reddy) | 1971–76 | Speech understanding | The canonical architecture: hypothesis blackboard with **abstraction levels**, condition/action knowledge sources, agenda-based opportunistic scheduling |
| **HASP/SIAP** | late 70s | Ocean sonar surveillance | Continuous input; the blackboard as a *situation board* maintained over time |
| **CRYSALIS / OPM** | late 70s–80s | Protein crystallography, planning | Multi-panel blackboards; planning as blackboard reasoning |
| **BB1** (Barbara Hayes-Roth) | 1985 | Control itself | The **control blackboard**: the system reasons about *its own next action* on a second blackboard — control becomes a first-class, inspectable problem |
| **GBB / commercial shells** | late 80s | Tooling | Generalized, reusable blackboard frameworks |

## 2. The canonical anatomy

Three parts, always the same three:

```
                    ┌───────────────────────────────────┐
                    │            BLACKBOARD             │
                    │  (shared, structured hypothesis   │
                    │   space — ALL system state)       │
                    │                                   │
                    │   level n   ┌───┐ ┌───┐           │
                    │   level ... │hyp│ │hyp│──links──▶ │
                    │   level 1   └───┘ └───┘           │
                    └────────▲──────────────┬───────────┘
                     writes  │              │  triggers (events)
                             │              ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────────┐
   │  KS #1  │  │  KS #2  │  │  KS #n  │  │      CONTROL      │
   │ cond ─▶ │  │ cond ─▶ │  │ cond ─▶ │  │  agenda of        │
   │ action  │  │ action  │  │ action  │  │  triggered KSs →  │
   └─────────┘  └─────────┘  └─────────┘  │  pick best → run  │
        ▲            ▲            ▲       └─────────┬─────────┘
        └────────────┴────────────┴─────────────────┘
                       "you may act now"
```

- **The blackboard** — a shared, structured workspace holding every partial solution
  (hypotheses), organized into **abstraction levels**, with links between levels. It is the
  *only* communication medium: knowledge sources never call each other.
- **Knowledge sources (KSs)** — independent specialists, each a *condition* ("when does my
  expertise apply?") plus an *action* ("write my contribution"). Adding or removing a KS
  requires no rewiring of the others — the board is the interface.
- **Control** — watches blackboard changes, collects the KSs whose conditions fire, ranks
  them (focus of attention), runs one, repeat. In BB1 this deliberation itself lives on a
  second blackboard.

### Hearsay-II's abstraction ladder (the classic picture)

```
   PHRASE        ┌────────────── "are any ships near Kenya?" ─────────┐
                 ▲ prediction (top-down)                 ▲ parse
   WORD-SEQ      │      ┌── "ships near" ──┐             │
                 ▲      │                  │             │
   WORD          │   [ships]   [near]   [Kenya]          │
                 ▲ syllable→word          ▲              │
   SYLLABLE      │  [sh-ips] [n-ear] ...  │              │
                 ▲ segment→syllable       │              │
   SEGMENT       │  [s][sh][ih]...        │              │
                 ▲ signal→segment         │              │
   PARAMETER     └── acoustic signal ─────┴──────────────┘
```

KSs work **bottom-up** (signal → segments → syllables → words) *and* **top-down** (a
predicted phrase proposes words to look for lower down). Control jumps to wherever the most
promising hypothesis is — the famous **island driving** strategy: grow confident islands of
interpretation outward instead of processing left-to-right. That freedom to attack the
problem wherever leverage is highest is what "opportunistic" means.

### The defining properties

1. **Incremental** — the solution accretes as partial contributions.
2. **Opportunistic** — the next action is chosen by the current board state, not a fixed script.
3. **Multi-level** — hypotheses live at multiple abstraction levels with cross-links.
4. **KS independence** — specialists are pluggable; the board is the only interface.
5. **No direct calls** — all coordination is mediated by shared, inspectable state.

---

## 3. Pathly's implementation

Pathly ("a board-driven control plane for orchestrating headless multi-agent software
development") maps onto the anatomy directly:

| Blackboard concept | Pathly realization |
|---|---|
| Blackboard | The **comms board**: `comms_messages` + `comms_artifacts` in the central SQLite DB, exposed via `/comms/*` |
| Hypothesis types | **Typed messages**: `decision`, `status`, `question`, `escalation`, `task`, artifacts |
| Abstraction levels | **Scope tiers**: feature → project → global, plus goals → task-DAG → tasks |
| Knowledge sources | **Roles**: architect, planner, builder, reviewer, tester, evaluator, explorer, … each a specialist prompt contract |
| KS condition/action contract | The **fragments layer** (`core/skills/fragments/`) — un-editable system-prompt layer owning all board reads/writes, context retrieval, progress logging, completion |
| Control | FSM pipeline + goal executors (`single`/`loop`/`team`) + DAG scheduler frontier |
| Opportunistic control | The **evaluator** (classifies an idle board, proposes next steps) + the `continue`/`block`/`escalate` decision gate |
| Focus of attention | `get_ready_tasks` — the dependency frontier of the goal's DAG |
| Solution accretion | Artifacts + decisions + statuses accumulating on the board, re-injected into every subsequent prompt |

```
                 ┌──────────────────────────────────────────────┐
                 │            PATHLY BOARD (SQLite)             │
                 │  global ── project ── feature   (scopes)     │
                 │  decisions · tasks(DAG) · artifacts · Q&A    │
                 │  status · escalations        ← typed rows    │
                 └───────▲──────────────────────────┬───────────┘
      board writes via   │                          │  context reconstruction
      fragments (forced) │                          ▼  per spawn:
   ┌───────────┐ ┌───────────┐ ┌───────────┐   governance (unconditional)
   │ architect │ │  builder  │ │ reviewer  │ + context_refs (by reference)
   │ (CLI proc)│ │ (CLI proc)│ │ (CLI proc)│ + semantic hits (relevance-gated)
   └─────▲─────┘ └─────▲─────┘ └─────▲─────┘ + code-intel block + history
         │ spawn       │ spawn       │ spawn
   ┌─────┴─────────────┴─────────────┴──────────────────────────┐
   │  CONTROL: FSM flow · goal executor · DAG frontier ·        │
   │  evaluator (opportunistic) · continue/block/escalate       │
   │  HUMAN = highest-authority KS (answers/decides ON board)   │
   └────────────────────────────────────────────────────────────┘
```

### The move the classics never had to make

> **The agents are deliberately amnesiac, so the board isn't just coordination — it's the
> entire memory of the system.** Classic KSs were resident processes watching the board;
> Pathly's are ephemeral CLI one-shots that die after every step. All continuity lives in
> the substrate. Most agent frameworks bolt memory onto agents (conversation history, vector
> stores); Pathly inverts it — context is *reconstructed* per spawn from typed, scoped board
> state. The intelligence lives in the substrate and the composition, not in any agent.
> Sessions are disposable; the board accumulates. That's the blackboard idea taken further
> than the originals, and it's the correct architecture for LLM agents, where context
> windows are ephemeral and expensive.

Two more structural moves worth naming:

- **The fragment layer is the KS activation contract, made non-editable.** A blackboard only
  works if every knowledge source reliably reads and writes it. By owning all board I/O in
  the un-editable fragments layer (while skills/abilities stay editable), the contract cannot
  be dropped by user customization. The per-task cadence — **claim → ground → build → verify
  → post → complete** — *is* the KS activation cycle, enforced structurally.
- **The human is on the board, not in a chat.** Questions, escalations, and decisions are
  board messages the human adjudicates. The human is another knowledge source — the
  highest-authority one — not a conversation partner. This is what enables "headless with
  supervision."

### The deliberate deviation

Classic blackboard control is **opportunistic**; Pathly's is mostly **deterministic** (FSM
stages, dependency-ordered DAG frontier). Only the evaluator and the decision gate are
opportunistic. For software delivery this is the right trade — auditability and
reproducibility beat emergence — but it makes Pathly a **plan-first blackboard**, not a
discovery-driven one. (BB1 solved "control as reasoning"; Pathly solves "control as
contract.")

### DAG tasks — the strongest single design

Tasks as self-contained prompts with **Files + Done-when + context_refs + depends_on** are
exactly what a stateless KS needs. *Done-when* is a falsifiable contract ("run it, don't
trust it"). `context_refs` is retrieval **by reference**, not similarity — the authoritative
design sections land in context deterministically, no embedding roulette. And unifying the
plan with the work queue (IMPLEMENTATION_PLAN → board DAG) kills plan/backlog drift.

---

## 4. How this differs from "session context" in the industry

The dominant industry pattern keeps memory **inside the agent**: the conversation window is
the working memory, optionally extended by summarization, vector recall, or checkpointed
graph state. Multi-agent variants share memory by **message passing** or a **shared
transcript**.

```
INDUSTRY (session-centric)                 PATHLY (substrate-centric)
─────────────────────────                  ──────────────────────────
┌─ Agent A ────────────┐                   ┌─ any agent (stateless) ─┐
│ [msg][msg][msg][msg] │ ← memory IS       │  spawn → context is     │
│  + vector recall     │   the transcript  │  REBUILT from the board │
└──────────┬───────────┘                   └───────────▲─────────────┘
           │ handoff = pass                            │ typed, scoped,
           ▼ the transcript                            │ governed reads
┌─ Agent B ────────────┐                   ┌───────────┴─────────────┐
│ inherits/summarizes  │                   │   BOARD (DB authority)  │
│ A's conversation     │                   │  decisions·tasks·artif. │
└──────────────────────┘                   │  survives every session │
   dies with the session                   └─────────────────────────┘
```

| Dimension | Session-centric (typical frameworks) | Pathly |
|---|---|---|
| Memory home | Inside the agent (message list, checkpoint, vector store per agent) | Outside every agent (DB-backed board) |
| Continuity | Dies or degrades with the session; summarization loses structure | Accumulates permanently; typed rows never "compress away" |
| Sharing | Transcript handoff / group-chat flattening | All agents read the same scoped substrate; no handoff object |
| Structure | Flat message sequence | Typed (decision/task/artifact/Q&A), scoped (feature/project/global), linked (DAG, reply_to, context_refs) |
| Retrieval | Recency + similarity | Governance (unconditional) + **references** (deterministic) + similarity (gated) |
| Human role | Chat participant | Highest-authority knowledge source on the board |
| Crash/restart | Lose or replay the conversation | Any agent respawns; the board is unaffected |
| Auditability | Read a transcript | Query typed state; exports (`STATE.json`, `BOARD.json`, `EVENTS.jsonl`) for git/audit |

The one-line contrast: **industry frameworks give agents a memory; Pathly gives the *system*
a memory and makes the agents disposable.** That is the blackboard thesis, executed with
modern parts (SQLite, HTTP, CLI one-shots, prompt composition).

Underneath it, one invariant makes the substrate trustworthy (the `state-one-authority`
work): **the DB is the single runtime authority; every disk file is a SEED read once in or
an EXPORT written DB→disk — never round-tripped for a runtime decision** — now enforced in
CI by `scripts/check_no_mirror_reads.py`.

---

## 5. Known gaps (and the honest next leaps)

First-hand findings from working inside the system:

1. **No truth maintenance.** The board preserves *claims*, not *truths* — a false design
   claim propagated architect → planner → task prompt untouched; only the cadence's
   ground-against-live-code step caught it. Next leap: typed `correction` replies that
   supersede automatically; a verifier arm in `/comms/consolidate` that re-checks
   code-referencing decisions against HEAD; and "promote decisions to gates" (a decision
   that matters becomes a CI check — exactly what the mirror-read rule did).
2. **Governance decays.** Unconditionally-injected decisions age into noise (a 22-day-old
   cross-feature decision injected into an unrelated task). Next leap: expiry/decay
   semantics — demote from the unconditional tier to the semantic tier when unreferenced,
   plus an `applies_to` blast-radius field.
3. **The two-identity split** (`<feature>` board scope vs `<fsm_feature>` run slug) is the
   recurrent bug source — identity is derived from storage location instead of issued at
   spawn. Next leap: make `run_id` the issued primary identity of telemetry, with board
   scope and storage slug as attributes of the run row, stamped once where truth is known.
