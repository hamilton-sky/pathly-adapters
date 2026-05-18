# pathly-runner — Implementation Plan

## Overview

Add a `pathly-run <topic>` CLI command that drives the Pathly FSM autonomously from the current state to DONE. The runner is a thin loop around the existing `_next_action` and `_complete_stage` functions in `mcp_server.py`. It invokes Claude as a subprocess per stage, surfaces human checkpoints and decide blocks interactively, and writes events to EVENTS.jsonl via the existing FSM functions so Studio sees live progress automatically.

Rigor: standard — 4 conversations.

## Pre-flight

Run before starting Conv 1. Expected outputs are noted inline.

```bash
python -c "from pathly_orchestrator.mcp_server import _next_action, _complete_stage; print('OK')"
python -c "from pathly_orchestrator.fsm import recover_state; print('OK')"
grep "pathly-run" pyproject.toml && echo EXISTS || echo "OK - not present"
ls src/pathly_orchestrator/runner.py 2>/dev/null && echo EXISTS || echo "OK - not present"
```

Expected: first two print `OK`; last two print `OK - not present`.

---

## Conversation 1 — Runner skeleton + FSM loop (no Claude yet)

**Stories:** S1 (partial), S6, S7

### Files

| File | Action | Change |
|---|---|---|
| `src/pathly_orchestrator/runner.py` | CREATE | Core loop without Claude invocation |
| `pyproject.toml` | EDIT | Add `pathly-run` entry point |

### `runner.py` — what to implement

Module docstring:
```python
"""pathly-run — autonomous FSM runner. Entry point: main()."""
```

**`run_flow(flow: str, topic: str, project_root: str, rigor: str = "standard", model: str = "claude-sonnet-4-6") -> int`**

1. Import `_next_action`, `_complete_stage` from `pathly_orchestrator.mcp_server`.
2. Print `── pathly-run ──  flow={flow}  topic={topic}  project_root={project_root}`.
3. Call `_next_action(flow, topic, project_root)`.
4. If response has `"blocked"`: call `handle_blocked(response)`, return 1.
5. If response has `"current_state"`: print `── [{current_state}] agent: {agent} ──`.
6. Call `invoke_agent(response["instructions"], project_root, model)` — stub in Conv 1: print `  [stub] agent instructions loaded ({len(instructions)} chars)`.
7. Call `_complete_stage(flow, topic, project_root)`.
8. If `"done"`: print `✓ Complete`, return 0.
9. If `"next_state"`: print `✓ {prev_state} → {next_state}`, loop back to step 3.
10. If `"decide"`: call `handle_decide(flow, topic, project_root, response)` (stub: picks default, logs), loop.
11. On `RuntimeError`: print error, return 1.

**`invoke_agent(instructions: str, project_root: str, model: str) -> None`** — Conv 1 stub only:
```python
print(f"  [stub] agent instructions loaded ({len(instructions)} chars)")
```

**`handle_blocked(response: dict) -> None`**:
- If `target_agent == "human"`: print `\n⚠  Human checkpoint:\n{response.get("instructions", "")}\nFile: {response["file"]}`.
- Else: print `⚠ Blocked on {response["file"]} → routed to {response["target_agent"]}`.

**`handle_decide(flow, topic, project_root, response) -> dict`**:
- Print `\n? {response["question"]}`.
- Print each option as `  [{key}] {value}`.
- Read `input("Choice (default: {default}): ").strip()`.
- If empty or not a valid key: use `response["default"]`.
- Return `_complete_stage(flow, topic, project_root, decision=chosen)`.

**`main()`**:
```python
import argparse
parser = argparse.ArgumentParser(description="Autonomous pathly FSM runner")
parser.add_argument("topic")
parser.add_argument("--flow", default="team")
parser.add_argument("--rigor", default="standard", choices=["lite", "standard", "strict"])
parser.add_argument("--model", default="claude-sonnet-4-6")
parser.add_argument("--project-root", default=None)
args = parser.parse_args()
project_root = args.project_root or str(Path.cwd())
sys.exit(run_flow(args.flow, args.topic, project_root, args.rigor, args.model))
```

### `pyproject.toml` addition

After the `pathly-validate-flow` entry in `[project.scripts]`:
```toml
pathly-run = "pathly_orchestrator.runner:main"
```

### Verify after Conv 1

```bash
python -c "from pathly_orchestrator.runner import run_flow, main; print('OK')"
grep "pathly-run" pyproject.toml
# With an existing topic in a real project:
pathly-run <any-topic> --flow team  # should print header + stub message, no crash
```

---

## Conversation 2 — Claude subprocess integration

**Stories:** S1 (complete), S2

### Files

| File | Change |
|---|---|
| `src/pathly_orchestrator/runner.py` | Replace `invoke_agent` stub with real subprocess call |

### Replace `invoke_agent` stub with

```python
def invoke_agent(
    instructions: str,
    project_root: str,
    model: str,
    state: str = "",
    topic: str = "",
    timeout: int = 600,
) -> None:
    prompt = (
        f"You are running pathly stage {state!r} for topic {topic!r}.\n\n"
        f"{instructions}"
    )
    cmd = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    try:
        return_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Claude subprocess timed out after {timeout}s")
    if return_code != 0:
        raise RuntimeError(f"Claude subprocess exited with code {return_code}")
```

