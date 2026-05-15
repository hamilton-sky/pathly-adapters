# EDGE_CASES.md — mcp-fsm-driver

---

## FSM core (`fsm.py`)

**STATE.json absent on first run**
`recover_state` returns `current_state = flow["states"][0]` (first state in
the YAML list). EVENTS.jsonl need not exist. `conv = 0`, `open_feedback_files = []`.

**STATE.json present but `current` field missing or invalid**
`recover_state` treats this as corrupt state. Raises `ValueError` with the path
and field. Does not silently default — a corrupt state file must surface to the
user.

**`transition_rules` absent for current state**
`evaluate_transition_rules` falls back to `flow["transitions"][current_state][0]`
(the first valid transition). If `transitions[current_state]` is also absent or
empty, raises `ValueError` — this indicates a broken flow YAML.

**`feedback/` directory does not exist**
`route_feedback` returns `None`. Does not raise. The directory is optional.

**Multiple feedback files present**
`route_feedback` returns only the highest-priority file per the fixed priority
list. The caller must resolve one file at a time. After resolution the caller
calls `route_feedback` again to check for remaining files.

**Feedback file present with unknown stem (not in `feedback_routing`)**
`route_feedback` skips unknown files and continues scanning for known ones. If
only unknown files exist, returns `None`. Unknown files do not block the pipeline.

**`run_transition_actions` — git commit fails (e.g. nothing to commit)**
If `git commit` exits with "nothing to commit", treat as a no-op — do not raise.
All other non-zero exit codes from git raise `RuntimeError`.

**`run_transition_actions` — no matching key in `transition_actions`**
No-op. Does not raise. Wildcard `->NEXT_STATE` checked after exact key.

**`run_transition_actions` — `transition_actions` key absent from flow YAML**
No-op. `get_transition_actions(flow)` returns `{}`.

---

## MCP server (`mcp_server.py`)

**`project_root` is a relative path or does not exist**
Both tools resolve `storage_path` as `Path(project_root) / ...`. If
`project_root` is relative or points to a non-existent directory, every
path operation will silently resolve to the wrong location. Validate at
call time: if `Path(project_root)` is not an absolute path or does not
exist as a directory, return `{"error": "project_root must be an absolute
path to an existing directory: <value>"}`.

**Agent contract file missing from package data**
`build_prompt` loads `core/agents/<agent>.md` via `importlib.resources`. If
the agent name in `agent_map` does not match any installed `.md` file, this
raises a `FileNotFoundError`. Catch it and return
`{"error": "agent contract not found: <agent>"}` rather than crashing the
MCP server.

**Unknown `flow` parameter**
`next_action("nonexistent", topic)` — flow YAML not found in package data.
Returns `{"error": "flow YAML not found: nonexistent.flow.yaml"}`. Does not
raise an unhandled exception to the MCP client.

**`storage_path` does not exist yet**
Both `next_action` and `complete_stage` create the storage directory (and
`feedback/` subdirectory) on first call. This matches current orchestrator
behavior.

**`complete_stage` called when already at DONE**
Returns `{"done": True}` immediately. Does not write another STATE_TRANSITION
event or re-run transition_actions.

**`next_action` called with open feedback**
Returns `{"blocked": True, target_agent, instructions}`. Does not advance state.
Caller must resolve feedback and call `next_action` again.

**`complete_stage` called with open feedback**
Same as `next_action` — returns blocked. Feedback resolution always takes
priority over stage advancement.

**Concurrent calls to `complete_stage` for the same topic**
Not supported. The MCP server processes one request at a time per topic. If two
calls arrive simultaneously the second will read the STATE.json written by the
first and likely return `{done: true}` or an unexpected next state. This matches
current orchestrator behavior (single active agent constraint).

---

## `mcp_config.py` registration

**`pathly-fsm` already registered**
`install_mcp_config` is idempotent — if the entry already exists, it is a no-op.
Same behavior as `pathly-telemetry`.

**`pathly-fsm` entry missing from `~/.claude/settings.json` during uninstall**
`uninstall_mcp_config` is a no-op if the entry is not found. Does not raise.

**Codex config TOML has a stale `pathly-fsm` section from a failed install**
`install_mcp_config` for Codex checks for the section header string before
adding. If it finds it, skips. Does not duplicate.

