# IMPLEMENTATION_PLAN.md — mcp-fsm-driver

_Rigor: standard — 4 conversations._

---

## Pre-flight baseline (run before Conversation 1)

```bash
# Confirm prior features are done
grep "_REQUIRED_FLOW_KEYS" src/pathly_orchestrator/state.py
grep "validate_flow_cli" src/pathly_orchestrator/state.py
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml

# Confirm new files don't exist yet
ls src/pathly_orchestrator/fsm.py 2>/dev/null && echo EXISTS || echo "OK - not present"
ls src/pathly_orchestrator/mcp_server.py 2>/dev/null && echo EXISTS || echo "OK - not present"

# Confirm entry point not yet registered
grep "pathly-fsm" pyproject.toml 2>/dev/null && echo EXISTS || echo "OK - not present"
```

Expected: first three return matches; last three return "OK - not present".

---

## Conversation 1 — Python FSM core + MCP server + entry point

**Stories delivered:** S1.1, S1.2, S1.3

**Scope:** Create `fsm.py` with four pure-Python FSM functions and `mcp_server.py`
with two MCP tools. Add `pathly-fsm` entry point to `pyproject.toml`. No skill
files touched; no `mcp_config.py` touched.

**Natural seam:** After this conversation the MCP server exists and can be
started. Nothing registers it yet — no behavior change to existing installs.
Codebase is runnable. `pytest -q` must still pass.

### Files to create/edit

| File | Action | Change |
|------|--------|--------|
| `src/pathly_orchestrator/fsm.py` | CREATE | Four FSM core functions (see below) |
| `src/pathly_orchestrator/mcp_server.py` | CREATE | `next_action` + `complete_stage` MCP tools |
| `pyproject.toml` | EDIT | Add `pathly-fsm` entry point |

### `fsm.py` — what to implement

Four functions with exactly these signatures:

```python
def recover_state(storage_path: Path, flow: dict) -> dict:
    """
    Read STATE.json and EVENTS.jsonl from storage_path.
    Return {"current_state": str, "conv": int, "open_feedback_files": list[str]}.
    If STATE.json absent: current_state = first entry in flow["states"].
    open_feedback_files: list of .md filenames in storage_path/feedback/ (stems only).
    """

def evaluate_transition_rules(flow: dict, current_state: str, storage_path: Path) -> str:
    """
    Read flow["transition_rules"][current_state].
    Check each on_artifact key: if that file exists under storage_path, return mapped state.
    If no artifact matches, return the "default" value.
    If transition_rules absent for current_state: return first entry in
    flow["transitions"][current_state].
    """

def route_feedback(flow: dict, storage_path: Path) -> dict | None:
    """
    Read *.md files in storage_path/feedback/.
    Apply priority order from flow["feedback_routing"]:
      HUMAN_QUESTIONS > ARCH_FEEDBACK > DESIGN_QUESTIONS >
      IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES
    Return {"file": filename, "target_agent": agent_name} for highest-priority match.
    Return None if feedback/ is empty or does not exist.
    """

def run_transition_actions(
    flow: dict, prev_state: str, next_state: str,
    storage_path: Path, topic: str, conv: int
) -> None:
    """
    Read flow["transition_actions"].
    Look up key "prev_state->next_state"; also check "->next_state" wildcard.
    For each matched action in YAML order:
      git_commit: subprocess git add -A + git commit -m <message>
      archive_artifacts: copy feedback/*.md to
        pathly/pipeline-walkthrough/<topic>/artifacts/<NAME>_conv<conv>_attempt<M>.md
      update_progress: edit PROGRESS.md — mark conv row DONE (mark: conv_done)
        or all phases DONE (mark: all_phases_done)
    No-op if no key matches.
    On action failure: raise RuntimeError with description.
    """
```

Import only: stdlib, `pathlib`, `subprocess`, `yaml`, `pathly_orchestrator.state`.

**Also extend `state.py`:** add agent-contract validation to `validate_flow_cli`.
For every value in `flow["agent_map"]`, check that
`files("pathly_data").joinpath(f"core/agents/{agent}.md")` exists. If any are
missing, raise `ValueError` listing all missing contracts. This catches `agent_map`
typos at install time rather than at runtime inside `build_prompt`.

### `mcp_server.py` — what to implement

- Use the MCP Python SDK (or equivalent) to define and serve two tools.
- Both tools take `flow`, `topic`, and **`project_root`** as parameters.
  `project_root` is the absolute path to the user's project directory. The caller
  (skill file) passes it explicitly — the server never calls `Path.cwd()`.
- Load flow YAML via `importlib.resources`:
  ```python
  from importlib.resources import files
  yaml_text = files("pathly_data").joinpath(f"core/flows/{flow}.flow.yaml").read_text()
  flow_config = yaml.safe_load(yaml_text)
  ```
