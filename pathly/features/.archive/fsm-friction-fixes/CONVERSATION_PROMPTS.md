# CONVERSATION_PROMPTS — fsm-friction-fixes

---

## Conv 1 — FSM server auto-start

**Stories delivered:** S1 (AC-S1-1 through AC-S1-6)

**Scope — files you are allowed to touch:**
- `src/pathly_orchestrator/fsm_http_client.py`
- `src/pathly_orchestrator/http_server.py`
- `src/pathly_data/core/skills/utilities/fsm-call.md`
- `tests/` (server startup tests only)

Do not touch `fsm.py`, `fsm_ops.py`, `team.flow.yaml`, or `review.md`.
Do not push to master without explicit user request.

---

### Prompt

You are implementing Conv 1 of the fsm-friction-fixes feature.

Read `pathly/plans/fsm-friction-fixes/USER_STORIES.md` S1 acceptance criteria (AC-S1-1 through AC-S1-6) before writing any code.
Read `src/pathly_orchestrator/CLAUDE.md` for the HTTP contract.

**Task 1 — `src/pathly_orchestrator/fsm_http_client.py`**

Rewrite `ensure_server_running` (currently lines 92–105) and `_start_server` (currently lines 77–89):

`ensure_server_running`:
- Remove the hard `time.sleep(2)` and single retry.
- Replace with a poll loop: `for _ in range(30): if _health_ok(): return; time.sleep(0.25)`. Exit immediately on first 200 from `/health`.
- After 30 failed attempts raise RuntimeError with message: "FSM server did not start within 7.5 s — run `pathly-fsm-http` to diagnose."

`_start_server`:
- Before spawning, write the child PID to `platformdirs.user_cache_dir("pathly") / "fsm.pid"`. Create the directory if absent.
- If `fsm.pid` exists, read the PID and probe `/health`. If `/health` returns 200, return immediately (server already running). If not, delete the stale PID file and proceed to spawn.
- On POSIX: spawn with `start_new_session=True`, stdout=DEVNULL, stderr=DEVNULL.
- On Windows: spawn with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS`, stdout=DEVNULL, stderr=DEVNULL.
- Write the PID of the spawned process to `fsm.pid` after Popen returns.

**Task 2 — `src/pathly_orchestrator/http_server.py`**

The `/health` route (currently lines 251–266) must return HTTP 200 before any logging or rate-limit middleware runs. Add a direct `@app.route("/health")` handler at module level that returns `{"status": "ok"}` with no pre/post hooks. Verify the existing route still passes its tests.

**Task 3 — `src/pathly_data/core/skills/utilities/fsm-call.md`**

Find the section that currently reads (steps 2–3):
```
python -m pathly_orchestrator.http_server &
```
(or any variant using `&` as a background operator).

Replace the entire steps 2 and 3 with a single instruction:
```
Call `pathly-fsm-call <subcommand> ...` — the helper handles health-check, auto-start, and retry automatically.
```
The `python -m pathly_orchestrator.http_server &` line and any fallback instructions referencing it must be absent from the file after your edit.

After editing `fsm-call.md`, run:
```
pathly-setup claude --apply
python -m build
```
and confirm both commands exit 0.

**Task 4 — Tests**

Rewrite server startup tests to cover:
- Poll loop exits early on first healthy response.
- Poll loop runs all 30 attempts when server never starts, then raises RuntimeError with the correct message.
- PID file exists with a live process: `_start_server` skips spawn and proceeds to poll.
- PID file exists with a dead/stale process: `_start_server` deletes the stale file and spawns fresh.
- POSIX path: child spawned with `start_new_session=True`.
- Windows path: child spawned with `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags.

Run `python -m pytest tests/ -q -k "server"` and confirm all pass with no skips.