---

## Skill file behavior

**Agent emits NEEDS_CONTEXT repeatedly without making progress**
The skill loop calls `scout-path` each time an agent emits `NEEDS_CONTEXT`, but
without a cap an agent that never stops asking for context will loop indefinitely.
Solution: the skill reads `limits.needs_context_per_stage` from the tool response
(resolved by `recover_state` from flow YAML, default 3). When the counter reaches
the limit the skill surfaces a warning to the user and halts. The limit can be
raised or lowered per-flow or per-state in the YAML:
```yaml
limits:
  needs_context_per_stage: 5   # flow-wide default
states:
  BUILDING:
    limits:
      needs_context_per_stage: 2  # tighter cap for builder
```

**Feedback blocks a stage more times than expected**
If a stage is repeatedly blocked by feedback (e.g. reviewer keeps finding new
failures), the skill reads `limits.feedback_rounds_per_stage` from the tool
response (default 2). When reached, the skill escalates by writing
`HUMAN_QUESTIONS.md` regardless of the original feedback type, and surfaces it
to the user. Configurable in YAML the same way as `needs_context_per_stage`.

**`limits` key absent from flow YAML**
`recover_state` applies module defaults:
`{needs_context_per_stage: 3, feedback_rounds_per_stage: 2}`.
No error raised — missing limits key is valid.

**Per-state `limits` partially overrides top-level**
If a state defines only `needs_context_per_stage`, the other keys still fall
through to the top-level `limits` (or defaults). Keys are merged individually,
not replaced wholesale.

