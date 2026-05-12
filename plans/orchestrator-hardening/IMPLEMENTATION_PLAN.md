# orchestrator-hardening — Implementation Plan

## Overview

Nine concrete fixes to the Pathly orchestrator and hook surfaces, grouped into
five conversations. The plan converts repo-root reference code into shipped
packages, adds a STATE.json JSON Schema with a transition table, makes
EVENTS.jsonl writes concurrency-safe, fixes a brittle classification heuristic,
versions the cross-repo protocol contract, documents the hook parity gap, and
deploys working hooks to Codex and Copilot VS Code via the installer.

## Layer Architecture

```
Plans (this file)                  →  Implementation modules                 →  Surfaces
        ↓                                            ↓                                 ↓
[9 stories, 5 conversations]        [src/pathly_orchestrator/, src/pathly_hooks/]   [pipx console scripts,
                                    [schemas/state.schema.json]                      JSON Schema for STATE.json,
                                    [protocol_contract.yaml + version]               cross-repo version check,
                                    [src/install_cli/materialize.py]                 Codex + Copilot VS Code hook files]
```

## Phases

### Phase 1.1: Move `orchestrator/` into `src/pathly_orchestrator/`   ← Conversation: 1
**File:** `src/pathly_orchestrator/{__init__.py,state.py,events.py,eventlog.py}` — CREATE by moving from `orchestrator/`; delete repo-root `orchestrator/` after move
**Done when:** `python -c "from pathly_orchestrator.eventlog import summary"` succeeds in an editable install and `orchestrator/` no longer exists at the repo root.
**Delivers stories:** S1
**Depends on:** nothing
**Enables:** Phase 1.2 (pyproject wiring), Phase 2.1 (schema imports)
**Details:**
Move all four files verbatim. Update any internal `from orchestrator.x` imports to `from pathly_orchestrator.x`. Update the docstring in `__init__.py` to reflect the new module path. `tests/test_orchestrator.py` will be added in Phase 2 — for now, just confirm `tests/` does not import from `orchestrator.*`.

### Phase 1.2: Move `hooks/` into `src/pathly_hooks/`   ← Conversation: 1
**File:** `src/pathly_hooks/{__init__.py,classify_feedback.py,inject_feedback_ttl.py}` — CREATE by moving from `hooks/`; delete repo-root `hooks/` after move
**Done when:** `python -m pathly_hooks.classify_feedback < /dev/null` runs and exits cleanly with `PATHLY_PROJECT_ROOT` unset (silent no-op path).
**Delivers stories:** S1
**Depends on:** nothing
**Enables:** Phase 1.3, Phase 3.1
**Details:**
Add a minimal `__init__.py` exposing both modules. Update `tests/test_hooks.py` to import from `pathly_hooks.classify_feedback` rather than `hooks.classify_feedback`. Preserve the existing `PATHLY_PROJECT_ROOT` guard and path-traversal check exactly.

### Phase 1.3: Wire pyproject `packages.find` and console scripts   ← Conversation: 1
**File:** `pyproject.toml` — MODIFY
**Done when:** `pipx install -e . && pathly-events summary nonexistent-feature` runs and prints "No events found …".
**Delivers stories:** S1
**Depends on:** Phase 1.1, Phase 1.2
**Enables:** Phase 1.4
**Details:**
- Add `pathly_orchestrator*` and `pathly_hooks*` to `[tool.setuptools.packages.find].include`.
- Add `pathly-events = "pathly_orchestrator.eventlog:_cli"` to `[project.scripts]`.
- Add `pathly-state = "pathly_orchestrator.eventlog:_state_cli"` (new tiny CLI that reads and prints `plans/<feature>/STATE.json`).
- Refactor `eventlog.py`'s existing `if __name__ == "__main__"` block into a `_cli()` function so the console script can import it.