Also:
- Pass `state` (the `current_state` from `_next_action`) and `topic` through from `run_flow` when calling `invoke_agent`.
- Add `--timeout` flag to `main()` (default 600, type int); pass it to `invoke_agent`.

### Verify after Conv 2

```bash
which claude
python -c "from pathly_orchestrator.runner import invoke_agent; print('OK')"
# End-to-end (requires a real project with a topic):
pathly-run <topic> --flow team
# Expect: stage header printed, Claude runs, transition printed, next stage begins
```

---

## Conversation 3 — Human checkpoints + feedback loop

**Stories:** S4, S5

### Files

| File | Change |
|---|---|
| `src/pathly_orchestrator/runner.py` | Add `resolve_stage`; wire into `run_flow`; add `_storage_path` helper |

### Add `_storage_path(flow: dict, topic: str) -> str` helper

Loads the flow YAML at `src/pathly_data/core/flows/{flow}.flow.yaml`, returns `flow["storage_path"].format(topic=topic)`.

### Add `resolve_stage(flow, topic, project_root, model, state, topic_name) -> dict`

Replace the single `_complete_stage` call in `run_flow` with a call to `resolve_stage`. This function handles all blocking variants and returns only when a non-blocked, non-feedback result is available.

```python
def resolve_stage(flow, topic, project_root, model, state, topic_name) -> dict:
    resolved: list[str] = []
    feedback_rounds = 0
    MAX_FEEDBACK_ROUNDS = 3

    while True:
        result = _complete_stage(flow, topic, project_root,
                                 resolved_files=resolved or None)
        resolved = []

        if result.get("done") or result.get("next_state"):
            return result

        if result.get("decide"):
            return handle_decide(flow, topic, project_root, result)

        if result.get("blocked"):
            target = result["target_agent"]
            file = result["file"]

            if target == "human":
                print(f"\n⚠  Human checkpoint — {file}")
                print(result.get("instructions", "(see file)"))
                input("\nPress Enter when resolved: ")
                resolved = [file]
                continue

            feedback_rounds += 1
            if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                print(f"⚠  Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file}. Escalating to human.")
                storage = Path(project_root) / _storage_path(flow, topic)
                (storage / "feedback" / "HUMAN_QUESTIONS.md").write_text(
                    f"# Escalation\nFeedback file `{file}` was not resolved after {MAX_FEEDBACK_ROUNDS} attempts.\n"
                )
                input("\nPress Enter when resolved: ")
                resolved = ["HUMAN_QUESTIONS.md"]
                continue

            print(f"\n↩  Feedback: {file}  →  resolving with {target}")
            fb_instructions = result.get("instructions", f"Resolve feedback in feedback/{file}")
            invoke_agent(fb_instructions, project_root, model,
                         state=f"resolving {file}", topic=topic)
            resolved = [file]
            continue
```

### Verify after Conv 3

```bash
mkdir -p pathly/plans/<topic>/feedback
echo "Question?" > pathly/plans/<topic>/feedback/HUMAN_QUESTIONS.md
pathly-run <topic> --flow team
# Expect: runner prints the question, waits for Enter, continues
```

---

## Conversation 4 — Tests

**Stories:** none (quality gate)

### Files

| File | Change |
|---|---|
| `tests/test_runner.py` | CREATE — unit tests with mocks |

### Cases to cover

- **Happy path:** mock `_next_action` returns a state response; mock `invoke_agent` is a no-op; mock `_complete_stage` returns `{done: True}` → `run_flow` returns 0.
- **Multi-stage:** mock a sequence of `_next_action` / `_complete_stage` returns → correct transition messages are printed and the loop terminates.
- **Blocked human (non-interactive):** mock `_next_action` returns `{blocked: True, target_agent: "human", file: "HUMAN_QUESTIONS.md"}` → `handle_blocked` prints the message; `run_flow` returns 1.
- **`handle_decide` valid input:** mock `input()` to return a valid key → correct decision is passed to `_complete_stage`.
- **`handle_decide` invalid input:** mock `input()` to return garbage → `default` key is used.
- **`resolve_stage` feedback once:** mock `_complete_stage` returning `blocked` on the first call then `{done: True}` → `resolved_files` is passed correctly on the second call.
- **`resolve_stage` exceeds MAX_FEEDBACK_ROUNDS:** mock `_complete_stage` to always return `blocked` with a non-human target → after 3 rounds the escalation file is written and `input()` is called.
- **`invoke_agent` timeout:** mock `subprocess.Popen` so `proc.wait` raises `subprocess.TimeoutExpired` → `RuntimeError` is raised.

Use `unittest.mock.patch` to mock `_next_action`, `_complete_stage`, `subprocess.Popen`, and `builtins.input`.

### Verify after Conv 4

```bash
pytest tests/test_runner.py -v
pytest -q  # full suite must still pass
```

---

## Overall verify (after all 4 conversations)

```bash
python -c "from pathly_orchestrator.runner import run_flow, main; print('OK')"
grep "pathly-run" pyproject.toml
pytest tests/test_runner.py -v
pytest -q
# End-to-end (real project):
pathly-run <topic> --flow team
```
