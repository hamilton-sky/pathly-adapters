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

## Test cases derived from edge cases

| Edge case | Test in |
|-----------|---------|
| Absent STATE.json → first state returned | `test_fsm.py::test_recover_state_absent` |
| Corrupt STATE.json → ValueError raised | `test_fsm.py::test_recover_state_corrupt` |
| No transition_rules entry → transitions fallback | `test_fsm.py::test_evaluate_fallback` |
| Empty feedback dir → None | `test_fsm.py::test_route_feedback_empty` |
| Two feedback files → priority winner | `test_fsm.py::test_route_feedback_priority` |
| git commit nothing-to-commit → no-op | `test_fsm.py::test_run_actions_empty_commit` |
| Unknown flow name → error dict | `test_mcp_server.py::test_next_action_bad_flow` |
| Feedback present → blocked response | `test_mcp_server.py::test_complete_stage_blocked` |
| Already DONE → done response | `test_mcp_server.py::test_complete_stage_already_done` |