### Phase 1.4: Document console scripts in README + CHANGELOG   ← Conversation: 1
**File:** `README.md`, `CHANGELOG.md` — MODIFY
**Done when:** README "All commands" section lists `pathly-events` and `pathly-state`; CHANGELOG has a new top entry describing the move and console scripts.
**Delivers stories:** S4
**Depends on:** Phase 1.3
**Enables:** nothing
**Details:**
Insert two new rows in README's all-commands block, after `pathly-setup --uninstall`. CHANGELOG entry must call out the move as non-breaking for end users (the old repo-root paths were never shipped).

### Phase 2.1: Create `schemas/state.schema.json`   ← Conversation: 2
**File:** `schemas/state.schema.json` — CREATE
**Done when:** `jsonschema -i plans/po-planner-separation/STATE.json schemas/state.schema.json` validates without error.
**Delivers stories:** S2
**Depends on:** Phase 1.1
**Enables:** Phase 2.2
**Details:**
- `properties.name`: `enum` of the 13 names in `src/pathly_orchestrator/state.py:25`.
- `properties.feature`: string, minLength 1.
- `properties.rigor`: `enum: ["lite", "standard", "strict"]`.
- `properties.current_conversation`: integer, minimum 0.
- `properties.retry_count_by_key`: object with string-keyed integer values.
- `properties.updated_at`: string, format date-time.
- `required: ["name", "feature", "rigor", "updated_at"]`.
- Plus a sibling top-level object `transitions` mapping each state to its allowed next states (e.g. `BUILDING: ["REVIEWING", "REVIEW_BLOCKED", "BLOCKED_ON_HUMAN", "DONE"]`).

### Phase 2.2: Add validator to `write_state` + tests   ← Conversation: 2
**File:** `src/pathly_orchestrator/state.py`, `src/pathly_orchestrator/eventlog.py`, `tests/test_orchestrator.py` — MODIFY/CREATE
**Done when:** `pytest tests/test_orchestrator.py -k state_validation` passes, covering valid state, invalid name, and illegal transition.
**Delivers stories:** S2
**Depends on:** Phase 2.1
**Enables:** Phase 2.3
**Details:**
- Add `VALID_STATES = frozenset(STATES.keys())` to `state.py`.
- Add `TRANSITIONS: dict[str, frozenset[str]]` to `state.py` mirroring the JSON-schema transitions block (or load it from the JSON file at import time).
- In `write_state`, before writing, assert `state["name"] in VALID_STATES`; raise `ValueError` on miss.
- When the caller writes a `STATE_TRANSITION` event via `append_event`, validate `from_state → to_state` is allowed.
- Tests assert both raises and one happy path.

### Phase 2.3: Add file lock to `append_event` + concurrency test   ← Conversation: 2
**File:** `src/pathly_orchestrator/eventlog.py`, `tests/test_orchestrator.py` — MODIFY
**Done when:** `pytest tests/test_orchestrator.py -k concurrent_append` passes — 10 threads each appending 50 events produce 500 valid JSON lines.
**Delivers stories:** S3
**Depends on:** Phase 2.2
**Enables:** nothing
**Details:**
Wrap the existing append in `fcntl.flock(f, LOCK_EX)` on POSIX. On Windows, fall back to `msvcrt.locking` or accept the existing race — gate the platform check at the top of the function. Keep the lock held only for the write itself; do not block reads. Add a `multiprocessing`-or-`threading`-based stress test.

### Phase 3.1: Tighten `classify_feedback.py` heuristic   ← Conversation: 3
**File:** `src/pathly_hooks/classify_feedback.py`, `tests/test_hooks.py` — MODIFY
**Done when:** `pytest tests/test_hooks.py -k classify` passes with cases for "How long does this take?" → `[REQ]` and "What design approach handles retries?" → `[ARCH]`.
**Delivers stories:** S5
**Depends on:** Phase 1.2
**Enables:** nothing
**Details:**
Replace the substring scan at the current line ~54 with a narrower keyword set: drop `"how"`; keep `"architect"`, `"design"`, `"approach"`, `"structure"`; add `"layer"`, `"boundary"`. Use word-boundary matching, not substring (`"approach"` should not match `"approaches"` in body text — keep, but `"layer"` should not match `"player"`). Use `re.search(r"\b<word>\b", ...)`. If `ANTHROPIC_API_KEY` is set, prefer the API path (already wired) and skip the heuristic entirely.

