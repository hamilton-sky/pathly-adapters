# pathly-runner — Architecture Proposal

## Component diagram

```
pathly-run (CLI entry point)
     ↓
runner.py: run_flow(flow, topic, project_root, rigor, model)
     ↓ calls directly (no HTTP)
_next_action() / _complete_stage()  ← mcp_server.py
     ↓
fsm.py: recover_state / evaluate_transition_rules / route_feedback / run_transition_actions
     ↓ writes
STATE.json + EVENTS.jsonl  ← on disk
     ↓ tailed by
http_server.py SSE  ←  Studio Monitor (no extra wiring needed)
     ↓
invoke_agent(instructions, project_root, model)
     ↓ subprocess
claude -p <prompt> --dangerously-skip-permissions  (cwd=project_root)
     ↓ streams to terminal
```

## Data flow — happy path

1. User runs `pathly-run my-feature`.
2. `main()` parses args, resolves `project_root`, calls `run_flow(...)`.
3. `run_flow` calls `_next_action(flow, topic, project_root)`.
   - Returns `{current_state, conv, agent, instructions, storage_path, limits}`.
4. Runner prints the stage header: `── [BUILDING] agent: builder ──`.
5. Runner calls `invoke_agent(instructions, project_root, model, state, topic)`.
   - Spawns `claude -p <prompt> --model <model> --dangerously-skip-permissions` with `cwd=project_root`.
   - subprocess stdout/stderr pipe directly to the terminal.
6. Claude runs, uses its file tools, writes output, exits 0.
7. Runner calls `resolve_stage(...)` which calls `_complete_stage(flow, topic, project_root)`.
   - If `next_state`: prints `✓ BUILDING → REVIEWING`, loops back to step 3.
   - If `done`: prints `✓ Complete`, exits 0.
   - If `decide`: calls `handle_decide(...)`, loops.
   - If `blocked/human`: prints checkpoint, waits for Enter, passes `resolved_files`, loops.
   - If `blocked/<agent>`: runs feedback agent, passes `resolved_files`, loops (up to MAX_FEEDBACK_ROUNDS).
8. `_next_action` / `_complete_stage` call `fsm.append_event` on each transition.
9. Studio SSE tails EVENTS.jsonl and pushes STATE_TRANSITION events to the browser automatically.

## Key decisions

### Direct Python call, not HTTP

The runner imports `_next_action` and `_complete_stage` directly from `pathly_orchestrator.mcp_server`. This avoids requiring a running HTTP server as a prerequisite, removes a network round-trip per stage, and keeps the runner testable with simple mocks. The HTTP server (`pathly-fsm-http`) remains useful for Studio integration but is not a runner dependency.

### `claude -p` subprocess for agent invocation

Agent contracts are already written for Claude Code's file tools (Read, Write, Bash, Grep, Glob, Edit). The runner passes the agent's `instructions` field (already loaded from the agent .md file by `_next_action`) as the prompt. Using `subprocess.Popen` with `stdout=sys.stdout, stderr=sys.stderr` gives real-time streaming to the terminal without any extra buffering logic.

### SSE works automatically — zero extra wiring

The runner calls FSM functions that internally call `fsm.append_event`. That function writes to `EVENTS.jsonl`. The Studio HTTP server's SSE endpoint already tails that file and pushes events to connected browsers. This means Studio live-updates with no changes to the runner, the HTTP server, or the Studio frontend.

### No new FSM logic in runner.py

`runner.py` is a thin orchestration loop. All state-machine logic (transition evaluation, feedback routing, transition actions, state writes) lives in `fsm.py` and `mcp_server.py`. The runner is not allowed to write STATE.json or EVENTS.jsonl directly — it always goes through `_next_action` / `_complete_stage`.

### Feedback file deletion owned by `complete_stage`

When the runner resolves a human checkpoint or a feedback file, it passes the filename via `resolved_files` to `_complete_stage`. The FSM function owns the deletion. The runner never calls `os.remove` or `Path.unlink` on feedback files. This keeps deletion logic in one place and ensures the FSM's view of resolved files stays consistent.

### Feedback loop capped at MAX_FEEDBACK_ROUNDS = 3

If `_complete_stage` returns `blocked` for the same agent-targeted feedback file more than 3 times, the runner escalates by writing a `HUMAN_QUESTIONS.md` file and prompting the user interactively. This prevents infinite loops while still giving the feedback agent multiple attempts to resolve the issue.

### `--timeout` flag for subprocess

The runner accepts `--timeout <seconds>` (default 600). If the Claude subprocess does not exit within the timeout, the runner kills it and raises `RuntimeError`. This prevents a hung subprocess from blocking an unattended run indefinitely.
