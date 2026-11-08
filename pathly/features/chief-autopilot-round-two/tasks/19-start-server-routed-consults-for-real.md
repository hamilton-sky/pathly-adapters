# Start a server-routed consult for real, on the asking run's board, billed once

Type: task
Status: open
Blocked by: 04, 06, 07, 16
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/consult_trigger.py, tests/comms_board/test_consult_router.py, src/pathly_data/core/skills/fragments/consult.md, tests/snapshots/team__build.claude.md, tests/snapshots/team__review.claude.md, tests/snapshots/team__test.claude.md, src/pathly_orchestrator/supervisor/goal_executor.py, src/pathly_orchestrator/supervisor/api.py, src/pathly_orchestrator/runner/events.py, src/pathly_orchestrator/supervisor/terminal_reconcile.py, tests/runner_supervisor/test_consult_start_for_real.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

Found by ticket 12 (acceptance). Driving the real routes, router and supervisor end to end, no
consult ever reaches a spawn host, a role question from a single run or a goal-loop task on the
project board is handed to the person instead of routed, and a consult on the project board is
billed twice. The draft acceptance test that shows all three is in the ticket 12 Attempt note.

1. **The consult spawn crashes.** `http_server/consult_trigger.py` passes
   `broadcast_fn=sse._broadcast_spawn` (one argument) to `on_question`; the stage spawn calls
   `broadcast_fn(state.topic, payload)` (`supervisor/terminal.py`), which raises, so the route is
   set `failed` and the question goes to the person. Pass `sse._broadcast_runner`, as the goal-run
   and decompose routes do. `tests/comms_board/test_consult_router.py` asserts the wrong function:
   change it with the fix.
2. **A role question's board never matches the asking run's token.** The post in
   `fragments/consult.md` has no `"board"`, so the question is stored on `feature`/<root>, while a
   single run's token is `project`/<root>; `consult_router._asker_refusal` then hands it to the
   person. Add `"board": "<board>"` to that post (the placeholder `comms-post.md` already uses and
   the runner sets), and regenerate the three team snapshots that compose `consult.md`. A goal-loop
   run's `sched-` task tokens are minted with `state.scope_tier`, which a goal flow run never sets
   (default `feature`, even for a goal on the project board): set it from the goal's board when
   `goal_executor` starts the flow run (pass it through `supervisor/api.start_run` if that is where
   the state is built; `runner.telemetry.scope_tier_for(board)` is the mapping board_run and
   consult_run use), so the loop task's token board equals the board its prompt tells it to post on.
3. **Project-board runs lose their own AGENT_DONE.** `runner/events.py` (`read_last_agent_done`
   and the AGENT_DONE lookup of the billing patch) and `supervisor/terminal_reconcile.py` take
   `storage.parent.parent.parent` as the project root, one level too high for
   `<root>/pathly/project/<kind>/<slug>`, so `_synthesize_agent_done_if_missing` never finds the
   consult's own AGENT_DONE and writes a second one (two `agent_invocations` rows). Derive the root
   by the `pathly/` anchor, as `eventlog` and `fsm_compose_vars._project_root_from_storage` already
   do (reuse one of them, do not add a third copy; respect the layer rule, imports lazy if needed).

Document the board rule and the root derivation in `src/pathly_orchestrator/CLAUDE.md` where the
consult run is described.

## Not in this ticket

- The acceptance test itself: ticket 12 (its draft is ready and is put back after this ticket).
- `GET /runs/<id>` reading `outcome: None` for a successful goal-loop run (ticket 12's draft checks
  status and error instead).

## Done when

- `python -m pytest tests/runner_supervisor/test_consult_start_for_real.py -q -p no:cacheprovider`
  passes and covers: a `type: question` post `to: architect` with a live run token, through the
  real `consult_trigger` hook and `on_question` with a host present, reaches a `TERMINAL_SPAWN`
  broadcast for a `consult-` run (no `TypeError`, route not `failed`); a question posted as the
  fragment now says, with a single run's `project` token, is routed (not handed to the person);
  a goal-loop flow run started by `goal_executor` for a goal on the project board has
  `scope_tier == "project"`; and on a project-board run a consult whose agent wrote its own
  AGENT_DONE leaves exactly one `agent_invocations` row.
- The composed team prompts show `"board": "<board>"` (substituted) in the consult post, and the
  snapshot tests pass.
- All existing tests under `tests/comms_board`, `tests/runner_supervisor`, `tests/telemetry` and
  `tests/dag_goals` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_consult_start_for_real.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board tests/runner_supervisor tests/telemetry tests/dag_goals -q -p no:cacheprovider
exit 0
```

## Reference

- ticket 12's Attempt note (the three failures, with file and line)
- `src/pathly_orchestrator/eventlog.py` (`pathly/` anchor root), `src/pathly_orchestrator/fsm_compose_vars.py` (`_project_root_from_storage`)
- `src/pathly_orchestrator/supervisor/consult_router.py` (`_asker_refusal`), `supervisor/board_run.py` and `supervisor/consult_run.py` (`scope_tier_for`)

## Answer