### Phase 3.2: Add `version` to protocol_contract.yaml + cross-check   ← Conversation: 3
**File:** `protocol_contract.yaml`, `src/pathly_hooks/__init__.py`, `tests/test_feedback_protocol.py`, `CHANGELOG.md` — MODIFY/CREATE
**Done when:** `pytest tests/test_feedback_protocol.py -k version` passes and fails loudly when the constant in `__init__.py` is desynced from the yaml.
**Delivers stories:** S6
**Depends on:** Phase 1.2
**Enables:** nothing
**Details:**
- Add `version: 1` near the top of `protocol_contract.yaml`.
- Add `PROTOCOL_VERSION = 1` to `src/pathly_hooks/__init__.py` (or a new `protocol.py` if cleaner).
- Update `tests/test_feedback_protocol.py` to read the yaml and assert version matches the Python constant.
- CHANGELOG entry: "Bump procedure: edit yaml, bump `PROTOCOL_VERSION`, mirror both to `pathly-engine`."

### Phase 4.1: Document hook parity gap   ← Conversation: 4
**File:** `docs/SECURITY.md`, `README.md` — MODIFY
**Done when:** `docs/SECURITY.md` has a "Hook surface coverage" subsection listing claude=supported, codex=supported (PostToolUse, v0.114+), copilot-vscode=supported (PostToolUse, Preview Feb 2026), copilot-cli=not-supported; README "Known Limitations" links to it.
**Delivers stories:** S7
**Depends on:** nothing
**Enables:** Phase 5.1 (implementation follows the documented spec)
**Details:**
Cite `src/pathly_hooks/classify_feedback.py` and `src/pathly_hooks/inject_feedback_ttl.py`. For Codex: hooks live in `~/.codex/hooks.json`, require `[features] codex_hooks = true`, use `PostToolUse` with a `tool_name: apply_patch` matcher. For Copilot VS Code: hooks live in `.github/hooks/*.json`, use `PostToolUse` event, platform-keyed command. Copilot CLI is the only remaining gap (no `postToolUse` event). Note Phase 5 will implement deployment for Codex and Copilot VS Code.

### Phase 4.2: Add per-stage iteration to STATE.json schema + skill docs   ← Conversation: 4
**File:** `schemas/state.schema.json`, `src/pathly_data/core/skills/team-flow.md`, `src/pathly_orchestrator/state.py` (docstring only) — MODIFY
**Done when:** schema accepts an optional `iteration_by_stage` map; team-flow.md documents when planners and reviewers should bump it; existing STATE.json files in `plans/` still validate.
**Delivers stories:** S8
**Depends on:** Phase 2.1
**Enables:** nothing
**Details:**
- Add `iteration_by_stage: {type: object, additionalProperties: {type: integer, minimum: 0}}` as optional.
- Keep `current_conversation` for back-compat; document that new callers may use either.
- In `team-flow.md`, mention the field once at the section that currently talks about retry counts.

### Phase 5.1: Deploy hook files for Codex via materialize.py   ← Conversation: 5
**File:** `src/install_cli/materialize.py`, `src/pathly_data/adapters/codex/install.yaml`, `tests/test_materialize_hooks.py` — MODIFY/CREATE
**Done when:** `pathly-setup codex --apply` writes `~/.codex/hooks.json` with two `PostToolUse` entries (one per hook script); `pathly-setup codex --uninstall` removes those entries; test asserts file is written and has correct shape.
**Delivers stories:** S9
**Depends on:** Phase 1.2 (hooks in src/), Phase 4.1 (documented spec)
**Enables:** Phase 5.2
**Details:**
- Read the `hooks:` list from `codex/install.yaml` (already declared there).
- Write `~/.codex/hooks.json` as a JSON file with the array of hook objects. If the file already exists and was written by a different tool, merge Pathly's entries under a `pathly` key rather than overwriting — avoid clobbering user hooks.
- Track the written file in the Pathly manifest so `--uninstall` can clean it up.
- `codex/install.yaml` already has `hooks:` with `event: post_tool_call` — rename the event value to `PostToolUse` to match Codex's hook system. Add a `matcher: {tool_name: apply_patch}` so hooks only fire on file writes.
- Requires `[features] codex_hooks = true` in `~/.codex/config.toml` — the installer should print a one-line note if that flag is absent, but not fail.

