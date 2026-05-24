# Plan — Concierge Chat (Part C)

> The small LLM is a **receptionist + translator**, not a manager. It understands plain-language intent, picks the right `/pathly` command and which tool runs it, and relays progress back. It must **never** decide which files to edit, whether tests passed, or how to fix a failure — those belong to the FSM and the strong worker. Keep the small model strictly on the "talk to the human" side of the boundary.

This is the single most important rule. A weak local model that starts making engineering decisions will hallucinate and erode trust. Confine it to conversation and routing.

---

## Status

| Thing | Status |
|---|---|
| Concierge chat | ◻ partial — `studio-ai-chat` plan covers a local-Ollama *guidance* chat + `terminal:write` IPC; the *driver* layer (Phase 1+) is new |

---

## Why build it

- **Solves the ceremony problem.** A newcomer types "add a logout button" — the concierge maps it to `/pathly go ...`, picks `nano` rigor, and runs it. They never learn rigor levels, feedback files, or the 29 skills.
- **Solves the multi-tool goal.** A `Claude | Codex` toggle just selects which worker adapter the concierge routes to. Progress tracking is identical because both write the same `EVENTS.jsonl`.
- **Good cost story.** Chit-chat + intent parsing run on the **free local model**; you only spend Claude/Codex tokens on real code work.

---

## Architecture

```
  User (plain language)
        │
        ▼
  Concierge (small local LLM, e.g. Ollama phi4-mini)   ← cheap, always on
        │  intent → { command: "/pathly go ...", tool: "claude" | "codex" }
        ▼
  Worker adapter (HEADLESS mode, not the TTY)
        ├── claude  -p / Agent SDK     ──► structured JSON events
        └── codex   exec (non-interactive) ──► structured JSON events
        │
        ▼
  pathly/plans/<feature>/EVENTS.jsonl   ← BOTH workers write here
  STATE.json  +  feedback/*.md          ← FSM gates (GATES_PLAN.md) enforce correctness
        │  SSE /events/stream (already exists)
        ▼
  Concierge narrates progress  +  Studio Monitor shows it
```

---

## Non-negotiable design rules

1. **Drive headless modes, never the interactive terminal.** `claude -p` / the Agent SDK and `codex exec` emit structured JSON; the TTY gives you scrollback you'd have to screen-scrape (fragile against prompts, approval dialogs, escape codes). Keep the existing `terminal:write` pty path only for the *human to watch*; control flows through the structured interface.
2. **Pass `HUMAN_QUESTIONS.md` through verbatim.** When the worker blocks on a human question, show the exact text — never let the small model paraphrase a blocking question; it will distort it.
3. **Show raw worker output, summary on top.** Transparency matters when the worker is editing real files. Stream the structured events to the user; layer a one-line concierge summary above, don't replace.
4. **The concierge issues commands; the FSM owns correctness.** The concierge's only "power" is choosing the command + tool. Whether work is accepted is decided by the FSM gates — not by the small model.

---

## What the concierge may / may not do

| May | May not |
|---|---|
| Parse intent → choose `/pathly` subcommand | Decide which files to edit |
| Pick rigor (`nano/lite/standard/strict`) and tool | Judge whether tests/verify passed |
| Summarize event-log progress for the user | Resolve feedback files or fix failures |
| Surface `HUMAN_QUESTIONS.md` verbatim and collect the answer | Rewrite/paraphrase blocking questions |
| Ask one clarifying question when intent is ambiguous | Override an FSM gate or force a transition |

---

## Build phases (incremental — ship value early)

- **Phase 0 — Guidance (already planned).** Ollama chat answers "what should I type"; optional `terminal:write` with approval. This is `studio-ai-chat` as-is. Ship it first.
- **Phase 1 — One worker, headless.** Concierge → `claude -p` only. Parse intent → issue one `/pathly go` command → stream the worker's JSON events into the chat + Monitor. No tool switch yet.
- **Phase 2 — The toggle.** Add the `Claude | Codex` switch = a second worker adapter (`codex exec`). Same event-log tracking, so the Monitor "just works" for both. Persist the choice (Zustand persist, like `chatAutoApprove`).
- **Phase 3 — Blocking-question loop.** Detect `HUMAN_QUESTIONS.md` from the event stream; surface verbatim; feed the user's answer back to the worker; resume. The concierge writes to `HUMAN_ANSWER.md` — the FSM picks this up. The concierge must **not** write directly to STATE.json or feedback files.
- **Phase 4 — Concierge polish.** Friendly progress narration over the raw stream; cost meter from `AGENT_DONE` events (reuse `EventLog.tsx` aggregation).

---

## Open issues

- **Intent parsing reliability** — phi4-mini reliably mapping "add a logout button" to the right `/pathly` subcommand + rigor level is unproven. Phase 0 must validate this before Phase 1 commits to it as a driver. If Phase 0 shows the model struggling with routing decisions, the concierge scope narrows to guidance-only.

- **Event-log dedup on SSE reconnect** — the same `AGENT_DONE` event can replay on reconnect. Cost aggregation in `EventLog.tsx` will double-count. Concrete strategy needed before Phase 1: dedupe by `event.id` in the SSE consumer. "studio-monitor-live plan already flags this" is not a solution.

- **Two chats confusion** — Ollama (Phase 0 guide) vs Claude/Codex worker tabs (Phase 1+) are distinct things. "Be explicit" is not a design. The UI needs a visual boundary that makes the difference viscerally clear — not a tooltip, a structural separation.

- **Concierge boundary must be enforced by permissions, not just prompts** — the "may not" list only holds if the concierge process has no write access to STATE.json or feedback files. If Phase 3 needs to relay a human answer, it writes `HUMAN_ANSWER.md` only; the FSM reads and routes it. Audit the tools/permissions the concierge process is granted before Phase 3.

- **Headless API drift** — `claude -p` / `codex exec` flags change across versions. Isolate each behind a thin adapter so a flag change is a one-file fix.

---

## Dependency

**This plan depends on GATES_PLAN.md being built first.** The concierge routes "dumbly" by design — it can only do that safely because the FSM refuses to advance unless verify passed and scope held. Phase 1 should not ship until the `verify_gate` on `BUILDING->REVIEWING` is live.