**Verification checklist (must all be true before marking Conv 1 DONE):**
- [ ] AC-S1-1: poll loop present, 30 × 250 ms ceiling, exits on 200
- [ ] AC-S1-2: PID file written; PID-alive check skips spawn
- [ ] AC-S1-3: POSIX uses `start_new_session=True`; Windows uses `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
- [ ] AC-S1-4: `fsm-call.md` has no `&` background operator; single `pathly-fsm-call` instruction
- [ ] AC-S1-5: `/health` returns 200 before middleware
- [ ] AC-S1-6: server startup tests pass green, none deleted
- [ ] `pathly-setup claude --apply` and `python -m build` exit 0

---

## Conv 2 — Scope gate preexisting-dirty snapshot

**Stories delivered:** S2 (AC-S2-1 through AC-S2-7)

**Scope — files you are allowed to touch:**
- `src/pathly_orchestrator/fsm_ops.py`
- `src/pathly_orchestrator/fsm.py`
- `tests/test_gates.py`

Do not touch `fsm_http_client.py`, `http_server.py`, `fsm-call.md`, `team.flow.yaml`, or `review.md`.
Do not push to master without explicit user request.

IMPORTANT: After Conv 2 ships, the `src/pathly_orchestrator/` exemption in `_is_exempt` is removed. This means Conv 3's builder prompt must also explicitly declare `src/pathly_orchestrator/fsm.py` and `src/pathly_orchestrator/fsm_ops.py` in scope, or the scope gate will block those edits.

---

### Prompt

You are implementing Conv 2 of the fsm-friction-fixes feature.

Read `pathly/plans/fsm-friction-fixes/USER_STORIES.md` S2 acceptance criteria (AC-S2-1 through AC-S2-7) before writing any code.
Read `src/pathly_orchestrator/CLAUDE.md` for the HTTP contract and STATE.json conventions.
Read `tests/test_gates.py` and `tests/test_fsm_ops.py` end-to-end before changing any implementation — understand the existing test contract first.

**Task 1 — `src/pathly_orchestrator/fsm_ops.py`: snapshot preexisting dirty files**

In `next_action` (around lines 349–353 where `conv_start_sha` is currently stamped):
- When entering a BUILDING state, run `git status --porcelain=v1 -z` from the feature's working directory.
- Parse the output into a sorted, deduplicated list of file paths.
- Write to STATE.json:
  ```json
  "build_baseline": {
    "started_at": "<ISO-8601 timestamp>",
    "preexisting_dirty": ["<path>", ...]
  }
  ```
- Cap the list at 500 entries. If the real count exceeds 500, store the first 500 and set a flag `"truncated": true` in `build_baseline`.

In `complete_stage` (around line 539):
- Clear `build_baseline` from STATE.json alongside the existing `conv_start_sha` clear.

**Task 2 — `src/pathly_orchestrator/fsm.py`: rewrite `_scope_clean` and update `run_gates`**

Rewrite `_scope_clean` (currently lines 363–436) with the new signature:
```python
def _scope_clean(storage_path, scope_file, preexisting_dirty: set[str] | None) -> bool:
```
Logic:
1. Read declared scope from `scope_file`.
2. Run `git diff --name-only HEAD` — get committed-but-modified files.
3. Run `git status --porcelain=v1 -z` — get untracked files (lines starting with `??`).
4. Union the two sets = "all currently dirty files".
5. Subtract `preexisting_dirty` (if not None) = "files the builder touched this conversation".
6. Compare the builder-touched set against declared scope. Any file not in declared scope that is not exempt = scope violation.
7. Exemptions that remain: `pathly/plans/` prefix and `*.tsbuildinfo` suffix. Remove the exemption for `src/pathly_orchestrator/`.

In `run_gates` (currently lines 439–509):
- Replace the read of `STATE.json["conv_start_sha"]` with a read of `STATE.json.get("build_baseline", {}).get("preexisting_dirty")`.
- If `build_baseline` is absent from STATE.json, emit `GATE_SKIPPED` with `reason: no_build_baseline` and return (do not run the scope comparison).
- If `build_baseline["truncated"]` is true, emit `GATE_DEGRADED` event and return True (permissive mode) — do not attempt the comparison on a truncated set.
- If `preexisting_dirty` count exceeds 500 at gate eval time (shouldn't happen given cap, but defensive check), emit `GATE_DEGRADED` and return True.
- Pass `set(preexisting_dirty)` to the rewritten `_scope_clean`.

**Task 3 — `tests/test_gates.py`: rewrite three tests**

Rewrite (do not delete) the following three tests:

`test_scope_gate_pass` (currently line 229):
- Set up STATE.json with `build_baseline: {preexisting_dirty: [], started_at: "..."}`.
- Mock `subprocess.run` for `git diff --name-only HEAD` to return declared files only.
- Mock `subprocess.run` for `git status --porcelain=v1 -z` to return empty.
- Assert result is None (gate passes).

`test_scope_gate_fail_undeclared_path` (currently line 256):
- Set up STATE.json with `build_baseline: {preexisting_dirty: [], started_at: "..."}`.
- Mock `git diff` to include one undeclared file.
- Assert `gate_failed == "scope_gate"`.

`test_scope_gate_no_baseline_sha` (currently line 313):
- Rename to `test_scope_gate_no_build_baseline` (or keep original name and update docstring).
- Set up STATE.json with no `build_baseline` key.
- Assert a `GATE_SKIPPED` event is emitted with `reason: no_build_baseline`.

Also verify `test_scope_gate_no_declared_scope` (line 292) still passes without modification.

Run `python -m pytest tests/test_gates.py -q` and confirm all pass, no skips, none deleted.

**Verification checklist (must all be true before marking Conv 2 DONE):**
- [ ] AC-S2-1: `build_baseline.preexisting_dirty` written on BUILDING entry with ISO timestamp
- [ ] AC-S2-2: `_scope_clean` new signature; subtracts preexisting from diff+untracked
- [ ] AC-S2-3: `src/pathly_orchestrator/` exemption removed; `pathly/plans/` and `*.tsbuildinfo` remain
- [ ] AC-S2-4: `complete_stage` clears `build_baseline`
- [ ] AC-S2-5: 500-entry cap emits `GATE_DEGRADED`, returns permissive
- [ ] AC-S2-6: absent `build_baseline` emits `GATE_SKIPPED reason=no_build_baseline`
- [ ] AC-S2-7: all three rewritten tests pass green; `test_scope_gate_no_declared_scope` unchanged and passing
- [ ] `python -m pytest tests/test_gates.py tests/test_fsm_ops.py -q` — no failures, no deletes

---

## Conv 3 — Multi-conversation routing (on_state_counter)

**Stories delivered:** S3 (AC-S3-1 through AC-S3-7)

**Scope — files you are allowed to touch:**
- `src/pathly_orchestrator/fsm_ops.py`
- `src/pathly_orchestrator/fsm.py`
- `src/pathly_data/core/flows/team.flow.yaml`
- `src/pathly_data/core/skills/team/review.md`
- `tests/` (new on_state_counter tests only)

Do not touch `fsm_http_client.py`, `http_server.py`, `fsm-call.md`, `test_gates.py` (unless a new test file is preferred).
Do not push to master without explicit user request.

NOTE: `src/pathly_orchestrator/fsm.py` and `src/pathly_orchestrator/fsm_ops.py` must be declared in this prompt's scope explicitly. The `src/pathly_orchestrator/` exemption was removed in Conv 2; these files will not pass the scope gate unless declared.

---

### Prompt

You are implementing Conv 3 of the fsm-friction-fixes feature.

Read `pathly/plans/fsm-friction-fixes/USER_STORIES.md` S3 acceptance criteria (AC-S3-1 through AC-S3-7) before writing any code.
Read `src/pathly_orchestrator/CLAUDE.md` for STATE.json conventions and the transition rule evaluation contract.
Read `src/pathly_data/CLAUDE.md` for the adapter sync rule — any change to core skills or flows requires running `pathly-setup claude --apply` and `python -m build`.
Read `tests/test_fsm_ops.py` end-to-end before changing any implementation.

**Task 1 — `src/pathly_orchestrator/fsm_ops.py`: planned-convs counter**

Add `_count_planned_convs(storage_path: Path) -> int`:
- Count rows matching `| [0-9]+ |` (the `#` column pattern) in `PROGRESS.md`.
- Return 0 if the file is absent or the pattern matches nothing.

