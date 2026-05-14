# CONVERSATION_PROMPTS.md — mcp-fsm-driver

_Ready-to-paste prompts. Run each conversation to completion before starting the next._

---

## Conversation 1 — Python FSM core + MCP server + entry point

**Stories:** S1.1, S1.2, S1.3

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: mcp-fsm-driver
Conversation: 1 of 4
Stories: S1.1, S1.2, S1.3

## Goal

Create two new Python modules and register a CLI entry point:
  src/pathly_orchestrator/fsm.py       — pure-Python FSM core functions
  src/pathly_orchestrator/mcp_server.py — MCP server exposing next_action + complete_stage
  pyproject.toml                       — add pathly-fsm entry point

## Context

pathly_orchestrator already has state.py (with load_flow, get_transition_actions,
validate_flow_cli) and eventlog.py. Read both files before writing anything.

The three flow YAMLs are at:
  src/pathly_data/core/flows/team.flow.yaml
  src/pathly_data/core/flows/debug.flow.yaml
  src/pathly_data/core/flows/explore.flow.yaml

Read all three. The storage_path field in each YAML uses {topic} substitution.

## File 1 — src/pathly_orchestrator/fsm.py

Implement exactly these four functions. No others.

def recover_state(storage_path: Path, flow: dict) -> dict:
    """
    Read STATE.json from storage_path. If absent, return first state in
    flow["states"]. Return {"current_state": str, "conv": int,
    "open_feedback_files": list[str]}.
    conv comes from STATE.json["current_conversation"] (default 0 if absent).
    open_feedback_files: list of .md filenames in storage_path/feedback/ (stems only).
    Raise ValueError if STATE.json exists but "current" key is missing.
    """

def evaluate_transition_rules(flow: dict, current_state: str, storage_path: Path) -> str:
    """
    Read flow["transition_rules"][current_state] if present.
    For each entry in on_artifact (in YAML order):
      if that file exists under storage_path → return mapped state.
    If no match → return "default" value.
    If transition_rules absent for current_state → return
      flow["transitions"][current_state][0].
    Raise ValueError if transitions[current_state] is also absent or empty.
    """

def route_feedback(flow: dict, storage_path: Path) -> dict | None:
    """
    Read *.md files in storage_path/feedback/. If dir absent → return None.
    Priority order: HUMAN_QUESTIONS > ARCH_FEEDBACK > DESIGN_QUESTIONS >
      IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES
    Return {"file": filename, "target_agent": agent} for highest-priority match.
    Skip files whose stem is not in flow["feedback_routing"].
    Return None if no known files found.
    """

def run_transition_actions(
    flow: dict, prev_state: str, next_state: str,
    storage_path: Path, topic: str, conv: int
) -> None:
    """
    Look up flow["transition_actions"] for key "prev_state->next_state".
    Also check wildcard "->next_state".
    Exact key takes precedence; wildcard only if no exact match.
    For each action in YAML order:
      git_commit: subprocess.run(["git", "add", "-A"]) then
        subprocess.run(["git", "commit", "-m", action["message"]]).
        If commit output contains "nothing to commit" → no-op (not an error).
        Other non-zero exit → raise RuntimeError.
      archive_artifacts: for each .md in storage_path/feedback/, copy to
        pathly/pipeline-walkthrough/<topic>/artifacts/<STEM>_conv<conv>_attempt<M>.md
        where M is 1 + count of existing files matching that pattern.
      update_progress: mark PROGRESS.md conv row DONE (mark: conv_done) or
        all phases DONE (mark: all_phases_done).
    No-op if no key matches.
    """

Imports allowed: stdlib only + pathlib + subprocess + yaml +
pathly_orchestrator.state (for load_flow, get_transition_actions).

## File 2 — src/pathly_orchestrator/mcp_server.py

Use the MCP Python SDK (mcp package) to implement two tools.

Load flow YAMLs via importlib.resources:
  from importlib.resources import files
  yaml_text = files("pathly_data").joinpath(f"core/flows/{flow}.flow.yaml").read_text()
  flow_config = yaml.safe_load(yaml_text)

Resolve storage_path by substituting {topic} in flow_config["storage_path"]
and joining with Path.cwd().

FEEDBACK_PRIORITY = [
    "HUMAN_QUESTIONS", "ARCH_FEEDBACK", "DESIGN_QUESTIONS",
    "IMPL_QUESTIONS", "REVIEW_FAILURES", "TEST_FAILURES"
]

