# ARCHITECTURE_PROPOSAL — fsm-friction-fixes

This is a cross-layer change note. No new abstractions are introduced. All changes are additive or targeted rewrites within existing modules.

---

## Layers touched

| Layer | File | Nature of change |
|---|---|---|
| Transport | `src/pathly_orchestrator/fsm_http_client.py` | Rewrite `ensure_server_running` (poll loop) and `_start_server` (PID file, platform flags) |
| Transport | `src/pathly_orchestrator/http_server.py` | Add fast `/health` short-circuit before middleware |
| Skill markdown | `src/pathly_data/core/skills/utilities/fsm-call.md` | Remove broken `&` fallback; single instruction to `pathly-fsm-call` |
| Gate logic | `src/pathly_orchestrator/fsm.py` | Rewrite `_scope_clean` signature + body; update `run_gates`; remove `_is_exempt` for `src/pathly_orchestrator/`; add `on_state_counter` level to `evaluate_transition_rules`; extend `update_progress` action |
| State management | `src/pathly_orchestrator/fsm_ops.py` | Add `build_baseline` snapshot in `next_action`; clear in `complete_stage`; add `_count_planned_convs`; stamp `convs_total`/`convs_done`; emit mismatch warning |
| Flow schema | `src/pathly_data/core/flows/team.flow.yaml` | Rewrite REVIEWING block with `on_state_counter`; retain `MORE_CONVS_NEEDED.md` fallback |
| Skill markdown | `src/pathly_data/core/skills/team/review.md` | Remove line 177 instruction to write `MORE_CONVS_NEEDED.md` |

---

## STATE.json schema additions (additive only)

All new keys are additive. Existing readers (`eventlog.py:read_state`, Studio STATE.json renderer) use `.get()`-style access and tolerate unknown keys silently — confirmed by scout (eventlog.py lines 170–175).

### Added by Conv 2

```json
"build_baseline": {
  "started_at": "2026-06-01T12:00:00+00:00",
  "preexisting_dirty": ["src/some/file.py", "tests/test_thing.py"],
  "truncated": false
}
```

- `preexisting_dirty`: sorted list, no duplicates, capped at 500 entries.
- `truncated`: true when the actual dirty count exceeded 500 (permissive-mode sentinel).
- Cleared by `complete_stage` at end of each conversation.
- Absent in legacy STATE.json files — triggers `GATE_SKIPPED reason=no_build_baseline`.

### Added by Conv 3

```json
"convs_total": 3,
"convs_done": 1
```

- `convs_total`: int, count of PROGRESS.md numbered rows at first `next_action`. Never auto-updated; mismatch emits warning event.
- `convs_done`: int, incremented atomically by `update_progress` action on `mark: conv_done`.
- Absent in legacy STATE.json files — `on_state_counter` falls through gracefully when fields missing.

### Keys removed or renamed

None. `conv_start_sha` is still cleared by `complete_stage` (existing behavior unchanged). The new `build_baseline` key supplements it but does not replace it.

---

## Dependency and ordering constraints

Problems 1, 2, and 3 are independent at the code level:
- Conv 1 touches only transport files and skill markdown.
- Conv 2 touches only gate logic and state management. STATE.json keys added: `build_baseline.*`.
- Conv 3 touches only routing logic, state management, flow schema, and skill markdown. STATE.json keys added: `convs_total`, `convs_done`.
- No key conflicts between Conv 2 and Conv 3 additions.

One non-code dependency: after Conv 2, `_is_exempt` for `src/pathly_orchestrator/` is removed. Conv 3's builder must declare `fsm.py` and `fsm_ops.py` explicitly in scope — failing to do so will cause the scope gate (now enforcing correctly) to block the build.

---

## Adapter cross-impact

- `fsm-call.md` (Conv 1) and `review.md` (Conv 3) are both in `core/` — they propagate to codex and copilot adapters automatically via `python -m build`. No manual `_meta/` edits required.
- Gate behavior is shared across adapters. The removal of the `src/pathly_orchestrator/` exemption affects all adapters equally. No adapter-level override exists for this exemption.
- `team.flow.yaml` is in `core/flows/` — also propagates via `python -m build`.

---

## What does not change

- No new `pathly-fsm-call` CLI flags or subcommands.
- No OS-level service registration.
- No Studio/Electron UI changes.
- No auto-migration of legacy STATE.json files.
- `eventlog.py:read_state` contract is unchanged — it already tolerates new keys.
- `on_artifact: MORE_CONVS_NEEDED.md: BUILDING` remains in `team.flow.yaml` for this release.
