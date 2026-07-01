# Implementation Sequencing — code-intel track vs the fragment/profile plan

> **Decision recorded 2026-06-28.** Produced by a 5-agent analysis (read the 3 code-intel
> APPROACH.md plans → synthesize an order → adversarially verify). The verifier grep-checked
> the codebase and **overturned the synthesis's first draft** (it had wedged fragment-P1 before
> C; refuted as an invented dependency). This file records the corrected, verified order.
> Companion to [unified-cli-composition/DESIGN.md](unified-cli-composition/DESIGN.md),
> [unified-cli-composition/ORCHESTRATION_MODEL.md](unified-cli-composition/ORCHESTRATION_MODEL.md),
> and the three plans `code-context-injection/`, `code-intel-proxy/`, `gitnexus-integration/`.

## TL;DR

```
  procure + verify gitnexus binary      ← shared gate; FIRST (not a code change)
        │
        ▼
  ① B-core ──► ② C        ← the "affected-area awareness for goal-task execution" value
        │
        ├──────────────►  fragment-P1   ← INDEPENDENT parallel track (heaviest; blocks nothing)
        │                                 + P1e agnostic cleanup (tiny: architect/research)
        ▼
  ③ A  (last — narrow; interactive research-agent bonus; independent)
```

**Answer to "fragment plan first or code-intel first?": code-intel first.** The two tracks are
**fully independent** (grep: zero cross-references in either direction). Code-intel is cheaper
(M each) and self-unblocking; fragment-P1 is the heaviest (L) refactor and gates none of it.

## The dependency DAG (grep-verified)

```
   gitnexus binary ──(shared prerequisite — procure FIRST)──┐
        │                                                    │
        ▼                                                    ▼
  ① B-core ───HARD──► ② C (proxy) ········(soft)·······► ③ A (gitnexus MCP)
  runner/code_context.py   POST /code/query                host-native MCP
  (FOUNDATION)             (payoff surface, all roles)     (3 research agents)
        ╎ injects 🧭 at fsm_ops.py:244-248 (like retrieve_board_context), NOT via fragments

  ④ fragment-plan-P1  ◄═══ FULLY INDEPENDENT ═══►  the entire code-intel track
     (goal-backed profile)   blocks nothing · blocked by nothing
```

## The four initiatives

| # | Initiative | Effort | Reaches | Hard dependency | Value |
|---|---|---|---|---|---|
| ① | **code-context-injection (B-core)** | M | runner/headless agents | gitnexus binary (cli backend) | Foundation: `runner/code_context.py` provider (`none`/`cli`/`mcp`); deterministic 🧭 push. Ships **safe-off**. |
| ② | **code-intel-proxy (C)** | M | ALL roles, interactive + headless | **B-core** (reuses its backend) | The **payoff surface** — `POST /code/query` on demand. Needs only **live P0** fragment gating, NOT P1. |
| ③ | **gitnexus-integration (A)** | M | scout/quick/explorer only | gitnexus binary | Host-native MCP; **independent**, blocks nothing; narrowest reach. |
| ④ | **fragment-plan-P1** | **L** | goal-execution agents | live P0 machinery + goal-run substrate (both present) | Goal-backed board awareness (board-start-context + task-dag-post); converts Decompose/drain-dag/loop. Blocks none of ①②③. |

## Why this order

- **B-core first** — it is the unique unblocker (root of the code-intel DAG). Verified: `runner/code_context.py` and `/code/query` do **not** exist yet, so C cannot ship until B-core lands. Ships default-off / never-raises → behavior-identical to today. Its `cli` backend needs no host MCP and no fragment-P1.
- **C second** — highest standalone value (on-demand, all roles, interactive + runner). Gated on B-core; needs only the **already-live P0** conditional-fragment gating (`requires:` mechanism), **not** P1's goal-backed context.
- **A last** — independent (blocks nothing) but narrowest: only 3 read-only research agents, host-native. No reason to pull it earlier unless interactive code-nav for research agents is the immediate priority.
- **fragment-P1 parallel** — strategically the right end-state (CLAUDE.md's "every prompt flows through fragments" direction) and it completes goal-backed board awareness, but it is the heaviest, most-invasive change (rewrites the live goal-run path) and **blocks nothing** in the code-intel track. Run it whenever; never let it gate the cheap code-intel wins.

## Two kinds of context (why the tracks don't compete)

```
  fragment-P1 (board layer)   →  "WHAT is the goal? what tasks? what did others decide/make?"
                                  GOVERNANCE + SEMANTIC context (the comms board)

  code-intel B/C/A            →  "WHAT CODE does this task touch? who calls it?"
                                  STRUCTURAL context (the codebase)
```

Both are *dynamic context channels* injected at prompt-assembly (like `retrieve_board_context`),
distinct from the *static fragment* connection layer. Complementary, not competing.

## Risks (carry into the build)

1. **gitnexus binary is a single shared prerequisite** for B-core's `cli` backend, A's data source, AND C's real (non-null) results. Procure + verify its 4-tool stdio contract **before** B-core, or all three degrade to safe-null.
2. **B-core alone has no visible payoff** — the live 🧭 channel ("B-inject") is deferred; B-core lands the backend + a safe no-op injection point. For a visible demo, pull B-inject forward or go through to C.
3. **C rests on a reachability assumption** — a spawned headless agent AND an interactive session can both POST to `127.0.0.1:8765`. Verify empirically in C's first conversation.
4. **fragment-P1 is the highest-regression change** (live goal-run path). If it slips, it must not block C's fragment-independent core (route + CLI shim + permission ship first; retrofit the gating fragment after P1).

## First concrete action

**Not code.** Procure + verify the **gitnexus binary** and its stdio tool contract — it gates ①, ③, and ②'s real output. Then start **B-core**.