**scout-path returns no useful summary**
`scout-path` may return an empty or trivially short summary (e.g. if the
codebase has no matching files for the agent's query). The skill feeds whatever
`scout-path` returns back to the agent unchanged — it does not validate the
summary. If the agent then emits `NEEDS_CONTEXT` again, the normal cycle counter
applies.

**MCP server not running when skill calls `next_action`**
The MCP call fails. The error surfaces to the LLM as a tool error. The skill
should instruct the LLM to fall back to spawning the orchestrator agent manually
and display a warning: `pathly-fsm MCP server not available — run
pathly-setup --apply and restart your AI tool.`

**`next_action` called for a topic already at DONE**
Returns `{done: true}`. The skill treats this as a completed pipeline and shows
a summary to the user.

**`complete_stage` called multiple times for the same completed stage**
Each call reads current STATE.json. If state has already advanced (e.g. builder
calls `complete_stage` twice), the second call evaluates `transition_rules` from
the already-advanced state and may advance again or return `{done: true}`. This
is a usage error — skills should call `complete_stage` exactly once per stage.
Document this constraint in `mcp_server.py` docstrings.

---

## Architectural edge cases (disingenuous patterns)

**Sub-agent writes STATE.json directly, bypassing `complete_stage`**
Nothing prevents a domain agent (planner, builder, reviewer) from writing
`STATE.json` directly instead of calling `complete_stage`. If it does, the MCP
server reads the modified state on the next call and advances from the wrong
point — silently.
Solution: Document in every agent contract that writing `STATE.json` is
forbidden; agents must call `complete_stage`. Additionally, `complete_stage`
reads `STATE.json` before and after `run_transition_actions` and raises
`RuntimeError` if the state changed between the two reads (concurrent write
detected).

**`agent_map` values are implicit unvalidated file paths**
Flow YAMLs map states to agent names (e.g. `PLANNING: planner`), but
`validate_flow_cli` does not verify that `core/agents/<agent>.md` exists in
the installed package. A typo in `agent_map` reaches `build_prompt` at runtime
and raises `FileNotFoundError`.
Solution: Extend `validate_flow_cli` (in `state.py`) to check every value in
`agent_map` against the list of `.md` files in `core/agents/` via
`importlib.resources`. Report all missing agent contracts as validation errors,
not runtime failures.

**`BLOCKED_ON_HUMAN` state has no agent contract**
`next_action` or `complete_stage` returning `{blocked: true}` means a feedback
file is present. The `target_agent` field names the agent that should resolve
the feedback (e.g. `"builder"`). But if the feedback file is `HUMAN_QUESTIONS.md`
the correct target is the *user*, not an LLM agent — there is no
`core/agents/human.md`. Calling `build_prompt` or `build_prompt_for_agent` here
would raise `FileNotFoundError`.
Solution: `route_feedback` returns `{file, target_agent: "human", instructions: <file contents>}`
for `HUMAN_QUESTIONS` priority files. The MCP server returns `instructions`
verbatim — neither `build_prompt` nor `build_prompt_for_agent` is called.
Skill files surface the instructions to the user and halt until the file is
deleted.

**`build_prompt` receives an agent name instead of a state name**
`build_prompt(flow_config, state_name, storage_path)` resolves the agent via
`agent_map[state_name]`. When feedback is open, `feedback["target_agent"]` is
already an agent name — passing it as `state_name` causes a `KeyError` because
agent names are not keys in `agent_map`.
Solution: use `build_prompt_for_agent(flow_config, agent_name, storage_path)` for
all blocked-feedback responses (non-human). This helper loads the agent `.md`
directly without an `agent_map` lookup.

**`orchestrator.md` (fallback) will drift from `fsm.py` (primary)**
Over time, `fsm.py` will handle new edge cases, support new action types, or
change transition evaluation logic. `orchestrator.md` will not be updated in
parallel. When someone falls back to the orchestrator agent they get different
— and likely incorrect — FSM behavior.
Solution: Add a comment block at the top of `orchestrator.md` listing the exact
`fsm.py` version and behavioral invariants it was synchronized with. Treat
orchestrator.md as a snapshot, not a living document. CI check: if `fsm.py`
changes and `orchestrator.md` has not been touched in the same PR, emit a
warning (not a failure). Long-term: remove the fallback path after two stable
releases and rely on MCP server availability checks in skill files.

---

## Test cases derived from edge cases

| Edge case | Test in |
|-----------|---------|
| Absent STATE.json → first state returned | `test_fsm.py::test_recover_state_absent` |
| Corrupt STATE.json → ValueError raised | `test_fsm.py::test_recover_state_corrupt` |
| No transition_rules entry → transitions fallback | `test_fsm.py::test_evaluate_fallback` |
| Empty feedback dir → None | `test_fsm.py::test_route_feedback_empty` |
| Two feedback files → priority winner | `test_fsm.py::test_route_feedback_priority` |
| git commit nothing-to-commit → no-op | `test_fsm.py::test_run_actions_empty_commit` |
| git_commit action → correct cwd + args | `test_fsm.py::test_run_actions_git_commit` |
| archive_artifacts → files copied with attempt counter | `test_fsm.py::test_run_actions_archive_artifacts` |
| update_progress → PROGRESS.md row marked DONE | `test_fsm.py::test_run_actions_update_progress` |
| write_state → STATE.json correct + prior fields preserved | `test_fsm.py::test_write_state` |
| append_event → EVENTS.jsonl gains one line with ts | `test_fsm.py::test_append_event` |
| Unknown flow name → error dict | `test_mcp_server.py::test_next_action_bad_flow` |
| Relative project_root → error dict | `test_mcp_server.py::test_next_action_relative_project_root` |
| Missing agent contract → error dict | `test_mcp_server.py::test_build_prompt_missing_agent` |
| Feedback present → blocked response | `test_mcp_server.py::test_complete_stage_blocked` |
| Already DONE → done response | `test_mcp_server.py::test_complete_stage_already_done` |
| HUMAN_QUESTIONS feedback → human target, no build_prompt | `test_mcp_server.py::test_route_feedback_human_questions` |
| Non-human feedback blocked → build_prompt_for_agent used | `test_mcp_server.py::test_complete_stage_blocked_nonhuman` |
| Concurrent STATE.json write → RuntimeError | `test_mcp_server.py::test_complete_stage_concurrent_write` |
| agent_map typo → validation error at validate_flow_cli | `test_fsm.py::test_validate_flow_missing_agent_contract` |
| limits absent from YAML → defaults applied | `test_fsm.py::test_recover_state_limits_defaults` |
| per-state limits override top-level partially | `test_fsm.py::test_recover_state_limits_per_state_merge` |
| limits returned in next_action response | `test_mcp_server.py::test_next_action_returns_limits` |