In `next_action`:
- If `STATE.json["convs_total"]` is absent, call `_count_planned_convs` and write `STATE.json["convs_total"] = <count>` and `STATE.json["convs_done"] = 0`.
- On every subsequent call, re-read `PROGRESS.md` row count. If it differs from `STATE.json["convs_total"]`, emit a warning event with `reason: convs_total_mismatch, persisted: <old>, current: <new>`. Do not update `STATE.json["convs_total"]`.

**Task 2 — `src/pathly_orchestrator/fsm.py`: `on_state_counter` rule level**

In `evaluate_transition_rules` (currently lines 81–176 of eventlog.py per scout findings, but the function lives in fsm.py — confirm actual location before editing):
- After the existing `on_artifact` check, add a new level for `on_state_counter`.
- Schema:
  ```yaml
  on_state_counter:
    field: convs_done
    op: lt           # one of: lt, lte, eq, gte, gt, ne
    compare_to: convs_total
    next: BUILDING
  ```
- Read `STATE.json[rule["field"]]` and `STATE.json[rule["compare_to"]]` as integers.
- Apply the operator. Supported: `lt`, `lte`, `eq`, `gte`, `gt`, `ne`.
- If condition is true, return `rule["next"]`.
- If condition is false, field is missing, value is non-integer, or op is unknown: fall through to the next rule level without raising.