- Resolve `storage_path` from `flow_config["storage_path"]` with `{topic}` substituted,
  joined to `Path(project_root)`. Example:
  ```python
  template = flow_config["storage_path"]          # e.g. "pathly/plans/{topic}/"
  storage_path = Path(project_root) / template.format(topic=topic)
  ```
- `git` subprocess calls in `run_transition_actions` must use `cwd=project_root` so
  commits land in the correct repo.
- `main()` function that starts the MCP server (called by `pathly-fsm` entry point
  and by `python -m pathly_orchestrator.mcp_server`).
- **`route_feedback` must distinguish human feedback**: if the file is
  `HUMAN_QUESTIONS.md`, return `{file, target_agent: "human", instructions: <file contents>}`.
  The MCP server propagates this without calling `build_prompt`. `build_prompt` is
  never called when `target_agent == "human"`.
- **`complete_stage` concurrent-write guard**: read `STATE.json` once before
  `run_transition_actions` and once after. If the `current` field differs between
  reads, raise `RuntimeError("STATE.json modified externally during transition")`.
  This catches sub-agents that bypass `complete_stage` and write state directly.

### `build_prompt` — what to implement

`build_prompt` is a private helper in `mcp_server.py`. It constructs the
instructions string returned in every tool response.

```python
def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
    """
    1. Look up agent name: agent = flow_config["agent_map"][state_name]
    2. Load core/agents/<agent>.md via importlib.resources:
         agent_text = files("pathly_data").joinpath(f"core/agents/{agent}.md").read_text()
    3. Append a context block:
         f"## Current task\n"
         f"Feature: {storage_path.name}\n"
         f"State: {state_name}\n"
         f"Storage path: {storage_path}\n"
    4. Return the combined string.
    """
```

This ensures the LLM receives the full agent contract plus the minimal context it
needs. The skill file does not need to load or pass agent content separately.

### `pyproject.toml` — what to add

In `[project.scripts]`, add after the existing `pathly-state` line:

```toml
pathly-fsm = "pathly_orchestrator.mcp_server:main"
```

### Verify after Conv 1

```bash
python -m pathly_orchestrator.mcp_server --help
grep "pathly-fsm" pyproject.toml
python -c "from pathly_orchestrator.fsm import recover_state, evaluate_transition_rules, route_feedback, run_transition_actions; print('OK')"
pytest -q  # must still pass
```

---

## Conversation 2 — `mcp_config.py` registration

**Stories delivered:** S2.1

**Scope:** Add `pathly-fsm` MCP server registration to `mcp_config.py` following
the exact same pattern as `pathly-telemetry`. Both `install_mcp_config` and
`uninstall_mcp_config` updated for both hosts.

**Natural seam:** After this conversation, `pathly-setup --apply` registers the
server in both host config files. Existing installs unaffected until they re-run
`pathly-setup --apply`.

### Files to edit

| File | Change |
|------|--------|
| `src/install_cli/mcp_config.py` | Add `pathly-fsm` constants + install/uninstall logic for Claude + Codex |

### Shape of change

Add two constants at the top of the module (after the existing `pathly-telemetry`
constants):

```python
_FSM_SERVER_NAME = "pathly-fsm"

_FSM_CLAUDE_ENTRY: dict = {
    "command": "python",
    "args": ["-m", "pathly_orchestrator.mcp_server"],
}

_FSM_CODEX_TOML_BLOCK = (
    f"\n[mcp_servers.{_FSM_SERVER_NAME}]\n"
    'command = "python"\n'
    'args = ["-m", "pathly_orchestrator.mcp_server"]\n'
)
```

Extend `install_mcp_config` and `uninstall_mcp_config` to call the new
`_install_fsm_claude`, `_install_fsm_codex` etc. helpers — modelled exactly on
the existing `pathly-telemetry` helpers. No structural change to the module.

### Verify after Conv 2

```bash
grep "pathly-fsm" src/install_cli/mcp_config.py
grep "_FSM_SERVER_NAME\|pathly-fsm" src/install_cli/mcp_config.py | wc -l  # expect >= 4
pytest tests/test_mcp_config.py -q  # must still pass
```

---

## Conversation 3 — Skill files + orchestrator agent update

**Stories delivered:** S3.1, S3.2

**Scope:** Update the three core skill files (team/debug/explore) to call MCP
tools instead of spawning the orchestrator agent. Update adapter `_meta` YAML
files for Claude and Codex. Add legacy note to orchestrator.md.

