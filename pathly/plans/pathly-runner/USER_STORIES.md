# pathly-runner — User Stories

## S1: `pathly-run <topic>` drives FSM autonomously from current state to DONE

**As a** developer running a pathly-managed project,
**I want** a single CLI command that drives the FSM from wherever it currently is all the way to DONE,
**so that** I do not have to manually invoke each builder conversation.

### Acceptance criteria

- `pathly-run my-feature` exits with code 0 when the flow reaches the DONE state.
- STATE.json shows `"current": "DONE"` after a successful run.
- Each stage transition is logged to EVENTS.jsonl as a `STATE_TRANSITION` event with `from_state` and `to_state` fields.
- The runner works for the `team`, `debug`, and `explore` flows (i.e. no hardcoded flow name in runner.py).
- If `_next_action` returns a response that is neither `current_state` nor `blocked`, the runner exits with code 1 and prints a descriptive error.
- If the runner encounters a `RuntimeError` (e.g. from the Claude subprocess), it prints the error message and exits with code 1.

---

## S2: Each stage's agent output streams to terminal in real-time

**As a** developer watching a run,
**I want** Claude's stdout and stderr to appear in my terminal as they are produced,
**so that** I can follow the agent's work without waiting for buffered output.

### Acceptance criteria

- Claude subprocess stdout and stderr are not buffered — output appears in the terminal as each line is produced (subprocess.Popen with `stdout=sys.stdout, stderr=sys.stderr`).
- Before invoking Claude for a stage, the runner prints a stage header in the format: `── [BUILDING] agent: builder ──`
- After each successful transition, the runner prints: `✓ BUILDING → REVIEWING` (using the actual from/to state names).
- The stage header uses the `current_state` value from `_next_action` and the `agent` field from the same response.

---

## S3: Studio shows live progress while runner is active (no extra wiring needed)

**As a** developer monitoring from the Studio UI,
**I want** the EventLog and pipeline bar to update as the runner progresses through states,
**so that** I have a live view without any additional integration work.

### Acceptance criteria

- Studio EventLog shows all `STATE_TRANSITION` events within 2 seconds of each transition occurring. This works because the runner calls `fsm.append_event` which writes to EVENTS.jsonl, and Studio's SSE server already tails that file — no extra wiring is required.
- The FsmView pipeline bar updates as states change (driven by the same SSE stream).
- No new endpoints, sockets, or pub/sub mechanisms are added to satisfy this story — it is a zero-code acceptance criterion confirming the existing SSE integration is sufficient.

---

## S4: Human checkpoints pause runner, print question, resume after user confirms

**As a** developer running pathly autonomously,
**I want** the runner to stop and wait for my input when a human checkpoint is reached,
**so that** I can answer questions or resolve blockers before the run continues.

### Acceptance criteria

- When `_next_action` returns `{blocked: True, target_agent: "human"}`, the runner prints the contents of the blocking file and waits for `input("Press Enter when resolved: ")`.
- The printed output includes the file path and the `instructions` field from the response (if present), formatted as:
  ```
  ⚠  Human checkpoint — <file>
  <instructions>
  ```
- After the user presses Enter, the runner calls `_complete_stage(resolved_files=["<file>"])` and continues the loop.
- The runner does NOT delete the blocking file manually — it passes the filename to `_complete_stage` via `resolved_files`, and `_complete_stage` owns deletion.
- When `_next_action` returns `{blocked: True, target_agent: "<non-human>"}`, the runner prints a routing message (`⚠ Blocked on <file> → routed to <agent>`) and exits with code 1 — this case is not interactively resolvable by the runner.

---

## S5: Decide blocks surface options to user in terminal, runner waits for choice

**As a** developer running pathly autonomously,
**I want** the runner to present me with options when `_complete_stage` returns a decide block,
**so that** I can make architectural or process decisions without leaving the terminal.

### Acceptance criteria

- When `_complete_stage` returns `{decide: True, question, options, default}`, the runner prints:
  ```
  ? <question>
    [<key>] <value>
    ...
  ```
- The runner reads user input via `input("Choice (default: <default>): ")`.
- If the user enters a key that matches one of the options keys, that key is used.
- If the user enters an empty string or an invalid key, the `default` key is used.
- After a valid choice is resolved, the runner calls `_complete_stage(flow, topic, project_root, decision=<chosen_key>)` and continues.
- The chosen key and the resulting next state are both printed to the terminal.

---

## S6: `--flow`, `--rigor`, `--model`, `--project-root` flags

**As a** developer using pathly-runner,
**I want** CLI flags to configure the flow, rigor level, model, and working directory,
**so that** I can run the tool in different project configurations without editing config files.

### Acceptance criteria

- `pathly-run <topic> --flow debug` uses `debug.flow.yaml` (passes `flow="debug"` through to `_next_action` and `_complete_stage`).
- `pathly-run <topic> --rigor lite|standard|strict` is accepted; the value is stored (available for future use); invalid values cause argparse to exit with code 2.
- `pathly-run <topic> --model claude-sonnet-4-6` passes the model string to the Claude subprocess as `--model <model>`. Default is `claude-sonnet-4-6`.
- `pathly-run <topic> --project-root /abs/path` sets the working directory for the Claude subprocess to that path rather than `Path.cwd()`.
- Omitting `--project-root` defaults to `str(Path.cwd())`.
- All flags are optional except `<topic>`.

---

## S7: Runner recovers from STATE.json on restart (resume interrupted runs)

**As a** developer whose run was interrupted,
**I want** re-running `pathly-run my-feature` to resume from where it left off,
**so that** I do not have to restart from STORMING after a crash or cancellation.

### Acceptance criteria

- When `STATE.json` exists in the feature's plans directory and `current` is not `DONE`, re-running `pathly-run my-feature` resumes from `current` — it does not restart from the first state.
- On resume, the runner prints: `Resuming my-feature from BUILDING (conv 2)` (using the actual state and `current_conversation` values from STATE.json).
- This works because `_next_action` reads STATE.json internally — the runner does not need to implement its own resume logic; it simply calls `_next_action` and trusts the FSM.
- If STATE.json does not exist, the runner starts from the flow's initial state without error.