Also in `fsm.py`, extend the `update_progress` transition action handler:
- When `mark: conv_done` is received, read `STATE.json["convs_done"]`, increment by 1, write back (atomic read-modify-write within the action).

**Task 3 — `src/pathly_data/core/flows/team.flow.yaml`: rewrite REVIEWING block**

Current REVIEWING block:
```yaml
REVIEWING:
  on_artifact:
    REVIEW_FAILURES.md: BUILDING
    MORE_CONVS_NEEDED.md: BUILDING
  default: TESTING
```

Replace with:
```yaml
REVIEWING:
  on_artifact:
    REVIEW_FAILURES.md: BUILDING
    MORE_CONVS_NEEDED.md: BUILDING   # backwards-compat fallback — one release window
  on_state_counter:
    field: convs_done
    op: lt
    compare_to: convs_total
    next: BUILDING
  default: TESTING
```

Rule evaluation order: `on_artifact` → `on_state_counter` → `default`. This preserves backward compat: if `MORE_CONVS_NEEDED.md` is present it fires before the counter check.

**Task 4 — `src/pathly_data/core/skills/team/review.md`**

Remove the instruction at line 177 that tells the reviewer to write `MORE_CONVS_NEEDED.md`. The reviewer no longer drives routing manually — the FSM counter handles it.

After editing `review.md`, run:
```
pathly-setup claude --apply
python -m build
```
Confirm both commands exit 0 and the codex/copilot adapters reflect the removal.

**Task 5 — Tests**

Add four new tests covering `on_state_counter` (in a new test function or file):

1. `test_on_state_counter_condition_met`: STATE.json has `convs_done=1`, `convs_total=3`. Rule: `field=convs_done, op=lt, compare_to=convs_total, next=BUILDING`. Assert evaluator returns `"BUILDING"`.
2. `test_on_state_counter_condition_unmet`: STATE.json has `convs_done=3`, `convs_total=3`. Same rule. Assert evaluator returns None (falls through).
3. `test_on_state_counter_missing_field`: STATE.json has no `convs_done` key. Assert evaluator returns None without raising.
4. `test_on_state_counter_malformed_op`: Rule has `op: xlt` (unknown). Assert evaluator returns None without raising.

Run `python -m pytest tests/ -q -k "on_state_counter"` and confirm all 4 pass.

Also verify `test_next_action_initial_state` (line 63 in `tests/test_fsm_ops.py`) still passes after `convs_total` and `convs_done` are added to STATE.json.

**Verification checklist (must all be true before marking Conv 3 DONE):**
- [ ] AC-S3-1: `_count_planned_convs` present; returns 0 for absent PROGRESS.md
- [ ] AC-S3-2: `convs_total`/`convs_done` stamped on first `next_action`; mismatch warning on subsequent calls
- [ ] AC-S3-3: `on_state_counter` level in `evaluate_transition_rules`; generic `{field, op, compare_to, next}` schema; all 6 ops supported; graceful fallthrough on miss/error
- [ ] AC-S3-4: `team.flow.yaml` REVIEWING block updated; `MORE_CONVS_NEEDED.md` fallback retained
- [ ] AC-S3-5: `update_progress` action increments `convs_done` on `mark: conv_done`
- [ ] AC-S3-6: `review.md` line 177 instruction removed; `pathly-setup claude --apply` and `python -m build` exit 0
- [ ] AC-S3-7: 4 new counter tests pass; `test_next_action_initial_state` still passes
- [ ] `python -m pytest tests/ -q` — no failures, no test deleted
