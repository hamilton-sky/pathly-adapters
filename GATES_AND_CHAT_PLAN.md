# Plan — Cross-Tool Enforcement Gates + Concierge Chat

_Two related upgrades:_
_**Part B** makes Pathly's behavioral rules enforceable across Claude **and** Codex (no reliance on Claude-only host hooks)._
_**Part C** adds a small-LLM chat that drives a headless Claude/Codex worker and relays progress — the friendly front door to the enforced engine._

These are complementary: **B makes the worker trustworthy regardless of which tool runs; C makes it approachable.**

---

## Status check (verified against the repo)

| Thing | Status |
|---|---|
| Monitor progress rail (`done`/`active`/`pending`, conv counts) | ✅ built — `FsmView.tsx` |
| Monitor cost/token totals (`Total ↑ ↓ $` with no-telemetry fallback) | ✅ built — `EventLog.tsx:143-176` |
| Monitor "Health" strip (server / STATE.json / feedback / event count) | ❌ **not in repo** — git clean, no stash; the screenshot is a mockup or an uncommitted local build. Every value it shows is already in the store (`monitorSource`, `fsmState.current`, `events.length`, feedback from `FILE_CREATED`/`FILE_DELETED`), so it is a small additive component if wanted. |
| Server-side enforcement gates | ❌ not built — this plan |
| Concierge chat | ◻ partial — `studio-ai-chat` plan covers a local-Ollama *guidance* chat + `terminal:write` IPC; the *driver* layer (Part C) is new |

---

# Part B — Cross-Tool Enforcement Gates

## Principle

> Never ask the model to follow a rule you can check in code. The **only** enforcement layer shared by all hosts is the FSM (pure Python, hit over HTTP). So portable rules live there, expressed as **gates** the FSM runs before it accepts a state transition.

Host hooks (`pathly_hooks/*.py`) fire **only under Claude Code** (the README "hook parity gap"). Gates run inside the FSM server, which **both Claude and Codex already call** via `POST /complete_stage`. So a gate enforces a rule identically no matter which CLI is driving.

**Tradeoff (accept it):** gates are **checkpoint** enforcement — caught at the handoff between stages, not mid-keystroke. They cannot *prevent* a bad edit; they *catch it at the gate*, refuse to advance, and route back. For almost every Pathly rule that is exactly right: you don't need to block the keystroke, you need to refuse to call the work "done."

## Where it plugs in

`fsm_ops.complete_stage()` (`src/pathly_orchestrator/fsm_ops.py:130`) already does, in order:

1. delete resolved feedback files
2. `recover_state`
3. `route_feedback` → if blocked, return (no advance)
4. `evaluate_transition_rules` → compute `next_state`
5. `run_transition_actions`
6. `write_state` + append `STATE_TRANSITION`

**Insert gates between step 4 and step 5.** If a gate fails: write a feedback file, append a `GATE_FAILED` event, and **return a blocked response without advancing**. The next `next_action` call then routes that feedback file to the owning agent through the *existing* `feedback_routing` machinery — zero new routing code.

## New surface

### 1. `gates:` section in the flow YAML

Keyed by transition (`FROM->TO`) or by wildcard (`->TO`), mirroring `transition_actions`:

```yaml
# team.flow.yaml (addition)
gates:
  BUILDING->REVIEWING:
    - type: verify_gate          # a verify result must exist and say PASS
      artifact: VERIFY.md
      pass_marker: "RESULT: PASS"
      on_fail: REVIEW_FAILURES.md # feedback file to write → routes to builder
    - type: scope_gate            # working-tree diff must stay within declared files
      scope_file: CONVERSATION_PROMPTS.md
      on_fail: SCOPE_VIOLATION.md
  REVIEWING->TESTING:
    - type: require_artifact
      artifact: REVIEW.md
      on_fail: HUMAN_QUESTIONS.md
```

### 2. `run_gates()` in `fsm.py` (pure Python, sibling of `run_transition_actions`)

