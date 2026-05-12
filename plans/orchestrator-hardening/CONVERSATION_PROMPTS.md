# orchestrator-hardening — Conversation Guide

Split into 4 conversations (at the cap). Each produces a runnable, testable codebase.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Ship orchestrator and hooks as real packages (Phases 1.1 – 1.4)

**Stories delivered:** S1, S4

**Prompt to paste:**
```
Read plans/orchestrator-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-hardening Conversation 1 (Phases 1.1 – 1.4) from
plans/orchestrator-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path the plan lists exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

Codebase files this conversation touches:
- `orchestrator/__init__.py`, `orchestrator/state.py`, `orchestrator/events.py`, `orchestrator/eventlog.py` — move into `src/pathly_orchestrator/` and delete the repo-root copies
- `hooks/classify_feedback.py`, `hooks/inject_feedback_ttl.py` — move into `src/pathly_hooks/` and delete the repo-root copies
- `pyproject.toml` — add `pathly_orchestrator*` and `pathly_hooks*` to `packages.find.include`; add `pathly-events` and `pathly-state` console scripts
- `tests/test_hooks.py` — update import paths to `pathly_hooks.*`
- `README.md` — add `pathly-events` and `pathly-state` to the "All commands" section
- `CHANGELOG.md` — add a new top entry describing the move and console scripts

Scope:
- Phase 1.1: move `orchestrator/` → `src/pathly_orchestrator/`
- Phase 1.2: move `hooks/` → `src/pathly_hooks/`
- Phase 1.3: wire pyproject.toml (packages.find + console scripts); refactor `eventlog.py`'s `__main__` block into a `_cli()` function the console script can import; add a tiny `_state_cli()` for `pathly-state`
- Phase 1.4: document the new console scripts in README and CHANGELOG

Architectural rules to observe:
- Move files, do not copy. Two sources of truth re-create the drift this plan is closing.
- Preserve exact content of each Python module on move; rename imports only.
- Do not modify any logic in `eventlog.py` beyond extracting `_cli()` — concurrency and validation are Conv 2's job.
- Do not touch `protocol_contract.yaml`, schemas, or the `classify_feedback` heuristic — those are Conv 2 and 3.

Do NOT touch `src/pathly_data/core/`, `src/install_cli/`, `src/pathly_telemetry/`, or any docs other than README.md and CHANGELOG.md.

Verify: `pytest && pip install -e ".[dev]" && pathly-events summary nonexistent-feature && pathly-state nonexistent-feature`

After done, update plans/orchestrator-hardening/PROGRESS.md phases 1.1 – 1.4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `orchestrator/` and `hooks/` directories no longer exist at the repo root; `src/pathly_orchestrator/` and `src/pathly_hooks/` exist and are importable; `pathly-events` and `pathly-state` work after editable install; README and CHANGELOG mention them.
**Files touched:** `src/pathly_orchestrator/*`, `src/pathly_hooks/*`, `pyproject.toml`, `tests/test_hooks.py`, `README.md`, `CHANGELOG.md`

---

## Conversation 2: FSM hardening — STATE.json schema + EVENTS.jsonl concurrency (Phases 2.1 – 2.3)

**Stories delivered:** S2, S3

**Prompt to paste:**
```
Read plans/orchestrator-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-hardening Conversation 2 (Phases 2.1 – 2.3) from
plans/orchestrator-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** confirm Conversation 1 has landed — `src/pathly_orchestrator/` must exist and be importable. If it does not, stop and report.

Codebase files this conversation touches:
- `schemas/state.schema.json` — CREATE: enum of state names, transition table, full property schema
- `src/pathly_orchestrator/state.py` — add `VALID_STATES`, `TRANSITIONS` exported constants
- `src/pathly_orchestrator/eventlog.py` — validate state in `write_state`; validate `STATE_TRANSITION` events in `append_event`; wrap append with file lock
- `tests/test_orchestrator.py` — CREATE: tests for schema validation, illegal transition, concurrent append

Scope:
- Phase 2.1: create the JSON Schema with the 13 state names from `state.py` and an allowed-transitions table
- Phase 2.2: enforce the schema at write time in `eventlog.write_state`; enforce transition validity in `append_event` when the event is a STATE_TRANSITION
- Phase 2.3: add `fcntl.flock` (POSIX) / `msvcrt.locking` (Windows) around the file write in `append_event`; add a stress test that spawns 10 threads appending 50 events each and asserts 500 valid JSON lines round-trip

Architectural rules to observe:
- Use `jsonschema` (already an indirect dep via tests) to validate against the file in `schemas/`. Do not duplicate the enum in Python — either load the schema at import or generate constants from it.
- Keep `write_state` and `append_event` signatures unchanged; raise `ValueError` on validation failure.
- The file lock must be held only for the write itself; release before returning. Readers are not locked.
- Verify the test does not flake — run the concurrent-append test 5 times locally before claiming PASS.

Do NOT touch hooks, protocol_contract.yaml, docs, README, or any skill markdown.
Do NOT modify `current_conversation` semantics — that is Conv 4.

Verify: `pytest tests/test_orchestrator.py -v && pytest`

After done, update plans/orchestrator-hardening/PROGRESS.md phases 2.1 – 2.3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** New `schemas/state.schema.json` with state enum and transition table; `eventlog.py` raises on invalid state and illegal transition; `append_event` is concurrency-safe; `tests/test_orchestrator.py` covers all three.
**Files touched:** `schemas/state.schema.json`, `src/pathly_orchestrator/state.py`, `src/pathly_orchestrator/eventlog.py`, `tests/test_orchestrator.py`

---

## Conversation 3: Contract integrity — classify hook + protocol version (Phases 3.1 – 3.2)

**Stories delivered:** S5, S6

**Prompt to paste:**
```
Read plans/orchestrator-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-hardening Conversation 3 (Phases 3.1 – 3.2) from
plans/orchestrator-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** confirm `src/pathly_hooks/classify_feedback.py` exists (Conv 1 landed). If not, stop and report.

Codebase files this conversation touches:
- `src/pathly_hooks/classify_feedback.py` — tighten the heuristic: drop the `"how"` keyword, use word-boundary regex, gate the heuristic off entirely when `ANTHROPIC_API_KEY` is set
- `tests/test_hooks.py` — add classification edge-case tests
- `protocol_contract.yaml` — add `version: 1` near the top
- `src/pathly_hooks/__init__.py` — add `PROTOCOL_VERSION = 1`
- `tests/test_feedback_protocol.py` — assert yaml version matches Python constant
- `CHANGELOG.md` — document the version bump procedure

Scope:
- Phase 3.1: heuristic fix. Keywords to keep: `architect`, `design`, `approach`, `structure`. Add: `layer`, `boundary`. Drop: `how`. Use `re.search(r"\b<kw>\b", line, re.IGNORECASE)`. Tests must cover: "How long does this take?" → `[REQ]`, "What design approach handles retries?" → `[ARCH]`, "Where is the boundary?" → `[ARCH]`, "Player needs to login" → `[REQ]` (word-boundary check).
- Phase 3.2: protocol version. Add `version: 1` field; expose `PROTOCOL_VERSION` constant; test asserts equality; CHANGELOG describes the bump procedure ("edit yaml, bump constant, mirror both files to pathly-engine").

Architectural rules to observe:
- The hook's existing `PATHLY_PROJECT_ROOT` guard and path-traversal check at `resolved.is_relative_to(plans_dir)` MUST be preserved exactly.
- Do not introduce a network call in the heuristic path. If `ANTHROPIC_API_KEY` is unset, the heuristic is the only path.
- Do not touch any state-machine code or schemas.

Do NOT touch `src/pathly_orchestrator/`, `schemas/`, `src/pathly_data/`, `src/install_cli/`, or README beyond what's required.

Verify: `pytest tests/test_hooks.py tests/test_feedback_protocol.py -v && pytest`

After done, update plans/orchestrator-hardening/PROGRESS.md phases 3.1 – 3.2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `classify_feedback.py` no longer triggers on the word "how"; word-boundary tests pass; `protocol_contract.yaml` carries `version: 1`; runtime assertion catches yaml-vs-constant desync.
**Files touched:** `src/pathly_hooks/classify_feedback.py`, `src/pathly_hooks/__init__.py`, `tests/test_hooks.py`, `tests/test_feedback_protocol.py`, `protocol_contract.yaml`, `CHANGELOG.md`

---

## Conversation 4: Cross-host hook parity docs + per-stage iteration (Phases 4.1 – 4.2)

**Stories delivered:** S7, S8

**Prompt to paste:**
```
Read plans/orchestrator-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-hardening Conversation 4 (Phases 4.1 – 4.2) from
plans/orchestrator-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** confirm `schemas/state.schema.json` exists from Conv 2. If not, stop and report.

Codebase files this conversation touches:
- `docs/SECURITY.md` — add a "Hook surface coverage" subsection listing per-host status
- `README.md` — add a Known Limitations bullet linking to the SECURITY.md subsection
- `schemas/state.schema.json` — add optional `iteration_by_stage` map
- `src/pathly_orchestrator/state.py` — extend the docstring to describe the new optional field
- `src/pathly_data/core/skills/team-flow.md` — reference the new field at the section that talks about retry counts

Scope:
- Phase 4.1: hook parity documentation. SECURITY.md subsection must enumerate claude (supported via Claude Code hook event system), codex (not supported), copilot (not supported), and describe the parity path (per-host `_meta/<name>_hook.yaml` overlay).
- Phase 4.2: schema extension. `iteration_by_stage: {type: object, additionalProperties: {type: integer, minimum: 0}}` as optional. Back-compat: existing STATE.json files without the field must still validate. Existing `current_conversation` field stays.

Architectural rules to observe:
- This is a docs + schema-extension conversation. Do not change behavior in any installer or runtime module.
- Re-validate every existing STATE.json file in `plans/` after the schema change; none may break.
- team-flow.md is a canonical skill — keep it host-neutral, do not introduce Claude-specific terminology.

Do NOT touch hooks, orchestrator Python code, protocol_contract.yaml, or any test file other than test_orchestrator.py (to add the back-compat assertion).

Verify: `pytest && python -c "import json, glob; from jsonschema import validate; schema=json.load(open('schemas/state.schema.json')); [validate(json.load(open(f)), schema) for f in glob.glob('plans/*/STATE.json')]"`

