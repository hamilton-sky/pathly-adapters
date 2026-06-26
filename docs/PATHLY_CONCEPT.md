# Pathly — Concept, Capabilities & Value

> A plain-language map of *what Pathly is*, *what it is trying to achieve*, *why it
> matters*, and *how the pieces fit together*. Written for a new contributor or a
> curious user — not an API reference. For the wiring, see
> [`PATHLY_ARCHITECTURE.md`](PATHLY_ARCHITECTURE.md), [`ARCHITECTURE.md`](ARCHITECTURE.md),
> and the layer `CLAUDE.md` files.

---

## 1. The one-line idea

**Pathly is a software-development operating system that sits *on top of* AI coding
CLIs** (Claude Code, Codex, Copilot, Antigravity). It is **not** another AI coding
agent. It is the layer that decides *when* an agent acts, *in what role*, *with what
context*, and *when to stop and hand the wheel back to a human*.

```
        WITHOUT PATHLY                         WITH PATHLY
   ┌────────────────────────┐         ┌───────────────────────────────┐
   │  You  ⇄  one AI agent  │         │  You ──▶ a managed PIPELINE    │
   │  (one long chat)       │         │  STORM▸PLAN▸DESIGN▸BUILD▸       │
   │                        │         │  REVIEW▸TEST▸RETRO▸DONE          │
   │  • jumps to code       │         │  • each phase = a specialist    │
   │  • no design / review  │         │  • review & test feed back      │
   │  • no memory of phase  │         │  • state machine is the brain   │
   │  • invisible           │         │  • every step visible & costed  │
   └────────────────────────┘         └───────────────────────────────┘
```

The AI agents are **interchangeable labor**. The durable, user-owned artifact is the
**flow graph** — the shape of the work.

---

## 2. The goal — *kybernetes*, the steersman

The deepest framing of Pathly is the Greek *kybernetes* — the **steersman** who holds a
course by judgment, the root of "govern" and "governor."

Pathly is **not** an autonomous-AI system that closes the loop and removes the human.
It is a **human-supervised cybernetic system**: automation runs the *inner* loops
(build → review → test), and a human stays the *outer-loop* governor — owning the
destination and grabbing the wheel when judgment is required.

```
                 ┌──────────────────────────────────────────┐
                 │             HUMAN  (the captain)           │
                 │   owns the DESTINATION + final judgment    │
                 └───────────────▲───────────────┬────────────┘
                      escalate ▲ │               │ intent / setpoint
                               │ │               ▼
                 ┌─────────────┴─┴───────────────────────────┐
                 │        FSM GOVERNOR  (the helm)            │
                 │   holds course STORM ▸ … ▸ DONE            │
                 │   continue · block · escalate              │
                 └───────────────▲───────────────┬────────────┘
                      feedback ▲  │               │ next action
                  EVENTS.jsonl │  │               ▼
                 ┌─────────────┴──┴──────────────────────────┐
                 │   AI AGENTS  (the rowers / interchangeable)│
                 │   builder · reviewer · tester · architect  │
                 └────────────────────────────────────────────┘
```

The escalate signal is the system **admitting** a decision needs a steersman it does
not have. The hole where judgment enters is the point, not a gap.

**The trajectory:** single chat assistant → supervised pipeline → self-driving goal →
**parallel agent fleet** under one human commander (the unbuilt P3 + HQ Command Center).
The human moves *up* a level of abstraction: from steering one boat to being the
harbor-master of a fleet.

---

## 3. Capabilities (what is actually built)

| Capability | What it means | Where it lives |
|---|---|---|
| **FSM pipeline** | Features advance through `STORM→PLAN→DESIGN→BUILD→REVIEW→TEST→RETRO→DONE`; the DB is the source of truth | `pathly_orchestrator/` |
| **Role contracts** | ~13 specialized roles (architect=opus, builder=sonnet, reviewer, tester, scout=haiku…), tool-agnostic markdown | `core/agents/` |
| **Configurable flows** | Any arrangement of states, transitions, per-stage agent + engine — drawn on a visual canvas, executed live | `core/flows/*.flow.yaml`, `FlowEditor/` |
| **Library authoring** | Create new **agents *and* skills** from the UI; they appear as graph nodes | `/catalog/item/new`, `LibraryCatalog/` |
| **Host neutrality** | One `core/` truth compiles to 4 adapters; `agent_hint` is host-neutral | `adapters/`, `pathly-setup` |
| **Visible execution** | Every agent runs in a watchable terminal — headless *one-shot*, never *invisible* | `supervisor/`, Studio PTY tabs |
| **API-accurate cost** | Per-stage token + cost telemetry, patched to real billing | stop hook + `BILLING_UPDATE` |
| **Comms board** | A DB-backed message board where agents + humans coordinate (see §5) | `/comms/*`, Command Center |

### Two delivery modes (an important nuance)

```
  INTERACTIVE  (you type /pathly build)        RUNNER  (Studio "Start")
  ┌───────────────────────────────┐            ┌───────────────────────────────┐
  │ CLI reads installed skill file │            │ supervisor injects FULL prompt │
  │ ~/.claude/skills/pathly-*.md    │            │ via -p argv; composes from     │
  │ model from agent _meta          │            │ core/ in Python at runtime     │
  │ (architect=opus, scout=haiku)   │            │ model is RUN-LEVEL (one value) │
  │ needs: pathly-setup --apply     │            │ needs: nothing — runs as-is    │
  └───────────────────────────────┘            └───────────────────────────────┘
```

