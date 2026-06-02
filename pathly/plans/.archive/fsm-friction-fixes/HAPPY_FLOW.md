# HAPPY_FLOW — fsm-friction-fixes

Nominal path for each conversation. No errors, no edge cases.

---

## Conv 1 — FSM server auto-start

1. Builder reads story S1 and scout findings for `fsm_http_client.py`.
2. `ensure_server_running` is rewritten: poll loop (30 × 250 ms), exits on first 200.
3. `_start_server` writes PID file to user cache; uses platform-correct Popen flags.
4. `/health` route in `http_server.py` returns 200 before middleware.
5. `fsm-call.md` steps 2–3 collapsed to a single `pathly-fsm-call` instruction; `&` fallback gone.
6. `pathly-setup claude --apply` and `python -m build` both exit 0.
7. Server startup tests pass green. Conv 1 marked DONE.

---

## Conv 2 — Scope gate preexisting-dirty snapshot

1. Builder reads story S2, existing `test_gates.py`, and `fsm.py`/`fsm_ops.py`.
2. `next_action` snapshots `git status --porcelain=v1 -z` into `STATE.json["build_baseline"]`.
3. `_scope_clean` rewritten: subtracts `preexisting_dirty` from `git diff HEAD` + untracked, compares remainder against declared scope.
4. `_is_exempt` exemption for `src/pathly_orchestrator/` removed.
5. `complete_stage` clears `build_baseline`.
6. Three tests in `test_gates.py` rewritten to seed `build_baseline`; all pass green.
7. `test_scope_gate_no_declared_scope` passes unchanged. Conv 2 marked DONE.

---

## Conv 3 — Multi-conversation routing (on_state_counter)

1. Builder reads story S3, `test_fsm_ops.py`, `team.flow.yaml`, and adapter sync rules.
2. `_count_planned_convs` added to `fsm_ops.py`; `next_action` stamps `convs_total`/`convs_done`.
3. `evaluate_transition_rules` gains `on_state_counter` level with generic `{field, op, compare_to, next}` schema.
4. `update_progress` action increments `convs_done` on `mark: conv_done`.
5. `team.flow.yaml` REVIEWING block updated: `on_state_counter` added, `MORE_CONVS_NEEDED.md` fallback retained.
6. `review.md` line 177 removed; `pathly-setup claude --apply` and `python -m build` exit 0.
7. Four new `on_state_counter` tests pass green. `test_next_action_initial_state` still passes. Conv 3 marked DONE.
