# USER_STORIES.md — mcp-fsm-driver

_Story IDs match FEATURE_INDEX.md conv map._

---

## Story S1.1 — Python FSM core module (`fsm.py`)

**As a** Pathly maintainer,
**I want** a `src/pathly_orchestrator/fsm.py` module with pure Python functions
for all FSM operations,
**so that** the MCP server has a deterministic, testable engine to call with no
LLM involvement.

**Delivered by:** Conversation 1

### Acceptance criteria

- `recover_state(storage_path: Path, flow: dict) -> dict` — reads `STATE.json`
  and `EVENTS.jsonl`; returns `{current_state, conv, open_feedback_files}`. If
  STATE.json is absent returns the first state in `flow["states"]`.
- `evaluate_transition_rules(flow: dict, current_state: str, storage_path: Path) -> str`
  — checks `on_artifact` entries in `transition_rules[current_state]`; returns
  `default` if no artifact matches; returns first match otherwise.
- `route_feedback(flow: dict, storage_path: Path) -> dict | None` — reads
  `feedback/` directory; returns `{file, target_agent}` for the highest-priority
  open feedback file per `feedback_routing`; returns `None` when no files exist.
  Priority order follows `protocol_contract.yaml`.
- `run_transition_actions(flow: dict, prev_state: str, next_state: str,
  storage_path: Path, topic: str, conv: int)` — reads `transition_actions` from
  flow, executes matched actions in YAML order (git_commit → Python subprocess;
  archive_artifacts → Python file copy; update_progress → PROGRESS.md edit).
- All four functions are pure Python; none spawns an LLM or network call.
- `fsm.py` imports only stdlib, `pathlib`, `yaml`, and `pathly_orchestrator.state`.

---

## Story S1.2 — MCP server with `next_action` and `complete_stage`

**As a** skill author,
**I want** two MCP tools exposed by `pathly_orchestrator.mcp_server`,
**so that** skill files can call Python-deterministic FSM routing instead of
spawning the orchestrator LLM agent.

**Delivered by:** Conversation 1

### Acceptance criteria

- `next_action(flow: str, topic: str, project_root: str) -> dict` — resolves
  `flow` to `src/pathly_data/core/flows/<flow>.flow.yaml`; resolves
  `storage_path` as `Path(project_root) / template.format(topic=topic)`; calls
  `recover_state` and `route_feedback`; returns
  `{current_state, agent, instructions, storage_path}`.
  If feedback is open, returns `{blocked: true, target_agent, instructions}`.
- `complete_stage(flow: str, topic: str, project_root: str) -> dict` — same
  `project_root` → `storage_path` resolution; checks feedback first; if open
  returns `{blocked: true, ...}`; otherwise calls `evaluate_transition_rules`,
  writes `STATE.json`, appends to `EVENTS.jsonl`, calls
  `run_transition_actions` with `cwd=project_root` for any git calls, returns
  `{next_state, agent, instructions}` or `{done: true}` when state is DONE.
- The `instructions` field in every response is produced by `build_prompt`:
  loads `core/agents/<agent>.md` via `importlib.resources` and appends a
  context block with feature name, state, and storage path.
- Both tools are registered with the MCP server framework and visible to MCP
  clients.
- `python -m pathly_orchestrator.mcp_server` starts the server without error.
- The server reads flow YAMLs and agent contracts from the installed package
  data via `importlib.resources` (not repo-relative paths).
- The server never calls `Path.cwd()`.

---

## Story S1.3 — `pathly-fsm` entry point in pyproject.toml

**As a** user running `pathly-setup --apply`,
**I want** a `pathly-fsm` CLI entry point registered in `pyproject.toml`,
**so that** `mcp_config.py` can reference it as the MCP server command.

**Delivered by:** Conversation 1

### Acceptance criteria

- `pyproject.toml` contains `pathly-fsm = "pathly_orchestrator.mcp_server:main"`.
- `python -m build` produces a wheel where `pathly-fsm` is a valid entry point.
- Running `pathly-fsm` from an installed wheel starts the MCP server.

---

## Story S2.1 — `mcp_config.py` registers `pathly-fsm` for Claude and Codex

**As a** user running `pathly-setup --apply`,
**I want** the `pathly-fsm` MCP server automatically registered in both Claude
Code and Codex config,
**so that** both hosts expose `next_action` and `complete_stage` to LLM agents
without any manual configuration.

**Delivered by:** Conversation 2

### Acceptance criteria