Tool 1 — next_action(flow: str, topic: str) -> dict:
  1. Load flow config.
  2. Create storage_path dir if absent.
  3. Call recover_state(storage_path, flow_config).
  4. Call route_feedback(flow_config, storage_path).
  5. If feedback found:
       return {"blocked": True,
               "target_agent": feedback["target_agent"],
               "instructions": f"Resolve {feedback['file']}: ..." }
  6. Else:
       current = state["current_state"]
       return {"current_state": current,
               "agent": flow_config["agent_map"][current],
               "instructions": f"You are the {flow_config['agent_map'][current]}. ...",
               "storage_path": str(storage_path)}

Tool 2 — complete_stage(flow: str, topic: str) -> dict:
  1. Load flow config.
  2. Call recover_state.
  3. Call route_feedback. If feedback found → return blocked (same as above).
  4. current = state["current_state"]
  5. next_state = evaluate_transition_rules(flow_config, current, storage_path)
  6. Write STATE.json: update "current" to next_state; update "updated_at".
  7. Append to EVENTS.jsonl: {"type": "STATE_TRANSITION", "from": current, "to": next_state}
  8. Call run_transition_actions(flow_config, current, next_state, storage_path, topic, state["conv"])
  9. If next_state == "DONE": return {"done": True}
  10. Return {"next_state": next_state,
              "agent": flow_config["agent_map"][next_state],
              "instructions": f"You are the {flow_config['agent_map'][next_state]}. ..."}

Add a main() function that starts the MCP server.
Add if __name__ == "__main__": main() at the bottom.

## File 3 — pyproject.toml

In [project.scripts], add this line after pathly-state:
  pathly-fsm = "pathly_orchestrator.mcp_server:main"

## Constraints

- Do not touch any skill .md files, agent .md files, or flow YAMLs.
- Do not touch mcp_config.py.
- fsm.py must not import the mcp package.
- mcp_server.py must not import pathly_hooks.

## Verify after completion

python -m pathly_orchestrator.mcp_server --help
grep "pathly-fsm" pyproject.toml
python -c "from pathly_orchestrator.fsm import recover_state, evaluate_transition_rules, route_feedback, run_transition_actions; print('OK')"
pytest -q
```

---

## Conversation 2 — `mcp_config.py` registration

**Stories:** S2.1

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: mcp-fsm-driver
Conversation: 2 of 4
Story: S2.1 — mcp_config.py registers pathly-fsm for Claude + Codex

## Prerequisite

Conversation 1 must be complete. Verify:
  python -c "from pathly_orchestrator.mcp_server import main; print('OK')"
  grep "pathly-fsm" pyproject.toml
Both must succeed before proceeding.

## File to edit

src/install_cli/mcp_config.py

## Read the file first

Read mcp_config.py in full. Understand the pattern used for pathly-telemetry:
- _SERVER_NAME constant
- _CLAUDE_ENTRY dict
- _CODEX_TOML_BLOCK string
- _install_claude / _uninstall_claude helpers
- _install_codex / _uninstall_codex helpers
- install_mcp_config / uninstall_mcp_config dispatch functions

## What to add

### 1. New constants (add after existing pathly-telemetry constants)

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

### 2. New helper functions

Add four helpers modelled exactly on the existing four pathly-telemetry helpers:
  _install_fsm_claude(*, dry_run: bool) -> None
  _uninstall_fsm_claude(*, dry_run: bool) -> None
  _install_fsm_codex(*, dry_run: bool) -> None
  _uninstall_fsm_codex(*, dry_run: bool) -> None

Each follows the identical logic as its telemetry counterpart, substituting
_FSM_SERVER_NAME, _FSM_CLAUDE_ENTRY, and _FSM_CODEX_TOML_BLOCK.

### 3. Update dispatch functions

In install_mcp_config(host, *, dry_run):
  After the existing telemetry call for each host, add the FSM call:
    if host == "claude":
        _install_claude(dry_run=dry_run)
        _install_fsm_claude(dry_run=dry_run)   ← add
    elif host == "codex":
        _install_codex(dry_run=dry_run)
        _install_fsm_codex(dry_run=dry_run)    ← add

In uninstall_mcp_config(host, *, dry_run):
    Same pattern.

## Constraints

- Do not change the structure of the module — only add helpers and extend the
  dispatch functions.
- Do not touch pyproject.toml, fsm.py, mcp_server.py, or any skill files.

## Verify after completion

grep "pathly-fsm" src/install_cli/mcp_config.py
grep "_FSM_SERVER_NAME\|_install_fsm" src/install_cli/mcp_config.py | wc -l
pytest tests/test_mcp_config.py -q
```

