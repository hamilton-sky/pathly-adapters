# USER_STORIES — fsm-friction-fixes

Delivered by: Conv 1 (S1), Conv 2 (S2), Conv 3 (S3).

---

## S1 — FSM server auto-start (zero-touch)

**As a** Pathly contributor invoking any `/pathly` skill,
**I want** the FSM HTTP server to start reliably on first call without me opening a terminal,
**So that** I never see "FSM server unavailable" mid-skill.

### Acceptance Criteria

**AC-S1-1:** `ensure_server_running` in `src/pathly_orchestrator/fsm_http_client.py` replaces the fixed `time.sleep(2)` + single retry with a poll loop of at most 30 attempts at 250 ms intervals (7.5 s ceiling). The loop exits immediately on the first HTTP 200 from `/health`.

**AC-S1-2:** `_start_server` writes a PID file to `<user_cache>/pathly/fsm.pid` before spawning the server process. If the PID file exists and the process is alive (via OS `psutil` or equivalent), spawn is skipped and the poll loop proceeds directly.

**AC-S1-3:** On POSIX, the child process is spawned with `start_new_session=True`. On Windows, the child is spawned with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS`. The fire-and-forget Popen with inherited file descriptors is removed.

**AC-S1-4:** `src/pathly_data/core/skills/utilities/fsm-call.md` contains exactly one instruction for starting the server: call `pathly-fsm-call`. The `python -m pathly_orchestrator.http_server &` fallback (and any variant using `&`) is absent from the file.

**AC-S1-5:** `/health` in `src/pathly_orchestrator/http_server.py` returns HTTP 200 before any logging or rate-limit middleware runs. A cold-start probe returns within 500 ms once the Flask process is bound.

**AC-S1-6:** Running `python -m pytest tests/ -q -k "server"` (or the equivalent server startup test suite) passes green with no skips and no test deleted.

### Edge Cases

- A stale PID file from a crashed prior session must not block a new server spawn. The PID is only trusted after `/health` returns 200; if `/health` fails after the PID-exists check, the old process is considered dead and a new one is spawned.
- Two concurrent skill invocations both calling `ensure_server_running` simultaneously: the PID file acts as a hint; both proceed to poll; the loser's Flask process dies on port-in-use; the health poll still returns 200 from the winner.
- Windows cold-start may take 3–6 s. The 7.5 s ceiling (30 × 250 ms) must be sufficient; if not, the error message must say "server did not start within 7.5 s — run `pathly-fsm-http` to diagnose" (not the old "Start it with: python -m …").

---

## S2 — Scope gate tracks touched files (not SHA delta)

**As a** Pathly contributor with uncommitted unrelated edits in my working tree,
**I want** the scope gate to only flag files the builder actually wrote during the conversation,
**So that** my pre-existing local changes do not cause SCOPE_VIOLATION false positives.

### Acceptance Criteria

**AC-S2-1:** When `next_action` enters a BUILDING state, `fsm_ops.py` runs `git status --porcelain=v1 -z` and persists the resulting file paths to `STATE.json["build_baseline"]["preexisting_dirty"]` (a sorted list, no duplicates), together with `STATE.json["build_baseline"]["started_at"]` as an ISO-8601 timestamp.

**AC-S2-2:** `_scope_clean` in `fsm.py` is rewritten with signature `_scope_clean(storage_path, scope_file, preexisting_dirty: set[str] | None) -> bool`. It reads `build_baseline.preexisting_dirty` from STATE.json, subtracts it from the union of `git diff --name-only HEAD` output and untracked files, then compares the remainder against the declared scope list.

**AC-S2-3:** The `_is_exempt` exemption for `src/pathly_orchestrator/` is removed. The exemptions for `pathly/plans/` and `*.tsbuildinfo` remain.

**AC-S2-4:** `complete_stage` clears `build_baseline` (along with `conv_start_sha`) from STATE.json so the next conversation re-baselines fresh.

**AC-S2-5:** When `build_baseline.preexisting_dirty` contains more than 500 entries, `_scope_clean` emits a `GATE_DEGRADED` event and returns `True` (permissive mode). The gate does not raise or block.

**AC-S2-6:** When STATE.json has no `build_baseline` key (legacy plan), `run_gates` emits `GATE_SKIPPED` with `reason: no_build_baseline` and does not attempt the scope comparison. No new keys are written into the old STATE.json.

**AC-S2-7:** The three rewritten tests (`test_scope_gate_pass`, `test_scope_gate_fail_undeclared_path`, `test_scope_gate_no_baseline_sha`) in `tests/test_gates.py` pass green. None is deleted; each is rewritten to seed `build_baseline.preexisting_dirty` and mock `git diff HEAD` + `git status --porcelain`. Running `python -m pytest tests/test_gates.py -q` shows no failures and no skips on those three tests.

### Edge Cases

- Builder runs `git add` before `next_action` is called: those files are absent from `porcelain` output and will be correctly flagged if out of scope.
- User edits a file between `next_action` snapshot and the builder's first write: that file is in `preexisting_dirty` and is exempted. Accepted as per-design (gate is belt-and-braces, not a primary auth control).
- Builder creates a new untracked file outside declared scope: `git status --porcelain` includes untracked files; they are subtracted only if pre-existing; new ones are caught.
- `preexisting_dirty` set is exactly 500 entries: gate operates normally. 501 entries: `GATE_DEGRADED` event, permissive mode.

---

## S3 — Multi-conversation routing as a first-class FSM concept

**As a** Pathly contributor running a multi-conversation feature plan,
**I want** the FSM to know how many conversations the plan declared and route explicitly on a counter,
**So that** reviewer forgetfulness can never advance the FSM past unfinished work.

### Acceptance Criteria

**AC-S3-1:** `fsm_ops.py` contains a function `_count_planned_convs(storage_path: Path) -> int` that counts rows matching `| [0-9]+ |` in `PROGRESS.md`. Returns 0 if the file is absent.

**AC-S3-2:** On the first `next_action` call for a feature (when `convs_total` is absent from STATE.json), the FSM writes `STATE.json["convs_total"]` and `STATE.json["convs_done"] = 0`. On every subsequent `next_action` call, it re-reads the PROGRESS.md row count and emits a warning event if it differs from the persisted `convs_total`; it does not auto-correct.

**AC-S3-3:** `evaluate_transition_rules` in `fsm.py` supports a new rule level `on_state_counter` with the generic schema:
```yaml
on_state_counter:
  field: convs_done
  op: lt            # one of: lt, lte, eq, gte, gt, ne
  compare_to: convs_total
  next: BUILDING
