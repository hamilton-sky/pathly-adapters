# Local Operator — Spec

> Supersedes the `local-worker-adapter` draft (2026-10-14): the local
> model is NOT a planner worker. It is a small operator — it answers
> simple questions and performs simple actions through Pathly's API,
> which spawns the heavy work on cloud headless CLIs.

## Problem

HQ answers questions but cannot do anything; every trivial operation
("rerun the failed test stage", "start the planner for goal X",
"pause the builder") currently costs frontier-model tokens through the
chief. The Mac already runs capable free local models, and simple
operations are single API calls — well within a small model's
tool-calling ability. There is no free, low-ceremony way to act on the
fleet.

## Goal and the bar

HQ gains an **Operator (local)** mode: the free local model answers
simple questions from the board packet (as in `hq-copilot`) AND invokes
a tiny, bounded set of Pathly API tools. Every mutating action is
proposed in the chat and executed only after the user confirms. The
operator never touches directives, agent questions, settings, or
complex orchestration — that is the chief's job.

**The bar:** `python -m pytest tests/local_operator/test_acceptance.py
-q -p no:cacheprovider` passes — with a stubbed model, "rerun the
failed test stage" produces a confirmation proposal and, after
confirmation, exactly one `retry_stage` API call; without confirmation
no call is made; and the model is never offered the forbidden tools
(answer_question, directives, settings).

## Stories

### Simple actions, free

**As a** Pathly user, **I want** to say "pause the builder" / "rerun
the failed stage" / "start a planner for goal X" **so that** trivial
ops cost nothing and take one sentence.

- [ ] The operator proposes the exact action (tool + args) in the chat.
- [ ] Nothing mutating executes without my explicit confirm.
- [ ] Reads ("what's the run state?") never need confirmation.

### Heavy work still goes to cloud

**As a** Pathly user, **I want** the operator to spawn — not perform —
heavy work **so that** planning/building still run on frontier CLIs.

- [ ] "Plan the auth refactor" → operator spawns a planner run
      (cloud headless CLI) via the API; the planner composes the plan.
- [ ] The operator never composes plans, writes code, or edits files
      itself.

### Small hands by construction

**As a** Pathly user, **I want** the operator incapable of dangerous
operations **so that** a confused local model cannot damage the fleet.

- [ ] The tool surface is exactly: spawn_planner, start_run,
      pause_run, resume_run, retry_stage, post_message. Nothing else is
exposed to the model.
- [ ] Every executed action is audit-logged with actor
      `local-operator`.

## Scope

In:
- Settle: the exact 6-tool surface + confirmation UX (per-action
  confirm cards in chat).
- Server: verify each tool maps to an existing endpoint; thin wrappers
  where missing.
- Studio: `llm:operate` tool loop in the Electron main process
  (extends `llm.ts`): tool schemas, loop, `operator:confirm` IPC
  events, audit logging.
- HQ picker: "Operator (local)" mode + Run/Cancel confirmation UI.
- Audit log of executed actions.

Not in scope:
- Complex orchestration, binding directives, answering agent
  questions, settings/tiers/secrets: the chief (frontier).
- Composing plans inline: the operator spawns the planner worker
  instead (the chief works the same way — it orchestrates through the
  API; the planner CLI composes).
- File/shell tools for the local model: explicitly out. The operator
  acts through the API, never on the repo directly.
- Ollama / Python harness: moot under this design — the loop lives in
  Electron main next to `llm.ts`, tools are HTTP to localhost. No new
  runtime dependency.
- The read-only HQ copilot: `pathly/features/hq-copilot/` (the
  operator mode reuses its board packet).

## Happy path

1. User switches HQ to Operator (local), types "rerun the failed test
   stage" → operator proposes: `retry_stage(run=goal-boot, stage=test)`
   → chat shows Run/Cancel → user hits Run → API executes → operator
   confirms "test stage rerunning" → audit entry recorded.
2. User types "plan the auth refactor" → operator proposes
   `spawn_planner(goal=auth-refactor)` → user confirms → cloud planner
   CLI spawns via the API → planner composes the plan for human review.
3. User types "answer the builder's question with yes" → operator
   refuses: answering agent questions is human-or-chief only, and
   points at the right surface.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Model proposes a tool outside the 6 | Impossible by construction (never in the schema); belt-and-braces: the loop rejects unknown tools | 03 |
| User hits Cancel | No API call; operator acknowledges and stands by | 03, 04 |
| Two mutating actions in one reply | Each gets its own confirm card; they execute in order, each confirmed | 03 |
| API call fails | Operator reports the error plainly; no retry loop beyond one automatic retry | 03 |
| Spawn requested but daycap/session ceilings hit | API refuses as today; operator relays the refusal, suggests the chief | 02 |

## Design

The loop lives in the Electron main process (extends
`studio/src/main/ipc/llm.ts`), because the model already lives there
and the tools are plain HTTP calls to the local Pathly server.

```
[HQ Operator mode] ── message ──► [llm:operate]
      │                                │
      │  system prompt (operator)      │  board packet (hq-copilot's
      │  + 6 tool schemas              │  hq_context) + message
      │                                ▼
      │                          [local model]
      │                                │ tool call
      │                                ▼
      │◄── Run/Cancel card ── [confirm gate] (mutating only)
      │         │ Run
      │         ▼
      │   [Pathly HTTP API → existing endpoints]
      │         │ result ──► model ──► final answer
      ▼         ▼
[audit log: actor=local-operator, tool, args, result]
```

Failure path: model never sees dangerous tools; unknown tool →
rejected; API error → reported, single retry max.

### Decisions

- **Loop in Electron main, not a Python/Ollama harness** — options:
  Ollama + Python harness; extend `llm.ts`. Chosen: extend `llm.ts`.
  Why: the model is already loaded there, tools are localhost HTTP,
  zero new dependencies. (This supersedes the local-worker-adapter
  ticket 01 Ollama settle.)
- **Per-action confirmation in chat UI** — options: auto-execute;
  confirm each. Chosen: confirm each mutating action. Why: a weak
  model with hands that spend real money (cloud spawns) must not act
  unilaterally. Reads need no confirm.
- **6 tools, fixed** — spawn_planner, start_run, pause_run, resume_run,
  retry_stage, post_message. Rejected: answer_question (human/chief
  only), directives (judgment), settings/tiers/secrets (fences),
  shell/file tools (not the operator's job).
- **Operator never composes** — it spawns the planner worker for
  composing, exactly like the chief does. The operator is hands, not
  brains.

## Interfaces

- `llm:operate` IPC (main): `{message, mode}` → streams
  `operator:token | operator:confirm {tool, args} |
  operator:done | operator:error`.
- `operator:confirm` → renderer shows Run/Cancel →
  `operator:resolve {approved: bool}`.
- Server: the 6 tools map onto existing endpoints (ticket 02 verifies
  each; thin wrappers only where missing).
- Audit: board message (or dedicated log) per executed action:
  `{actor: "local-operator", tool, args, result, ts}`.

## Migration and compatibility

None. Operator mode is opt-in per HQ session; the read-only copilot
and everything else behave as today.

## Risks

- Model calls the wrong tool/args — mitigation: tiny surface,
  confirmation shows exact args, audit log; single retry max.
- Confirmation fatigue → user blanket-approves — mitigation: confirm
  cards show the money-relevant facts (what spawns, estimated scope);
  reads never interrupt.
- Prompt-injection via board packet steering a tool call — mitigation:
  packet is data-not-instructions (hq-copilot), tools are few and
  confirmed; injection can at worst propose, never execute.
