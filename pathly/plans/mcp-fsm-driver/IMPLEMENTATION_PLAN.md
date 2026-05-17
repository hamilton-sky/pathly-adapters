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

**Scope:** Create `fsm.py` with six pure-Python FSM functions and `mcp_server.py`
with two MCP tools plus `resolve_decide`. Add `pathly-fsm` entry point to
`pyproject.toml`. No skill files touched; no `mcp_config.py` touched.

**Natural seam:** After this conversation the MCP server exists and can be
started. Nothing registers it yet — no behavior change to existing installs.
Codebase is runnable. `pytest -q` must still pass.

### Files to create/edit

| File | Action | Change |
|------|--------|--------|
| `src/pathly_orchestrator/fsm.py` | CREATE | Six FSM core functions (see below) |
| `src/pathly_orchestrator/mcp_server.py` | CREATE | `next_action` + `complete_stage` MCP tools |
| `pyproject.toml` | EDIT | Add `pathly-fsm` entry point |

### `fsm.py` — what to implement

Six functions with exactly these signatures:

```python
def recover_state(storage_path: Path, flow: dict) -> dict:
    """
    Read STATE.json and EVENTS.jsonl from storage_path.
    Return {"current_state": str, "conv": int, "open_feedback_files": list[str],
            "limits": dict}.
    If STATE.json absent: current_state = first entry in flow["states"].
    open_feedback_files: list of .md filenames in storage_path/feedback/ (stems only).
    limits: resolved from flow["states"][current_state]["limits"] if present,
            falling back to flow["limits"], falling back to module defaults
            {needs_context_per_stage: 3, feedback_rounds_per_stage: 2}.
    Per-state limits override top-level limits key by key (not wholesale replace).
    """

def evaluate_transition_rules(
    flow: dict, current_state: str, storage_path: Path
) -> str | dict:
    """
    Evaluate routing rules for current_state in strict level order.
    Stop and return at the first match.

    Level 1 — on_artifact (list):
      For each entry: if storage_path / entry["file"] exists → return entry["next"].

    Level 2 — on_content (list):
      For each entry: read storage_path / entry["file"] (skip if missing).
        If entry["contains"] is a substring of file contents → return entry["next"].
        If entry["regex"] is set, use re.search instead of substring check.

    Level 3 — decide (dict):
      Do NOT call LLM here. Return the decide dict as a sentinel:
        {"decide": True, "context_file": str, "question": str,
         "options": dict[str, str], "default": str}
      mcp_server.py detects this sentinel and calls resolve_decide().
      fsm.py never imports or calls any LLM SDK.

    Fallback — default (str):
      Return flow["transition_rules"][current_state]["default"] if present.
      Else return flow["transitions"][current_state][0].
      If neither exists: raise ValueError.
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
        <M> = count of existing files in that dir matching <NAME>_conv<conv>_attempt*.md + 1
      update_progress: edit PROGRESS.md — mark conv row DONE (mark: conv_done)
        or all phases DONE (mark: all_phases_done)
    No-op if no key matches.
    On action failure: raise RuntimeError with description.
    """

def write_state(storage_path: Path, next_state: str, prior_state: dict) -> None:
    """
    Write STATE.json atomically (write to .tmp then rename).
    Preserve all fields from prior_state; overwrite "current" with next_state.
    Create storage_path if it does not exist.
    """

def append_event(storage_path: Path, event: dict) -> None:
    """
    Append a single JSON line to EVENTS.jsonl.
    Inject "ts": datetime.utcnow().isoformat() into event before writing.
    Create the file if absent.
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
- Both tools include a `limits` field in every non-error response, taken from
  `recover_state`'s resolved limits dict. The skill reads these values to enforce
  `NEEDS_CONTEXT` and feedback-round caps without hardcoding them.
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

### `build_prompt` and `build_prompt_for_agent` — what to implement

Two private helpers in `mcp_server.py`. They construct the instructions string
returned in every tool response.

```python
def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
    """
    Used for normal (non-blocked) responses where state_name is a key in agent_map.
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

def build_prompt_for_agent(flow_config: dict, agent_name: str, storage_path: Path) -> str:
    """
    Used for blocked responses where the agent name is already known directly
    (e.g. from feedback_routing), not via agent_map lookup.
    1. Load core/agents/<agent_name>.md via importlib.resources.
    2. Append the same context block as build_prompt.
    3. Return the combined string.
    """
```

**Key distinction:** `build_prompt` takes a *state name* and resolves it through
`agent_map`. `build_prompt_for_agent` takes an *agent name* directly. Never pass
a `feedback["target_agent"]` value (an agent name) to `build_prompt` — it will
`KeyError` because agent names are not keys in `agent_map`.

### `resolve_decide` — what to implement

`complete_stage` detects the Level 3 sentinel and returns it to the **calling
LLM** (Claude or Codex) as a structured response. No external API or Anthropic
SDK is involved — the same LLM that is running the skill makes the decision.

#### `complete_stage` signature change

Add an optional `decision` parameter:

```python
@mcp_tool
def complete_stage(flow: str, topic: str, project_root: str,
                   decision: str | None = None) -> dict:
```

#### Level 3 flow (two-call protocol)

**Call 1** — `complete_stage(flow, topic, project_root)` — no `decision`:
1. L1 and L2 evaluate as normal.
2. If `evaluate_transition_rules` returns a `{"decide": True, ...}` sentinel:
   a. Read `decide_config["context_file"]` from `storage_path`.
      If file missing: skip to fallback (see below).
   b. Return immediately — do NOT write STATE.json, do NOT run actions:
      ```json
      {
        "decide": true,
        "question": "<decide_config.question>",
        "context": "<file contents>",
        "options": {"key1": "STATE_A", "key2": "STATE_B"},
        "default": "<decide_config.default>"
      }
      ```
3. The skill surfaces `question` + `context` to the calling LLM and asks it to
   reply with exactly one option key.

**Call 2** — `complete_stage(flow, topic, project_root, decision="<key>")`:
1. Recover state (same as always).
2. Evaluate transition rules again (L1/L2 may now resolve differently — check
   first; only use `decision` if the result is still a decide sentinel).
3. If still a decide sentinel: validate `decision` is a key in `options`.
   - Valid: `next_state = options[decision]`.
   - Invalid or missing: `next_state = decide_config["default"]`.
4. Append event:
   ```json
   {"type": "DECIDE_ROUTING", "chosen": "<next_state>",
    "decision_input": "<decision>", "options": {...}}
   ```
5. Continue normally: `write_state`, `append_event STATE_TRANSITION`,
   `run_transition_actions`, return `{next_state, agent, instructions}`.

**Failure mode:** if `context_file` is missing on Call 1, return the decide
response with `"context": null` — the LLM should still be able to choose based
on the question and option labels alone, falling back to `default` if it cannot.
No exception is raised to the MCP client.

`fsm.py` is unchanged — it still returns the `{"decide": True, ...}` sentinel.
All two-call coordination logic lives in `mcp_server.py` only.

**Human feedback special case:** When `feedback["target_agent"] == "human"`,
`route_feedback` returns the file contents as `feedback["instructions"]`. The MCP
server returns those contents directly — neither `build_prompt` nor
`build_prompt_for_agent` is called.

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

**Out of scope (follow-up plan):** `start.md`, `pause.md`, `end.md`, and
`go.md` are NOT updated in this conversation. They will get the contextual menu
panel in a separate plan after this one ships and is validated.

**Menu spec:** The builder must read
`pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md` before touching any skill
file. That document is the authoritative format reference — border style,
pipeline progress bar, Panel A/B for decide, blocked-state option swap.

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

Core skill files use **generic pseudo-syntax** — no host-specific MCP call
syntax. The adapter `_meta/*.yaml` files expand this for each host.

#### Contextual state menu (required)

After calling `next_action` and before executing agent instructions, the skill
**must display a contextual menu** whose content depends on the current state.
This is the primary UX surface — do not skip it.

```
─────────────────────────────────────────
Pathly · team · <TOPIC>
State: <current_state>  (conv <N>)
Agent: <agent_name>
─────────────────────────────────────────
<STATE-SPECIFIC GUIDANCE — see table below>
─────────────────────────────────────────
Options:
  [1] Proceed
  [2] Pause
  [3] Show full state (STATE.json + recent events)
  [4] Switch path (team / debug / explore)
─────────────────────────────────────────
```

State-specific guidance:

| State | Guidance line |
|-------|--------------|
| `PLANNING` | "Planner will draft IMPLEMENTATION_PLAN.md." |
| `BUILDING` | "Builder will implement. Reviewer runs after." |
| `REVIEWING` | "Reviewer checks BUILDING output. Any REVIEW_FAILURES.md blocks forward." |
| `TESTING` | "Tester validates. TEST_FAILURES.md loops back to builder." |
| `RETRO` | "Final retrospective. Completes this topic when done." |
| `DONE` | "Topic complete. Artifacts archived." |
| (any debug state) | Surface `debug.flow.yaml` agent_map description for that state. |
| (any explore state) | Surface `explore.flow.yaml` agent_map description for that state. |

If the user chooses [2] Pause, call `pause` skill and stop.  
If the user chooses [3], print STATE.json pretty-printed and the last 10 EVENTS.jsonl lines.  
If the user chooses [4], surface `/pathly team|debug|explore <TOPIC>` options.  
If the user presses Enter or chooses [1], proceed with the returned instructions.

Replace any `spawn orchestrator` or `Agent(subagent_type="orchestrator", ...)`
instructions with:

```
1. Call FSM tool: next_action(flow="team", topic=<TOPIC>, project_root=<PROJECT_ROOT>)
   - Receives: {current_state, agent, instructions, storage_path}
   - If {blocked: true, target_agent: "human"}: surface instructions to the user
     and halt until the user deletes the file manually. Then call next_action again.
   - If {blocked: true, target_agent: <agent>}: follow instructions to resolve
     feedback, **delete result.file from feedback/**, then call next_action again.

2. Execute the instructions for the returned agent.
   Track two counters, reset at the start of each stage:
   needs_context_count = 0, feedback_round_count = 0.

   - If the agent outputs NEEDS_CONTEXT:
       a. needs_context_count += 1
       b. If needs_context_count >= limits.needs_context_per_stage:
            surface warning to user: "Agent has requested context
            {N} times without completing this stage." Halt and await
            user instruction.
       c. Otherwise: call scout-path, feed summary back, resume.
       d. Repeat until agent no longer emits NEEDS_CONTEXT.
   - The FSM is not notified about NEEDS_CONTEXT cycles — they are entirely
     internal to the skill loop.

3. When stage work is complete, call FSM tool: complete_stage(flow="team", topic=<TOPIC>, project_root=<PROJECT_ROOT>)
   - Receives: {next_state, agent, instructions, limits} or {done: true}
   - If {blocked: true, target_agent: "human"}:
       Surface instructions to the user and halt. Wait for the user to
       delete the file. Then call complete_stage again.
   - If {blocked: true, target_agent: <agent>}:
       a. feedback_round_count += 1
       b. If feedback_round_count >= limits.feedback_rounds_per_stage:
            write HUMAN_QUESTIONS.md with escalation note regardless of
            original feedback type. Surface to user and halt.
       c. Otherwise:
            i.  Follow instructions to resolve feedback with <agent>.
            ii. **Delete result.file from feedback/** — the skill deletes it;
                Python never does. If not deleted, complete_stage will return
                the same file again forever.
            iii. Call complete_stage again (loop — do NOT batch-resolve
                 multiple files before calling).

   Each call to complete_stage returns at most one blocked file. Resolve
   one file, delete it, call complete_stage again. Repeat until not blocked.

4. Repeat from step 2 until done=true.
```

"FSM tool" in core means the abstract operation. Adapters map it to the concrete
host syntax (e.g. `mcp__pathly-fsm__next_action(...)` for Claude Code).

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
- `evaluate_transition_rules`:
  - L1: artifact present → mapped next state; artifact absent → falls through.
  - L2: file contains pattern → mapped next state; no match → falls through.
  - L3: no L1/L2 match → returns decide sentinel dict (not a string).
  - fallback: no rules match → returns `default` / `transitions[0]`.
  - evaluation order: L1 before L2 before L3 before fallback.
- `evaluate_transition_rules` L3: when decide sentinel returned, no external SDK
  call occurs (fsm.py is LLM-free). Sentinel is a plain dict with `decide=True`.
- `route_feedback`: empty feedback dir → None; single file → correct agent;
  two files of different priority → highest priority wins; HUMAN_QUESTIONS
  always wins regardless of discovery order.
- `run_transition_actions` — `git_commit`: mock subprocess; assert `git add -A`
  and `git commit` called with correct `cwd`; assert "nothing to commit" exit
  code treated as no-op.
- `run_transition_actions` — `archive_artifacts`: create two feedback files;
  assert both copied to pipeline-walkthrough dir with correct naming including
  attempt counter `<M>`.
- `run_transition_actions` — `update_progress`: write a PROGRESS.md with a conv
  row; assert the row is marked DONE after action.
- `write_state`: assert STATE.json written with correct `current` field and that
  prior fields are preserved.
- `append_event`: assert EVENTS.jsonl gains exactly one new JSON line with a `ts`
  field after each call.
- `recover_state` — limits resolution:
  - no `limits` key in flow → defaults `{needs_context_per_stage: 3, feedback_rounds_per_stage: 2}`
  - top-level `limits` only → used as-is
  - per-state `limits` partially defined → merged with top-level; missing keys
    fall through to top-level or defaults

Use `tmp_path` fixture for all filesystem interactions.

### `test_mcp_server.py` — cases to cover

Call the tool functions directly (not via MCP protocol):

- `next_action("team", "test-topic")` with no prior state → returns
  `current_state == first flow state` and `agent` matches `agent_map`.
- `complete_stage("team", "test-topic")` after writing `IMPLEMENTATION_PLAN.md`
  → returns `next_state == "BUILDING"`.
- `complete_stage` with `REVIEW_FAILURES.md` in `feedback/` → returns
  `blocked=True, target_agent="builder"`.

**Two-call decide protocol — three additional cases (required):**

- `test_complete_stage_returns_decide_sentinel`
  Set STATE.json to a state whose transition_rules only has a `decide` block
  (no on_artifact files present). Call `complete_stage(decision=None)`.
  Assert: returns `{decide: True, question: ..., options: dict}`.
  Assert: STATE.json unchanged. Assert: no STATE_TRANSITION in EVENTS.jsonl.

- `test_complete_stage_with_valid_decision`
  Same setup. Call `complete_stage(decision="<valid_key>")`.
  Assert: returns `{next_state: options[valid_key], agent: ..., instructions: ...}`.
  Assert: STATE.json updated. Assert: DECIDE_ROUTING + STATE_TRANSITION in EVENTS.jsonl.

- `test_complete_stage_with_invalid_decision`
  Same setup. Call `complete_stage(decision="nonsense")`.
  Assert: returns `{next_state: decide_config["default"]}`.
  Assert: no exception raised. Assert: DECIDE_ROUTING event with decision_input="nonsense".

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