```
The evaluator compares two integer fields from STATE.json using the specified operator. On match it returns the `next` state string. On miss (condition false, missing fields, or malformed rule) it falls through to the next rule level without raising.

**AC-S3-4:** `team.flow.yaml` REVIEWING block is updated: `on_state_counter` checks `convs_done < convs_total → BUILDING`; `on_artifact: MORE_CONVS_NEEDED.md: BUILDING` remains as a backwards-compat fallback; `default: TESTING` is unchanged.

**AC-S3-5:** The `update_progress` transition action increments `STATE.json["convs_done"]` atomically (read-modify-write within the existing action handler) when called with `mark: conv_done`.

**AC-S3-6:** `core/skills/team/review.md` no longer contains the instruction to write `MORE_CONVS_NEEDED.md` (previously line 177). After removing that instruction, `pathly-setup claude --apply` and `python -m build` are run and produce no errors; the codex and copilot adapters reflect the change.

**AC-S3-7:** New tests cover the `on_state_counter` evaluator: (a) condition met routes to next state, (b) condition unmet falls through to next rule level, (c) missing STATE.json field falls through without raising, (d) malformed rule (unknown op) falls through without raising. All four cases pass in `python -m pytest tests/ -q -k "on_state_counter"`.

### Edge Cases

- `convs_total = 0` (legacy single-conv or absent PROGRESS.md): `on_state_counter` with `convs_done < convs_total` evaluates `0 < 0` = false, falls through to `default: TESTING`. Correct behavior.
- `convs_done` equals `convs_total` (last conversation complete): condition false, falls through to `default: TESTING`. Correct behavior.
- PROGRESS.md row count changes mid-feature: warning event emitted, no auto-correction. Manual CLI reset required.
- Reviewer writes `MORE_CONVS_NEEDED.md` AND counter says done: `on_artifact` fires first (existing rule precedence), routes to BUILDING. Counter would have said TESTING. `on_artifact` wins; this is the backward-compat case.
- `on_state_counter` rule `compare_to` field references a string (not an int) in STATE.json: falls through, does not raise.