- `pathly-setup claude --apply` adds a `pathly-fsm` entry to
  `~/.claude/settings.json` `mcpServers` with
  `{"command": "python", "args": ["-m", "pathly_orchestrator.mcp_server"]}`.
- `pathly-setup codex --apply` adds a `[mcp_servers.pathly-fsm]` section to
  `~/.codex/config.toml`.
- `pathly-setup --uninstall` removes both entries cleanly.
- `pathly-setup --dry-run` shows the planned `pathly-fsm` registration alongside
  the existing `pathly-telemetry` entry.
- Registration follows the same pattern as `pathly-telemetry` in `mcp_config.py`.

---

## Story S3.1 — Core skill files call MCP tools instead of spawning orchestrator

**As an** LLM agent executing a Pathly workflow,
**I want** the team/debug/explore skill files to call `next_action` and
`complete_stage` MCP tools rather than spawning the orchestrator agent,
**so that** all FSM routing is handled deterministically by Python with no
possibility of LLM drift.

**Delivered by:** Conversation 3

### Acceptance criteria

- `src/pathly_data/core/skills/team.md` calls the FSM `next_action` tool at
  session start and `complete_stage` after each stage completes, using generic
  pseudo-syntax (not host-specific MCP call syntax).
- `src/pathly_data/core/skills/debug.md` uses `flow="debug"` equivalently.
- `src/pathly_data/core/skills/explore.md` uses `flow="explore"` equivalently.
- Each skill loop handles the `NEEDS_CONTEXT` cycle internally:
  - When the active agent emits `NEEDS_CONTEXT`, the skill calls `scout-path`.
  - `scout-path` spawns multiple scouts in parallel and returns a summary.
  - The summary is fed back to the agent; execution resumes.
  - This cycle repeats until the agent no longer emits `NEEDS_CONTEXT`.
  - `complete_stage` is only called after the agent fully completes its work —
    the FSM never sees `NEEDS_CONTEXT` events.
- Skill loop enforces limits read from the tool response (`limits` field):
  - `needs_context_count` reaches `limits.needs_context_per_stage` → warn user, halt.
  - `feedback_round_count` reaches `limits.feedback_rounds_per_stage` → escalate
    to human (write `HUMAN_QUESTIONS.md`), surface to user.
  - Limits are defined in the flow YAML (top-level or per-state); defaults apply
    when absent. Skills never hardcode limit values.
- No skill file spawns the `orchestrator` agent directly.
- Adapter `_meta/*.yaml` files for Claude and Codex updated to expand generic
  FSM tool calls into host-specific MCP syntax.
- Skills remain tool-agnostic in `core/`; only adapter files carry host-specific
  MCP tool call syntax.

---

## Story S3.2 — Orchestrator agent marked as reference/legacy

**As a** Pathly contributor,
**I want** `orchestrator.md` and `orchestrator.yaml` updated with a clear note
that the MCP server is now the primary FSM runtime,
**so that** no one mistakes the orchestrator agent for the active execution path.

**Delivered by:** Conversation 3

### Acceptance criteria

- `src/pathly_data/core/agents/orchestrator.md` contains a header note:
  `> **Runtime note:** As of mcp-fsm-driver, the primary FSM executor is
  > \`pathly_orchestrator.mcp_server\`. This file is the reference spec the MCP
  > server implements, kept for documentation and fallback use.`
- `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` updated with
  equivalent note.
- The orchestrator agent is not removed — it remains as a fallback if the MCP
  server is unavailable.

---

## Story S4.1 — Unit and integration tests for FSM core and MCP server

**As a** developer,
**I want** automated tests for `fsm.py` and `mcp_server.py`,
**so that** regressions in the deterministic FSM engine are caught before they
reach users.

**Delivered by:** Conversation 4

### Acceptance criteria

- `tests/test_fsm.py` covers:
  - `recover_state`: absent STATE.json returns first flow state; present
    STATE.json returns its `current` value.
  - `evaluate_transition_rules`: artifact present → mapped state; no artifact →
    default.
  - `route_feedback`: no files → None; one file → correct target agent; multiple
    files → highest-priority file wins.
- `tests/test_mcp_server.py` covers:
  - `next_action` with no prior state returns first-state instructions.
  - `complete_stage` with a valid artifact advances state and returns next
    instructions.
  - `complete_stage` with an open feedback file returns `blocked: true`.
- Tests use `team.flow.yaml` from the installed package data.
- `pytest -q` passes with no failures or errors.