```python
def run_gates(flow, prev_state, next_state, storage_path, topic, conv) -> dict | None:
    """Return None if all gates pass; else a dict describing the failure.
    On failure, write the on_fail feedback file (dual-write to artifacts too)
    and append a GATE_FAILED event. Never advances state."""
    gates = (flow.get("gates") or {})
    to_run = gates.get(f"{prev_state}->{next_state}", []) + gates.get(f"->{next_state}", [])
    for gate in to_run:
        gtype = gate["type"]
        if gtype == "require_artifact":
            ok = (storage_path / gate["artifact"]).exists()
        elif gtype == "verify_gate":
            ok = _verify_passed(storage_path / gate["artifact"], gate["pass_marker"])
        elif gtype == "scope_gate":
            ok = _scope_clean(storage_path, gate["scope_file"])  # git diff vs declared files
        else:
            raise RuntimeError(f"Unknown gate type: {gtype!r}")
        if not ok:
            _write_feedback(storage_path, gate["on_fail"], _gate_reason(gate))
            append_event(storage_path, {"type": "GATE_FAILED",
                                        "gate": gtype, "transition": f"{prev_state}->{next_state}"})
            return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
    return None
```

Gate primitives:
- **`require_artifact`** — file must exist. (Simplest; `evaluate_transition_rules` already does `on_artifact` routing, but that *routes*; this *blocks*.)
- **`verify_gate`** — read the artifact, require a pass marker. Stops "claimed success without running verify."
- **`scope_gate`** — `git diff --name-only` (working tree) vs the file list declared in the conv's `CONVERSATION_PROMPTS.md`; any path outside the declared set fails. Stops silent out-of-scope edits/refactors. (Run with `cwd` = project root, same derivation `run_transition_actions` already uses.)

### 3. Wire into `complete_stage`

```python
# after next_state is computed, before run_transition_actions(...)
gate_failure = run_gates(flow_config, state_info["current_state"], next_state,
                         storage_path, topic, state_info["conv"])
if gate_failure is not None:
    # do NOT write_state — re-route through normal feedback handling
    feedback = route_feedback(flow_config, storage_path)
    return _blocked_response(feedback, state_info)  # reuses existing machinery
```

## Why this is the right shape

- **Cross-tool by construction** — lives in `fsm.py`/`fsm_ops.py`, zero LLM/host imports, runs for anyone hitting `/complete_stage`.
- **Reuses everything** — failures become feedback files; `feedback_routing` + `route_feedback` already send them to the right agent and block the pipeline. The Monitor already shows `FILE_CREATED`; add `GATE_FAILED` to the event color map.
- **Declarative** — rules live in the flow YAML next to the transitions they guard, not buried in prose.

## Tests (pure, fast)

- `run_gates` returns `None` when artifact present / verify passes / diff in-scope.
- `require_artifact` missing → writes `on_fail` file + `GATE_FAILED` event, no `STATE.json` change.
- `verify_gate` artifact present but marker absent → fail.
- `scope_gate` with a diff touching an undeclared path → fail; in-scope diff → pass.
- `complete_stage` end-to-end: gate failure returns a blocked response and state does **not** advance; second call after the agent resolves the feedback file advances normally.

## Limitations / decisions

- **Checkpoint, not in-the-moment** (see Principle). Pre-emptive blocking still requires host hooks (Claude-only). Keep both: gates for portability, hooks as a Claude-only bonus.
- **`scope_gate` needs a declared file list.** If a conv doesn't declare files, the gate no-ops (don't invent scope). Decide: warn vs skip — recommend skip + a one-line note in the event.
- **Don't double-commit.** `BUILDING->REVIEWING` already runs a `commit` action; run gates **before** that action so a failing build is never committed.

---

# Part C — The Concierge Chat

## Principle

> The small LLM is a **receptionist + translator**, not a manager. It understands plain-language intent, picks the right `/pathly` command and which tool runs it, and relays progress back. It must **never** decide which files to edit, whether tests passed, or how to fix a failure — those belong to the FSM (Part B) and the strong worker. Keep the small model strictly on the "talk to the human" side of the boundary.

This is the single most important rule. A weak local model that starts making engineering decisions will hallucinate and erode trust. Confine it to conversation and routing.

## Why build it

