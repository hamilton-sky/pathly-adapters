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

Both tools take flow, topic, and project_root (str) as parameters.
The skill file passes project_root explicitly — the server never calls Path.cwd().

Resolve storage_path like this:
  template = flow_config["storage_path"]          # e.g. "pathly/plans/{topic}/"
  storage_path = Path(project_root) / template.format(topic=topic)

All git subprocess calls must pass cwd=project_root so commits land in the
correct repo.

Implement a private build_prompt(flow_config, state_name, storage_path) helper:
  1. agent = flow_config["agent_map"][state_name]
  2. agent_text = files("pathly_data").joinpath(f"core/agents/{agent}.md").read_text()
  3. Return agent_text + "\n## Current task\n" +
       f"Feature: {storage_path.name}\nState: {state_name}\nStorage path: {storage_path}\n"
Use build_prompt() for all instructions fields — never f"You are the {agent}. ..."

Tool 1 — next_action(flow: str, topic: str, project_root: str) -> dict:
  1. Load flow config.
  2. Resolve storage_path = Path(project_root) / template.format(topic=topic).
  3. Create storage_path dir if absent.
  4. Call recover_state(storage_path, flow_config).
  5. Call route_feedback(flow_config, storage_path).
  6. If feedback found:
       return {"blocked": True,
               "target_agent": feedback["target_agent"],
               "instructions": build_prompt(flow_config, feedback["target_agent"], storage_path)}
  7. Else:
       current = state["current_state"]
       return {"current_state": current,
               "agent": flow_config["agent_map"][current],
               "instructions": build_prompt(flow_config, current, storage_path),
               "storage_path": str(storage_path)}

Tool 2 — complete_stage(flow: str, topic: str, project_root: str,
                        decision: str | None = None) -> dict:

  No external API. No Anthropic SDK. Level 3 routing is resolved by the calling
  LLM via a two-call protocol — see below.

  Call path when decision is None:
  1. Load flow config.
  2. Resolve storage_path.
  3. Call recover_state.
  4. Call route_feedback. If feedback found → return blocked (same as above).
  5. current = state["current_state"]
  6. routing = evaluate_transition_rules(flow_config, current, storage_path)
  7. If routing is a dict with {"decide": True, ...} (Level 3 sentinel):
       a. Read routing["context_file"] from storage_path. If missing: context = None.
       b. Do NOT write STATE.json. Do NOT run transition_actions.
       c. Return immediately:
            {"decide": True,
             "question": routing["question"],
             "context": context,
             "options": routing["options"],
             "default": routing["default"]}
  8. Otherwise (routing is a str): next_state = routing.
     Write STATE.json: update "current" to next_state; update "updated_at".
     Append to EVENTS.jsonl: {"type": "STATE_TRANSITION", "from": current, "to": next_state}
     Call run_transition_actions(...)
     If next_state == "DONE": return {"done": True}
     Return {"next_state": next_state,
             "agent": flow_config["agent_map"][next_state],
             "instructions": build_prompt(flow_config, next_state, storage_path)}

  Call path when decision is provided (Call 2 of the two-call protocol):
  1–4. Same as above (load, resolve, recover, route_feedback check).
  5. Re-evaluate transition rules.
  6. If result is still a decide sentinel:
       a. Validate decision is a key in routing["options"].
       b. Valid: next_state = routing["options"][decision].
       c. Invalid or None: next_state = routing["default"].
       d. Append: {"type": "DECIDE_ROUTING", "chosen": next_state,
                   "decision_input": decision, "options": routing["options"]}
  7. Continue: write STATE.json, append STATE_TRANSITION, run_transition_actions,
     return next agent response. Never raise for invalid decision — always fallback.

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

Before writing any skill file content, read:
  pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md
This is the authoritative spec for the contextual state menu — border style,
pipeline progress bar construction, Panel A/B for decide, blocked-state option
swap. Implement the menu exactly as shown there. Do not invent a different format.

## Out of scope for this conversation

Do NOT update these skill files — they are a separate follow-up plan:
  src/pathly_data/core/skills/start.md
  src/pathly_data/core/skills/pause.md
  src/pathly_data/core/skills/end.md
  src/pathly_data/core/skills/go.md (if it exists)
Only team.md, debug.md, and explore.md get the contextual menu in this plan.

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