---

## Conversation 3 — Skill files + orchestrator agent update

**Stories:** S3.1, S3.2

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: mcp-fsm-driver
Conversation: 3 of 4
Stories: S3.1, S3.2

## Prerequisite

Conversation 2 must be complete. Verify:
  grep "pathly-fsm" src/install_cli/mcp_config.py
Must return at least one match.

## Overview

Update three core skill files, their adapter YAML files, and add a legacy note
to the orchestrator agent. No Python files touched.

## Files to edit

Group A — Core skill files (tool-agnostic):
  src/pathly_data/core/skills/team.md
  src/pathly_data/core/skills/debug.md
  src/pathly_data/core/skills/explore.md

Group B — Claude adapter YAML files:
  src/pathly_data/adapters/claude/_meta/team_skill.yaml
  src/pathly_data/adapters/claude/_meta/debug_skill.yaml
  src/pathly_data/adapters/claude/_meta/explore_skill.yaml

Group C — Codex adapter YAML files:
  src/pathly_data/adapters/codex/_meta/team_skill.yaml
  src/pathly_data/adapters/codex/_meta/debug_skill.yaml
  src/pathly_data/adapters/codex/_meta/explore_skill.yaml

Group D — Orchestrator agent:
  src/pathly_data/core/agents/orchestrator.md
  src/pathly_data/adapters/claude/_meta/orchestrator.yaml

## Read all files before editing

Read every file in Groups A–D before making any changes.

## Group A — Core skill file changes

For each skill file, replace any instruction that spawns the orchestrator agent
with the following MCP tool call pattern. Use the correct flow name for each:
  team.md    → flow="team"
  debug.md   → flow="debug"
  explore.md → flow="explore"

Replace the orchestrator invocation with:

---
## Runtime execution

This skill drives the pipeline via the pathly-fsm MCP server. Do not spawn
the orchestrator agent directly.

1. Call `next_action(flow="<FLOW>", topic=<TOPIC>)`.
   - Returns: `{current_state, agent, instructions, storage_path}`
   - If `blocked=true`: follow `target_agent` instructions to resolve the
     open feedback file. Then call `next_action` again.
2. Follow the returned instructions as the specified agent.
3. When stage work is complete, call `complete_stage(flow="<FLOW>", topic=<TOPIC>)`.
   - Returns: `{next_state, agent, instructions}` or `{done: true}`
   - If `blocked=true`: resolve feedback first (step 1).
4. Repeat from step 2 until `done=true`.
---

Keep all other content in each skill file unchanged.

## Group B+C — Adapter YAML file changes

The adapter YAML files currently reference `orchestrator` as the agent to spawn.
Update the `natural_language` or description field to reflect that the skill now
uses MCP tools. Do not add host-specific MCP syntax to the YAML — the MCP call
pattern is already in the core skill file.

Minimal change: update the description/natural_language value if it mentions
"spawns orchestrator" to instead say "drives pipeline via pathly-fsm MCP server".

## Group D — Orchestrator agent legacy note

Prepend this exact block to the top of orchestrator.md (before all existing content):

> **Runtime note (mcp-fsm-driver):** The primary FSM executor is now
> `pathly_orchestrator.mcp_server`. This file is the reference spec the MCP
> server implements, retained for documentation and as a manual fallback when
> the MCP server is unavailable. Do not edit this file to change FSM routing
> behavior — change `src/pathly_orchestrator/fsm.py` instead.

Add an equivalent one-line note to `orchestrator.yaml`:
  legacy_note: "Primary FSM executor is pathly_orchestrator.mcp_server. See orchestrator.md."

## Constraints

- Do not touch any Python files.
- Do not remove any existing content from skill files — only replace the
  orchestrator-spawn section.
- Do not add Claude Code slash-command syntax or Codex plugin syntax to core
  skill files — those belong in adapter _meta/ only.

## Verify after completion

grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
grep "orchestrator" src/pathly_data/core/skills/team.md   # must return nothing
grep "next_action\|complete_stage" src/pathly_data/core/skills/debug.md
grep "next_action\|complete_stage" src/pathly_data/core/skills/explore.md
grep "Runtime note" src/pathly_data/core/agents/orchestrator.md
```

---

## Conversation 4 — Tests

**Stories:** S4.1

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: mcp-fsm-driver
Conversation: 4 of 4
Story: S4.1 — Tests for FSM core and MCP server

## Prerequisite

Conversations 1–3 must be complete. Verify:
  python -c "from pathly_orchestrator.fsm import recover_state; print('OK')"
  grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
Both must succeed.

## Files to create

tests/test_fsm.py
tests/test_mcp_server.py

## Read before writing

Read these files before writing tests:
  src/pathly_orchestrator/fsm.py
  src/pathly_orchestrator/mcp_server.py
  src/pathly_data/core/flows/team.flow.yaml
  tests/conftest.py
  tests/test_orchestrator.py  (for style and fixture patterns)

## tests/test_fsm.py — cases to implement

Use tmp_path fixture for all filesystem interactions.
Load team.flow.yaml for all tests using:
  from importlib.resources import files
  import yaml
  TEAM_FLOW = yaml.safe_load(
      files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text()
  )

Cases:
  test_recover_state_absent_json
    - tmp_path has no STATE.json
    - recover_state returns current_state == TEAM_FLOW["states"][0]
    - conv == 0, open_feedback_files == []

  test_recover_state_present_json
    - write STATE.json: {"current": "BUILDING", "current_conversation": 2}
    - recover_state returns current_state == "BUILDING", conv == 2

  test_recover_state_corrupt_json
    - write STATE.json: {"updated_at": "2026-01-01"}  (missing "current")
    - recover_state raises ValueError

  test_evaluate_transition_rules_artifact_match
    - Write IMPLEMENTATION_PLAN.md in tmp_path
    - evaluate_transition_rules(TEAM_FLOW, "PLANNING", tmp_path) == "BUILDING"

  test_evaluate_transition_rules_no_match
    - No artifact files
    - evaluate_transition_rules(TEAM_FLOW, "PLANNING", tmp_path) == "PLANNING"
      (default value from transition_rules)

  test_evaluate_transition_rules_no_rules_entry
    - Use a minimal flow dict with no transition_rules key
    - Falls back to transitions[current_state][0]

  test_route_feedback_empty_dir
    - tmp_path/feedback/ does not exist
    - route_feedback returns None

  test_route_feedback_single_file
    - Write tmp_path/feedback/REVIEW_FAILURES.md
    - route_feedback returns {"file": "REVIEW_FAILURES.md", "target_agent": "builder"}

  test_route_feedback_priority
    - Write both tmp_path/feedback/REVIEW_FAILURES.md and
      tmp_path/feedback/HUMAN_QUESTIONS.md
    - route_feedback returns HUMAN_QUESTIONS entry (higher priority)

## tests/test_mcp_server.py — cases to implement

Import tool functions directly (not via MCP protocol):
  from pathly_orchestrator.mcp_server import next_action, complete_stage

Use monkeypatch to override Path.cwd() to return tmp_path for storage path
resolution.

Cases:
  test_next_action_no_state
    - No STATE.json in tmp_path
    - next_action("team", "test-topic") returns dict with
      current_state == TEAM_FLOW["states"][0]
    - "agent" key is present and non-empty

  test_next_action_feedback_blocked
    - Write tmp_path/.../feedback/REVIEW_FAILURES.md
      (path = team flow storage_path with topic="test-topic")
    - next_action("team", "test-topic") returns {"blocked": True}
    - "target_agent" == "builder"

  test_complete_stage_advances_state
    - Set up storage_path with STATE.json {"current": "PLANNING", ...}
    - Write IMPLEMENTATION_PLAN.md in storage_path
    - complete_stage("team", "test-topic") returns dict with next_state == "BUILDING"
    - STATE.json updated to {"current": "BUILDING"}
    - EVENTS.jsonl contains a STATE_TRANSITION entry

  test_complete_stage_blocked_by_feedback
    - Set up STATE.json {"current": "BUILDING"}
    - Write storage_path/feedback/REVIEW_FAILURES.md
    - complete_stage("team", "test-topic") returns {"blocked": True}
    - STATE.json NOT changed

  test_next_action_unknown_flow
    - next_action("nonexistent", "test-topic") returns dict with "error" key
    - Does not raise an unhandled exception

## Constraints

- Do not edit fsm.py or mcp_server.py.
- Use tmp_path for all filesystem writes.
- Tests must be independent — no shared mutable state between test functions.

## Verify after completion

pytest tests/test_fsm.py tests/test_mcp_server.py -v
pytest -q
```
