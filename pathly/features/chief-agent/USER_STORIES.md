# User Stories — Chief Agent

Acceptance criteria are the testable definition of done. Design: [SPEC.md](SPEC.md).
Prerequisite: role-read-policy RRP-1..3 (run token, provenance, read predicate).

## US-1 — I talk only to the chief
> **Given** Pathly is running and I open the chat panel,
> **When** I write "add rate limiting to the API, standard rigor",
> **Then** the chief creates a goal on the right board, decomposes it, starts it with an
> executor it chose, and replies with what it started and the board ids, without me touching
> the board UI.

Acceptance:
- Every action goes through the existing HTTP API with the chief's run token; the board shows
  the goal, tasks and run exactly as if I had started them from the UI.
- The chief never edits project files and never runs a stage itself.
- It asks before stopping a run or starting a `strict` goal.

## US-2 — "How is it going?"
> **When** I ask for status,
> **Then** the chief answers from goal rollups and run summaries, citing board ids, and does not
> paste raw status streams.

## US-3 — Agent questions reach me through the chief
> **Given** a running stage asks a question (`interactions.py`),
> **When** it lands in the chief's inbox,
> **Then** the chief asks me in chat, sends my answer via `/runner/agent-answer`, and the board
> shows both the question and my answer.

Acceptance:
- The chief never answers on my behalf unless I said so in this thread; its answer quotes me.
- Ten events in one second produce one chief turn (debounce).

## US-4 — The chief's decisions bind every worker
> **Given** I tell the chief "use Postgres, not SQLite",
> **When** it posts a binding decision to `*`,
> **Then** the next builder, reviewer and tester prompts all contain it, still after someone
> acknowledges it, until it is superseded.

Acceptance:
- `to_agent='reviewer'` reaches the reviewer and not the builder.
- A builder-token post with `binding=1` is refused.
- A stage that ran across a newer binding decision is re-queued (`stale_directive`), not advanced.

## US-5 — It remembers last time
> **Given** a finished run on feature X,
> **When** a new run on X starts,
> **Then** its context includes the previous run's summary (episodic tier), except where the role
> wall withholds it (the reviewer does not get the builder's summary).

## US-6 — Lessons are promoted safely
> **Given** a run reaches RETRO/DONE,
> **Then** consolidate + promote run automatically; lessons appear on the project board; nothing
> with `author_source ∈ {legacy, none}` is promoted to global, and promotion to global needs
> evaluator or human approval.

## US-7 — It stays within budget and survives restarts
> **Given** the chief hits `chief.max_turns_per_hour` or the provider refuses a turn,
> **Then** chat shows "paused until …" instead of failing silently;
> **and given** the CLI session is lost, the next turn rebuilds goal status from the board and
> memory only.
