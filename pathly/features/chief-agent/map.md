# Map: chief-agent

## Destination

One long-lived chief agent per project that the human talks to through the Studio chat. Each
turn is a headless `claude -p --resume` spawn through the existing spawn hosts, holding a
`chief` run token. It drives Pathly only through the HTTP API (goals, decompose, run, stop,
agent-answer, board posts), never runs a stage, relays agent questions to the human, posts
binding decisions that every worker prompt carries until superseded, remembers past runs through
an episodic memory tier behind the role read wall, and schedules lesson promotion with a
provenance gate. Design: `SPEC.md`; stories: `USER_STORIES.md`; the human-facing ticket list
(CHF-1..8) is `IMPLEMENTATION_PLAN.md`.

**Prerequisite.** role-read-policy tickets 01–10 (RRP-1..3) are built: run tokens, server-stamped
provenance, `runner/read_policy.py`. `commands.md` Smoke fails until they are.

**The bar.** `python -m pytest tests/comms_board/test_chief_acceptance.py -q` passes with a fake
spawn host: a chat message creates a goal on the board through the API with a `chief` token; an
agent question reaches the chief thread and the human's answer unblocks the run; a binding
decision to `*` appears in the next builder, reviewer and tester prompts after an
acknowledgement; a builder-token `binding` post is refused; and the next run on the same feature
sees the previous run's episode while a reviewer does not see the builder's. And
`python -m pytest tests/ -q -p no:cacheprovider` passes in full. Ticket 13 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py chief-agent` (with `FLOW_DIR=pathly/features`). Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py chief-agent --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.

## Decisions so far

- Plan — chief turns lock on their own key `("chief", <project_root>)`, not the project board,
  so turns serialize per project and never block the evaluator or consolidate (learnings.md).
- Plan — the chief's tools are `curl` lines in fragments, like every other agent; no new MCP
  server. Its run token carries role `chief`, so the server, not the prompt, enforces what only
  the chief may do (`binding`, relayed answers).
- Plan — a relayed answer must name the `chief_thread` message id of the human's words; the
  server checks the id exists, is `role=human` and belongs to this project.
- Plan — mid-run delivery of a directive is a post-run check (`stale_directive` → re-queue), since
  a headless run takes no input after spawn (SPEC § C6.3).
- Plan — run category gains `chief`; the closed set is widened in all places at once (ticket 04).
- Plan — `chat_agent.py` stays as the no-LLM fallback when `chief.enabled` is off.

## Open questions

- SPEC § F Q1: subscription terms for event-triggered turns. Planned default: `chief.enabled`
  off by default, `chief.max_turns_per_hour=20`, event-triggered turns only while enabled. Ask
  before raising.
- SPEC § F Q4: absorb `director.md` or call it? Planned default: the chief contract absorbs its
  routing; `director` stays for interactive `/pathly`.
- Model for the chief role: planned default `sonnet` (turn volume), `opus` configurable.