1. Call `next_action(flow="<FLOW>", topic=<TOPIC>, project_root=<PROJECT_ROOT>)`.
   - Returns: `{current_state, agent, instructions, storage_path, limits}`
   - If `blocked=true, target_agent="human"`: surface instructions to the user
     and halt. Wait for user to delete the feedback file. Then call next_action again.
   - If `blocked=true, target_agent=<agent>`: follow instructions, delete the
     feedback file from feedback/, then call next_action again.

2. BEFORE executing agent instructions, display the contextual state menu:

   ```
   ─────────────────────────────────────────
   Pathly · <FLOW> · <TOPIC>
   State: <current_state>  (conv <N>)
   Agent: <agent>
   ─────────────────────────────────────────
   <STATE-SPECIFIC GUIDANCE LINE — see table>
   ─────────────────────────────────────────
   Options:
     [1] Proceed
     [2] Pause
     [3] Show full state (STATE.json + last 10 events)
     [4] Switch path (team / debug / explore)
   ─────────────────────────────────────────
   ```

   State-specific guidance lines:
     PLANNING  → "Planner will draft IMPLEMENTATION_PLAN.md."
     BUILDING  → "Builder will implement. Reviewer runs after."
     REVIEWING → "Reviewer checks output. REVIEW_FAILURES.md blocks forward."
     TESTING   → "Tester validates. TEST_FAILURES.md loops back to builder."
     RETRO     → "Final retrospective. Completes topic when done."
     DONE      → "Topic complete. Artifacts archived."
     (other)   → "Agent: <agent> will work on state <current_state>."

   If user chooses [2]: call the pause skill and stop.
   If user chooses [3]: print STATE.json and last 10 EVENTS.jsonl lines, then
     show the menu again.
   If user chooses [4]: surface /pathly team|debug|explore <TOPIC> and stop.
   If user presses Enter or chooses [1]: proceed with agent instructions.

3. Execute the returned instructions as the specified agent.
   Track counters reset at each stage start:
     needs_context_count = 0, feedback_round_count = 0

   - If agent outputs NEEDS_CONTEXT:
       needs_context_count += 1
       If >= limits.needs_context_per_stage: surface warning to user, halt.
       Otherwise: call scout-path, feed summary back, resume.

4. When stage work is complete, call
   `complete_stage(flow="<FLOW>", topic=<TOPIC>, project_root=<PROJECT_ROOT>)`.
   - Returns `{next_state, agent, instructions}`, `{done: true}`, or
     `{decide: true, question, context, options, default}`.
   - If `{decide: true}`: read the question and context, choose one option key,
     call `complete_stage(..., decision="<chosen_key>")`.
   - If `blocked=true, target_agent="human"`: surface, halt, wait for file delete.
   - If `blocked=true, target_agent=<agent>`:
       feedback_round_count += 1
       If >= limits.feedback_rounds_per_stage: write HUMAN_QUESTIONS.md with
         escalation note, surface to user, halt.
       Otherwise: resolve with <agent>, delete feedback file, call complete_stage
         again. One file at a time — do NOT batch.

5. Repeat from step 2 until done=true.
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

  ## Two-call decide protocol (complete_stage)

  test_complete_stage_returns_decide_sentinel
    - Set up STATE.json {"current": "REVIEWING"}
    - Configure a minimal flow dict with transition_rules for REVIEWING that
      has a decide block (no on_artifact, no on_content files present)
    - complete_stage("team", "test-topic") with no decision argument
    - Returns dict with "decide" == True, "question" non-empty, "options" is dict
    - STATE.json is NOT changed (still "REVIEWING")
    - EVENTS.jsonl does NOT contain a STATE_TRANSITION entry

  test_complete_stage_with_valid_decision
    - Same setup as above (decide sentinel would fire)
    - Call complete_stage("team", "test-topic", decision="refactor")
      where "refactor" is a key in the options dict
    - Returns dict with next_state == options["refactor"]
    - STATE.json updated to that next_state
    - EVENTS.jsonl contains DECIDE_ROUTING entry with decision_input="refactor"
    - EVENTS.jsonl contains STATE_TRANSITION entry

  test_complete_stage_with_invalid_decision
    - Same setup
    - Call complete_stage("team", "test-topic", decision="nonsense")
      where "nonsense" is NOT a key in options
    - Returns dict with next_state == decide_config["default"]
    - No exception raised
    - DECIDE_ROUTING event appended with decision_input="nonsense"

## Constraints

- Do not edit fsm.py or mcp_server.py.
- Use tmp_path for all filesystem writes.
- Tests must be independent — no shared mutable state between test functions.

## Verify after completion

pytest tests/test_fsm.py tests/test_mcp_server.py -v
pytest -q
```
