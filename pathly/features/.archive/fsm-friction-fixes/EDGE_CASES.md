# EDGE_CASES — fsm-friction-fixes

---

## EC-1 — PID staleness on Windows (Conv 1)

**Scenario:** A previous Pathly session crashed without cleaning up `fsm.pid`. The PID now belongs to an unrelated Windows process (PID reuse is common on Windows with small PID spaces).

**Risk:** `_start_server` reads the stale PID, determines the process is "alive" (it is, but it's not the FSM server), skips spawn, and proceeds to the poll loop. The poll loop exhausts all 30 attempts and raises RuntimeError.

**Mitigation:** PID is a hint only. The poll loop runs in all cases after `_start_server` returns. If `/health` does not return 200 within 7.5 s, the error message directs the user to run `pathly-fsm-http` manually. Never trust the PID alone without a successful health probe.

**Boundary:** The PID check bypasses spawn but does not bypass the health poll. A stale PID delays the first spawn by one health-probe attempt (250 ms) at most before the logic recognizes the existing process is not the FSM and respawns.

**Implementation note:** After the PID-alive check, if `/health` fails, delete the PID file and call the spawn path. This prevents a single stale file from permanently blocking auto-start.

---

## EC-2 — Concurrent skill invocations racing on port 8765 (Conv 1)

**Scenario:** Two `/pathly` skill calls execute simultaneously (e.g., two Claude Code panels open). Both call `ensure_server_running`. Both read a missing or stale PID and both call `_start_server`.

**Risk:** Both spawn a new `pathly_orchestrator.http_server` process. The first to bind port 8765 wins. The second raises `OSError: [WinError 10048]` (Windows) or `OSError: [Errno 98] Address already in use` (POSIX) and the spawned process exits silently (stdout/stderr DEVNULL).

**Mitigation:** The poll loop in both skills polls `/health`. The winner's server is running; both polls eventually return 200 from the winner. The loser's spawned process died quietly; the user never sees an error. This is the intended behavior: the PID file after this race holds whichever PID was written last, which may be the loser's (dead) process. The next call that finds a dead PID will delete and respawn — one wasted poll attempt.

**Boundary:** Acceptable. No user-visible error. One orphaned process exits immediately. Next PID file is written by whichever spawn succeeds.

---

## EC-3 — Snapshot race: builder runs `git add` before `next_action` (Conv 2)

**Scenario:** The user has files they intend to stage (`git add`) before calling `next_action`. Those files are clean (already staged) by the time `next_action` runs `git status --porcelain=v1 -z`. They are absent from `preexisting_dirty`.

**Risk:** If the builder then re-edits those staged files, they appear in `git diff HEAD` output but are not in `preexisting_dirty`. They will be correctly flagged as "builder-touched" — which is accurate, since the builder did touch them after `next_action`.

**Outcome:** This is correct behavior, not a false positive. The boundary of "before the conversation" is `next_action` call time.

---

## EC-4 — Snapshot race: user edits a file between `next_action` and builder's first write (Conv 2)

**Scenario:** `next_action` runs, snapshots `preexisting_dirty`. Before the builder starts, the user edits an unrelated file. That file is now dirty but not in `preexisting_dirty`.

**Risk:** If that file happens to be within the builder's declared scope, the scope gate will pass (the builder-touched set includes it, and it's in scope). Correct. If the file is outside scope, the gate will flag it as a scope violation even though the builder didn't touch it.

**Mitigation:** Accepted as per-design. The gate is a belt-and-braces control against builder runaway, not a primary authorization control. `CONVERSATION_PROMPTS.md` scope declaration is the primary contract.

---

## EC-5 — Large `preexisting_dirty` sets (Conv 2)

**Scenario:** A developer works on a large monorepo with hundreds of modified files in their working tree before running `next_action`.

**Risk:** `STATE.json["build_baseline"]["preexisting_dirty"]` could contain thousands of entries, making STATE.json multi-KB and causing parsing/serialization overhead on every gate evaluation.