After done, update plans/orchestrator-hardening/PROGRESS.md phases 4.1 – 4.2 to DONE; flip top-level Status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** SECURITY.md documents hook parity gap; README links to it; STATE.json schema accepts an optional `iteration_by_stage` map without breaking existing files; team-flow.md references the new field.
**Files touched:** `docs/SECURITY.md`, `README.md`, `schemas/state.schema.json`, `src/pathly_orchestrator/state.py`, `src/pathly_data/core/skills/team-flow.md`, `tests/test_orchestrator.py`

---

## Conversation 5: Deploy hooks to Codex and Copilot VS Code (Phases 5.1 – 5.3)

**Stories delivered:** S9, S7 (completion)

**Prompt to paste:**
```
Read plans/orchestrator-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement orchestrator-hardening Conversation 5 (Phases 5.1 – 5.3) from
plans/orchestrator-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** confirm Conv 4 has landed — `docs/SECURITY.md` must exist with a Hook surface coverage section. Also confirm `src/pathly_hooks/inject_feedback_ttl.py` and `src/pathly_hooks/classify_feedback.py` exist (Conv 1). If either is missing, stop and report.

Codebase files this conversation touches:
- `src/install_cli/materialize.py` — add hook file deployment for Codex and Copilot VS Code hosts
- `src/pathly_data/adapters/codex/install.yaml` — update hook event name from `post_tool_call` → `PostToolUse`; add `matcher: {tool_name: apply_patch}`
- `src/pathly_data/adapters/copilot/install.yaml` — update hook event name to `PostToolUse`; add platform-keyed command format
- `tests/test_materialize_hooks.py` — CREATE: tests asserting hook files are written and removed correctly for each host
- `docs/SECURITY.md` — Phase 5.3: update the hook coverage table to show "deployed by pathly-setup" for Codex and Copilot VS Code

Scope:
- Phase 5.1: Codex hook deployment. `pathly-setup codex --apply` writes `~/.codex/hooks.json` with two PostToolUse entries. If the file exists and contains other hooks, merge Pathly's entries under a `"pathly"` namespace key rather than overwriting. `--uninstall` removes Pathly's entries without touching user hooks. Print a one-line note if `[features] codex_hooks = true` is absent from `~/.codex/config.toml`.
- Phase 5.2: Copilot VS Code hook deployment. `pathly-setup copilot --apply` writes `.github/hooks/pathly-classify.json` and `.github/hooks/pathly-ttl.json` in the project root (current working directory). Each file has `{"event": "PostToolUse", "command": {"windows": "...", "linux": "...", "osx": "..."}}`. Script path is the absolute installed package path from `importlib.resources`. `--uninstall` deletes both files.
- Phase 5.3: Update `docs/SECURITY.md` hook coverage table — add a "Deployed by installer" column showing ✅ for Claude, Codex, Copilot VS Code and ❌ for Copilot CLI.

Architectural rules to observe:
- Do NOT overwrite user hooks. Codex merge must be safe under repeated `--apply` runs (idempotent).
- Script paths in Copilot hook files must resolve correctly from an installed wheel, not just a source checkout — use `importlib.resources` or the absolute path of the installed `pathly_hooks` package.
- Do not change hook script logic — `classify_feedback.py` and `inject_feedback_ttl.py` already read JSON from stdin and work cross-host.
- Do not touch `src/pathly_data/adapters/claude/install.yaml` — Claude's hook event name stays `post_tool_call`.

Do NOT touch `src/pathly_orchestrator/`, `schemas/`, `protocol_contract.yaml`, or any skill markdown.

Verify: `pytest tests/test_materialize_hooks.py -v && pytest && pathly-setup codex --dry-run && pathly-setup copilot --dry-run`

After done, update plans/orchestrator-hardening/PROGRESS.md phases 5.1 – 5.3 to DONE; flip top-level Status to COMPLETE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `pathly-setup codex --apply` writes `~/.codex/hooks.json` with Pathly entries merged safely; `pathly-setup copilot --apply` writes two hook files under `.github/hooks/`; both `--uninstall` clean up; SECURITY.md table shows deployed status.
**Files touched:** `src/install_cli/materialize.py`, `src/pathly_data/adapters/codex/install.yaml`, `src/pathly_data/adapters/copilot/install.yaml`, `tests/test_materialize_hooks.py`, `docs/SECURITY.md`