A Library-authored agent **runs immediately in runner mode** (prompt composed from
`core/`, inherits the run model). Giving it a *per-role* model or exposing it to the
interactive `/pathly` path is what needs `pathly-setup --apply --repair`.

---

## 4. The value

1. **Process discipline on a chaotic medium.** Raw agents skip design and review.
   Pathly makes "what phase are we in, and is it actually done?" a *machine-checked*
   fact (gates, `decision: continue|block|escalate`), not a vibe.
2. **Trust through visibility.** Automation you can't see, you won't trust. Every
   spawn is a visible terminal; every decision and artifact is on the board; every
   stage is costed to API accuracy.
3. **Vendor neutrality.** Your process, roles, and context are not locked to one AI
   vendor. Run BUILD on Codex and REVIEW on Claude in the *same* pipeline.
4. **The graph is the asset.** Models get cheaper and swappable; the flow you designed
   — which role acts when, what must be true before the rudder turns — is the durable
   intellectual property.

---

## 5. The board idea

The **comms board** is the orchestration substrate: a DB-backed message board
(`comms_messages` + `comms_artifacts`) where agents *and* humans post decisions,
discoveries, artifacts, questions, and DAG tasks. It is the Studio **Command Center**
surface and is injected into every agent prompt as governance + semantic context.

It is *communication* in Wiener's exact sense ("control **and communication** in the
animal and the machine") — the shared-state fabric the fleet coordinates through.

```
        ┌──────────────────────── COMMS BOARD ────────────────────────┐
        │  🔒 governance   📎 referenced artifacts   💡 semantic memory │
        └───────▲─────────────────────┬───────────────────────────────┘
                │ post / claim / answer │ retrieve_board_context (prompt injection)
   ┌────────────┴───┐   ┌──────────────▼───────────────┐
   │ humans         │   │ agents (builder, reviewer…)   │
   └────────────────┘   └───────────────────────────────┘

   BOARD ▸ GOALS ▸ per-goal TASK-DAG ▸ pluggable EXECUTORS
   ────────────────────────────────────────────────────────
   goal ──decompose──▶  ▢──▶▢──▶▢        executor ∈ { single | loop | team }
   (planner /          ▢──▶▢   ▲          single → 1 agent drains the DAG
    consultation)         └────┘          loop   → supervisor owns the frontier
                                          team   → runs a full FSM flow
```

**Status:** the self-driving system for *one* goal is shipped and visible/controllable
in Studio (Decompose / Run / Stop). Plus live: context-retrieval (hydrate artifact
sections on demand) and memory-consolidation (dedup + reflection). The only unbuilt
phase is **P3 — parallel** (across-goal lanes → worktree fan-in).

---

## 6. How this approach helps — coding *and* beyond

The pattern is **a configurable feedback graph over a roster of specialist agents,
coordinated through a shared board, with a human in the outer loop.** Nothing about it
is coding-specific.

```
  CODING                 │  RESEARCH              │  CONTENT / DOCS
  STORM  scope feature   │  define question       │  brief
  PLAN   user stories    │  search plan           │  outline
  DESIGN architecture    │  source gathering      │  structure
  BUILD  implement       │  draft synthesis       │  draft
  REVIEW adversarial     │  fact-check / verify   │  edit pass
  TEST   acceptance      │  citation audit        │  proofread
  RETRO  lessons         │  what's missing?       │  retro
```

The **states change; the machinery doesn't.** Any workflow that benefits from
*phases + specialist roles + a review/feedback loop + a coordinating board + human
escalation* maps onto Pathly. The flow editor is how you re-chart the helm for a new
domain — you design the steering apparatus itself, one level up.

---

## 7. Framework — editing MD files by spawning agents

Most Pathly artifacts are **Markdown** (plans, user stories, design docs, this file).
The framework for producing them is the pipeline itself: **plan the document, spawn
specialist agents to draft sections in parallel, assemble, review, commit.** The diagram
plan is part of the design phase — diagrams are authored as ASCII/Mermaid *before* prose
so structure is agreed first.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  MD-AUTHORING AS A PIPELINE                                          │
  │                                                                      │
  │  1. PLAN   ── outline + section list + DIAGRAM PLAN (ascii/mermaid)  │
  │     │         "which diagrams, what each must show"                   │
  │     ▼                                                                 │
  │  2. FAN-OUT  ── spawn one agent per section (parallel)               │
  │     ├─▶ agent: "§ Concept"     ─┐                                    │
  │     ├─▶ agent: "§ Board"        ├─ each returns markdown + diagrams  │
  │     ├─▶ agent: "§ Value"        │                                    │
  │     └─▶ agent: "§ Diagrams"    ─┘                                    │
  │     ▼                                                                 │
  │  3. ASSEMBLE ── stitch sections in order, dedupe, normalize headings │
  │     ▼                                                                 │
  │  4. REVIEW   ── adversarial pass: accuracy vs code, broken links,    │
  │     │           diagram/prose mismatch  →  fixes feed back to draft  │
  │     ▼                                                                 │
  │  5. COMMIT   ── write file, git commit, push, open PR                │
  └─────────────────────────────────────────────────────────────────────┘
```

This mirrors the product's own thesis: **decompose → fan out specialists → verify →
synthesize**, with diagrams planned up front and a human reviewing the PR. The same
loop that builds software builds its documentation.

---

## 8. One-paragraph summary

Pathly turns AI coding agents from a clever autocomplete into a **managed, visible,
multi-agent software-engineering team**: a finite-state machine for discipline, role
contracts for division of labor, a configurable flow graph you draw yourself, a comms
board for coordination, and a command center for the human who stays the steersman.
The agents are rowers; the ship is yours.