**Mitigation:** Cap at 500 entries (sorted, first 500 by path). Set `truncated: true`. When `run_gates` reads `truncated: true`, emit `GATE_DEGRADED` event and return permissive (True). Do not run the scope comparison on a truncated set — the subtraction would be incomplete and produce false positives.

**Boundary:** 500 entries covers typical working-tree state. A developer with >500 dirty files in a typical feature implementation is an unusual case; the gate degrading to permissive is the least-bad outcome.

---

## EC-6 — PROGRESS.md edited mid-feature (Conv 3)

**Scenario:** The user manually edits `PROGRESS.md` to add a fourth conversation after the feature is already in BUILDING state with `convs_total = 3` persisted.

**Risk:** FSM counts 4 rows in PROGRESS.md on the next `next_action` call but `convs_total` in STATE.json is 3. The counter check `convs_done < convs_total` will fire correctly for 3 conversations, then `default: TESTING` will fire. The fourth conversation never runs unless the user explicitly resets.

**Mitigation:** On every `next_action` call, re-read PROGRESS.md row count and emit a warning event if it differs from persisted `convs_total` (`reason: convs_total_mismatch, persisted: 3, current: 4`). Do not auto-correct. The user must explicitly reset `convs_total` via a CLI flag (or manually edit STATE.json) if they intentionally added a conversation.

**Boundary:** A warning event is surfaced to the user. No silent data loss or incorrect routing.

---

## EC-7 — GATE_SKIPPED backward compat when `preexisting_dirty` is absent from older STATE.json (Conv 2)

**Scenario:** A feature plan created before Conv 2 ships has a STATE.json with no `build_baseline` key. The builder tries to complete a BUILDING stage on the old plan.

**Risk:** `run_gates` reads `STATE.json.get("build_baseline")` and gets None. Without the guard, `_scope_clean` would be called with `preexisting_dirty=None` and might raise or produce incorrect results.

**Mitigation:** When `build_baseline` is absent, `run_gates` emits `GATE_SKIPPED` with `reason: no_build_baseline` and returns without running the scope comparison. No new keys are written into the old STATE.json. The next `next_action` call for that feature will write `build_baseline` fresh.

**Boundary:** Existing in-progress features continue to work. The scope gate is skipped for exactly one conversation cycle (from the old BUILDING entry to `complete_stage`). After `complete_stage`, the next `next_action` writes a fresh `build_baseline` and the gate runs normally.

---

## EC-8 — `on_state_counter` with `convs_total = 0` (legacy single-conv, Conv 3)

**Scenario:** `PROGRESS.md` is absent or has no numbered rows. `_count_planned_convs` returns 0. STATE.json is written with `convs_total = 0`, `convs_done = 0`.

**Risk:** `on_state_counter` rule evaluates `0 < 0` = false. Falls through to `default: TESTING`. This is correct for a single-conversation flow that never needs to loop back.

**Mitigation:** No action needed. This is the intended behavior for legacy flows and single-conversation plans.

---

## EC-9 — `on_state_counter` `compare_to` field is a non-integer (Conv 3)

**Scenario:** STATE.json has `convs_total: "three"` (string, perhaps manually edited).

**Risk:** The evaluator tries `int(state["convs_done"]) < int(state["convs_total"])` and `int("three")` raises ValueError.

**Mitigation:** Wrap the comparison in a try/except. On ValueError or TypeError, fall through to the next rule level without raising. Log a warning event with `reason: on_state_counter_type_error`.

---

## EC-10 — Conv 3 ships before Conv 2 (ordering risk)

**Scenario:** Conv 3 (counter-driven routing) is deployed without Conv 2 (preexisting-dirty snapshot). The scope gate is still SHA-based.

**Risk:** REVIEWING → BUILDING counter loop fires correctly. Builder runs a second conversation. The SHA-based scope gate treats any preexisting-dirty files as in-scope (same bug as before Conv 2). No new failure mode introduced — behavior is no worse than before this feature.

**Mitigation:** Planned ordering is Conv 1 → Conv 2 → Conv 3. If Conv 3 must ship early, document that the scope gate remains unfixed until Conv 2 completes.