### Phase 5.2: Deploy hook files for Copilot VS Code via materialize.py   ← Conversation: 5
**File:** `src/install_cli/materialize.py`, `src/pathly_data/adapters/copilot/install.yaml`, `tests/test_materialize_hooks.py` — MODIFY
**Done when:** `pathly-setup copilot --apply` writes `.github/hooks/pathly-classify.json` and `.github/hooks/pathly-ttl.json` in the project root; `--uninstall` removes them; test asserts both files are written with correct `PostToolUse` event shape.
**Delivers stories:** S9
**Depends on:** Phase 5.1
**Enables:** nothing
**Details:**
- Copilot VS Code hooks live per-project in `.github/hooks/`. Write two separate JSON files, one per hook.
- Each file: `{"event": "PostToolUse", "command": {"windows": "python ...", "linux": "python ...", "osx": "python ..."}}`.
- The script path must be absolute or relative to the project root — use the installed package path via `importlib.resources`.
- Track both files in the Pathly manifest.
- `copilot/install.yaml` already has `hooks:` — update the event name to `PostToolUse` and add platform-keyed command format.

### Phase 5.3: Update Story 7 acceptance criteria + SECURITY.md follow-up   ← Conversation: 5
**File:** `docs/SECURITY.md` — MODIFY (add "Deployed via" column to the coverage table)
**Done when:** SECURITY.md hook coverage table shows "deployed by pathly-setup" for Codex and Copilot VS Code; Copilot CLI row shows "not supported — no PostToolUse event".
**Delivers stories:** S7 (completion), S9
**Depends on:** Phase 5.1, Phase 5.2
**Enables:** nothing
**Details:**
Single prose update — no code change. Update the table written in Phase 4.1 to reflect that Codex and Copilot VS Code hooks are now deployed automatically by the installer.

## Prerequisites
- Editable install (`pip install -e ".[dev]"`) works against the current main.
- `pytest` passes on current main before this work starts.
- `jsonschema` is available for Phase 2.1's done-when (add to `dev` extras if missing).

## Key Decisions

- **Move, not copy.** `orchestrator/` and `hooks/` are NOT copied into `src/` — they are *moved*. Two sources of truth would re-create exactly the drift the plan is trying to fix.
- **JSON Schema, not Pydantic.** The repo already has `schemas/pathly-meta.schema.json` and uses `jsonschema`-style validation in tests. Stay consistent rather than introducing a runtime type library.
- **Heuristic stays as a fallback.** Phase 3.1 tightens but does not delete the keyword heuristic. The API path requires `ANTHROPIC_API_KEY` which a fresh install will not have, so a non-API fallback must still produce sane output.
- **Version starts at 1, not 0.** `protocol_contract.yaml` has been used in production runs; bumping from "unversioned" to `version: 1` is more honest than starting at 0.
- **Per-stage iteration is additive.** Phase 4.2 does not remove `current_conversation`. Removing it would touch every skill markdown file that references the FSM — out of scope.
- **Hook deployment merges, not overwrites.** Phase 5.1 must not clobber existing `~/.codex/hooks.json` content. Pathly entries are namespaced or merged so user-defined hooks survive a reinstall.
- **Copilot CLI excluded from scope.** Copilot CLI has no `postToolUse` event. Pathly documents this gap but does not attempt a workaround. If the Copilot CLI team adds the event, Phase 5 can be extended.
- **PostToolUse event name normalisation.** The existing `install.yaml` files use `post_tool_call` (Claude Code's name). Phases 5.1–5.2 update the Codex and Copilot adapter yamls to use `PostToolUse` (their native name) while leaving Claude's yaml unchanged.