- **Solves the ceremony problem.** A newcomer types "add a logout button" — the concierge maps it to `/pathly go ...`, picks `nano` rigor, and runs it. They never learn rigor levels, feedback files, or the 29 skills.
- **Solves the multi-tool goal.** A `Claude | Codex` toggle just selects which worker adapter the concierge routes to. Progress tracking is identical because both write the same `EVENTS.jsonl`.
- **Good cost story.** Chit-chat + intent parsing run on the **free local model**; you only spend Claude/Codex tokens on real code work.

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
  STATE.json  +  feedback/*.md          ← FSM gates (Part B) enforce correctness
        │  SSE /events/stream (already exists)
        ▼
  Concierge narrates progress  +  Studio Monitor shows it
```

## Non-negotiable design rules

1. **Drive headless modes, never the interactive terminal.** `claude -p` / the Agent SDK and `codex exec` emit structured JSON; the TTY gives you scrollback you'd have to screen-scrape (fragile against prompts, approval dialogs, escape codes). Keep the existing `terminal:write` pty path only for the *human to watch*; control flows through the structured interface. The `studio-ai-chat` plan's "type into the terminal" mechanism is fine for Level-2 guidance but **not** for the Level-3 driver.
2. **Pass `HUMAN_QUESTIONS.md` through verbatim.** When the worker blocks on a human question, show the exact text — never let the small model paraphrase a blocking question; it will distort it.
3. **Show raw worker output, summary on top.** Transparency matters when the worker is editing real files. Stream the structured events to the user; layer a one-line concierge summary above, don't replace.
4. **The concierge issues commands; the FSM owns correctness.** The concierge's only "power" is choosing the command + tool. Whether work is accepted is decided by Part B's gates — not by the small model.

## What the concierge may / may not do

| May | May not |
|---|---|
| Parse intent → choose `/pathly` subcommand | Decide which files to edit |
| Pick rigor (`nano/lite/standard/strict`) and tool | Judge whether tests/verify passed |
| Summarize event-log progress for the user | Resolve feedback files or fix failures |
| Surface `HUMAN_QUESTIONS.md` verbatim and collect the answer | Rewrite/paraphrase blocking questions |
| Ask one clarifying question when intent is ambiguous | Override an FSM gate or force a transition |

## Build phases (incremental — ship value early)

- **Phase 0 — Guidance (already planned).** Ollama chat answers "what should I type"; optional `terminal:write` with approval. This is `studio-ai-chat` as-is. Ship it first.
- **Phase 1 — One worker, headless.** Concierge → `claude -p` only. Parse intent → issue one `/pathly go` command → stream the worker's JSON events into the chat + Monitor. No tool switch yet.
- **Phase 2 — The toggle.** Add the `Claude | Codex` switch = a second worker adapter (`codex exec`). Same event-log tracking, so the Monitor "just works" for both. Persist the choice (Zustand persist, like `chatAutoApprove`).
- **Phase 3 — Blocking-question loop.** Detect `HUMAN_QUESTIONS.md` from the event stream; surface verbatim; feed the user's answer back to the worker; resume.
- **Phase 4 — Concierge polish.** Friendly progress narration over the raw stream; cost meter from `AGENT_DONE` events (reuse `EventLog.tsx` aggregation).

## How B and C lock together

Part B's gates mean it does not matter that the concierge is "dumb" or that the worker might be Claude or Codex: **the FSM refuses to advance unless verify passed and scope held.** The concierge can route confidently because correctness is enforced downstream, server-side, for every tool. C is safe *because* B exists — build B first.

## Risks

- **Weak-model overreach** — mitigated by the may/may-not boundary; keep the concierge prompt narrow and give it tools that only *read* state + *issue* commands.
- **Headless API drift** — `claude -p` / `codex exec` flags change across versions; isolate each behind a thin adapter so a flag change is a one-file fix.
- **Event-log dedup** — on SSE reconnect the same `AGENT_DONE` can replay; dedup by event id before any cost aggregation (the `studio-monitor-live` plan already flags this).
- **Two "chats" confusion** — be explicit: Ollama = guide (Phase 0); Claude/Codex tabs = workers (Phase 1+). Don't blur them in the UI.

---

## Recommended order

1. **Part B gates** — foundation; makes the worker trustworthy for any tool. Start with `verify_gate` on `BUILDING->REVIEWING`.
2. **Concierge Phase 1** — single headless Claude worker over the now-safe engine.
3. **Concierge Phase 2** — add the Codex toggle.
4. (Optional, parallel) the Monitor **Health strip** — small additive component from data already in the store.