**Natural seam:** After this conversation the full integration is wired. Users
who have run `pathly-setup --apply` (which installed the MCP server from Conv 2)
get deterministic FSM routing. Users who have not yet re-run setup continue using
the prior orchestrator agent — the adapter files are only deployed on next
`pathly-setup --apply`.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/team.md` | Replace orchestrator spawn with MCP tool calls |
| `src/pathly_data/core/skills/debug.md` | Same |
| `src/pathly_data/core/skills/explore.md` | Same |
| `src/pathly_data/adapters/claude/_meta/team_skill.yaml` | Update to MCP invocation |
| `src/pathly_data/adapters/claude/_meta/debug_skill.yaml` | Same |
| `src/pathly_data/adapters/claude/_meta/explore_skill.yaml` | Same |
| `src/pathly_data/adapters/codex/_meta/team_skill.yaml` | Update to MCP invocation |
| `src/pathly_data/adapters/codex/_meta/debug_skill.yaml` | Same |
| `src/pathly_data/adapters/codex/_meta/explore_skill.yaml` | Same |
| `src/pathly_data/core/agents/orchestrator.md` | Add legacy/reference header note |
| `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` | Add equivalent note |

### Core skill change — `team.md` shape

Replace any `spawn orchestrator` or `Agent(subagent_type="orchestrator", ...)` 
instructions with:

```
1. Call next_action(flow="team", topic=<TOPIC>)
   - Receives: {current_state, agent, instructions, storage_path}
   - If {blocked: true}: follow target_agent instructions to resolve feedback,
     then call next_action again.
2. Execute the instructions for the returned agent.
3. When stage work is complete, call complete_stage(flow="team", topic=<TOPIC>)
   - Receives: {next_state, agent, instructions} or {done: true}
   - If {blocked: true}: resolve feedback first (see step 1).
4. Repeat from step 2 until done=true.
```

Apply equivalent changes to `debug.md` (`flow="debug"`) and `explore.md`
(`flow="explore"`).

### Orchestrator agent note — what to prepend to `orchestrator.md`

```markdown
> **Runtime note (mcp-fsm-driver):** The primary FSM executor is now
> `pathly_orchestrator.mcp_server`. This file is the reference spec the MCP
> server implements, retained for documentation and as a manual fallback when
> the MCP server is unavailable. Do not edit this file to change FSM routing
> behavior — change `fsm.py` instead.
```

### Verify after Conv 3

```bash
grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
grep "orchestrator" src/pathly_data/core/skills/team.md   # must return nothing
grep "next_action\|complete_stage" src/pathly_data/core/skills/debug.md
grep "next_action\|complete_stage" src/pathly_data/core/skills/explore.md
grep "Runtime note" src/pathly_data/core/agents/orchestrator.md
```

---

## Conversation 4 — Tests

**Stories delivered:** S4.1

**Scope:** Write unit tests for `fsm.py` and integration tests for `mcp_server.py`
tool functions. No new Python modules. No skill file changes.

**Natural seam:** Pure test addition. Does not change any behavior.

### Files to create

| File | Change |
|------|--------|
| `tests/test_fsm.py` | Unit tests for all four `fsm.py` functions |
| `tests/test_mcp_server.py` | Integration tests for `next_action` + `complete_stage` |

### `test_fsm.py` — cases to cover

Using `team.flow.yaml` loaded via `importlib.resources`:

- `recover_state`: absent STATE.json → returns `states[0]` from flow; present
  STATE.json → returns its `current` value; `open_feedback_files` list reflects
  files in `feedback/` dir.
- `evaluate_transition_rules`: artifact file present → mapped next state;
  artifact absent → `default`; no `transition_rules` entry → `transitions[0]`.
- `route_feedback`: empty feedback dir → None; single file → correct agent;
  two files of different priority → highest priority wins; HUMAN_QUESTIONS
  always wins regardless of discovery order.

Use `tmp_path` fixture for all filesystem interactions.

### `test_mcp_server.py` — cases to cover

Call the tool functions directly (not via MCP protocol):

- `next_action("team", "test-topic")` with no prior state → returns
  `current_state == first flow state` and `agent` matches `agent_map`.
- `complete_stage("team", "test-topic")` after writing `IMPLEMENTATION_PLAN.md`
  → returns `next_state == "BUILDING"`.
- `complete_stage` with `REVIEW_FAILURES.md` in `feedback/` → returns
  `blocked=True, target_agent="builder"`.

Use `tmp_path` + monkeypatching to override `Path.cwd()` for storage path
resolution.

### Verify after Conv 4

```bash
pytest tests/test_fsm.py tests/test_mcp_server.py -v
pytest -q  # full suite must still pass
```

---

## Overall verify (run after all four conversations complete)

```bash
python -m pathly_orchestrator.mcp_server --help
grep "pathly-fsm" pyproject.toml
grep "pathly-fsm" src/install_cli/mcp_config.py
grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
grep "orchestrator" src/pathly_data/core/skills/team.md   # must return nothing
grep "Runtime note" src/pathly_data/core/agents/orchestrator.md
pytest -q
```

All checks must pass. `pytest -q` must show zero failures.
