# Open a fresh CLI session for the reviewer instead of resuming the builder's

Type: task
Status: open
Blocked by: —
Test first: yes

Leaving the builder's summary out of the reviewer's prompt is not enough on its own.
`supervisor/orchestrator_session.py::resolve_session` reuses `state.open_session` whenever a
stage's adapter equals the previous stage's. `team-build` maps BUILDING and REVIEWING to
`claude`, and `team` has no `adapter_map`, so `_loop` defaults both stages to `claude`. The
reviewer's spawn therefore gets `--resume <builder session id>` (`core/adapters.yaml`,
`claude.resume`). A resumed claude session restores the full conversation history, tool calls
and results included, also under `-p` (map.md § Decisions so far). So the reviewer holds the
builder's whole transcript and its completion summary, whatever its prompt leaves out.

**One role mapping.** Add `agent_role_of(agent: str) -> str` to `src/pathly_orchestrator/fsm_compose_tables.py`:
`_SKILL_AGENT_ROLE.get(agent)`, else the last `/` segment of `agent`. Today the same mapping is
written inline twice: the `agent_role` lines in `fsm_compose.build_prompt` and the return line
in `supervisor/terminal_identity._spawn_role`. Replace both with the helper, so the stage that
gets the Review packet and the stage that gets a fresh session are picked by one rule (root
`CLAUDE.md` SOLID rule 5).

**The fresh session.** In `orchestrator_session.py`:

- add `INDEPENDENT_ROLES = frozenset({"reviewer"})`;
- give `resolve_session` a fifth parameter, `stage_agent: str = ""` (the `/next_action`
  response's `agent`, an `agent_map` entry such as `team/review`);
- when `agent_role_of(stage_agent)` is in `INDEPENDENT_ROLES`, return `session_id=None` whatever
  the open session is. The `SESSION` event then has `kind: "opened"` and `"independent": True`.
  `degraded` and `adapter_supports_resume` are computed as before;
- import `agent_role_of` inside the function, as it already imports `resolve_command`.

In `orchestrator._loop`, pass `response.get("agent", "")` as the fifth positional argument of
the `resolve_session(` call. The argument line is then 86 characters, under black's default of
88 (map.md § Decisions so far), so the call stays three lines. `orchestrator.py` is at 399
lines and must not pass 400 (`scripts/check_file_size.py`).

What stays as it is:

- `_loop` still stores the reviewer's own new session as `open_session`. The next stage on the
  same adapter (TESTING, or the next task's BUILDING in `team-build`) continues the reviewer's
  session, not the builder's (spec.md § Risks).
- The question-answer re-spawn inside a stage (`retry_session` in `_loop`) resumes that stage's
  own session, so a reviewer that asked a question keeps its own conversation.
- Feedback spawns already pass `session=None` (`orchestrator_stage._resolve_stage_supervised`).

Living docs, in `src/pathly_orchestrator/CLAUDE.md`:

- step 3 of the control diagram ("reuse session_id iff same adapter");
- the `orchestrator_session.py` line in the package structure;
- the "Same-adapter consecutive stages share a `session_id`" sentence under "Visible runner";
- the `SESSION` row of the SSE events table (the `independent` field).

Each one says the reviewer stage always opens a fresh session.

## Not in this ticket

- What the reviewer's prompt carries (the Review packet, no history block): ticket 10.
- Fresh sessions for the tester or any other role: not asked. They keep same-adapter
  continuity.
- Restoring the builder's session for the stage after REVIEWING: not done. It needs a second
  session slot in `RunnerState` and a change inside `orchestrator.py`, which has one line left.

## Done when

- `python -m pytest tests/runner_supervisor/test_reviewer_fresh_session.py -q -p no:cacheprovider`
  passes. Through `start_run`, with `fsm_http_client.next_action`, `complete_stage` and
  `supervisor._run_stage_via_terminal` patched as
  `tests/runner_supervisor/test_supervisor.py::test_session_continuity_same_adapter` does, it
  covers:
  - BUILDING (`team/build`, claude) then REVIEWING (`team/review`, claude): the builder spawn
    returns `session_id` `builder-sess`, and the reviewer spawn is called with `session=None`.
    The `SESSION` event for REVIEWING has `kind` `opened` and `independent` true;
  - REVIEWING then TESTING (`team/test`, claude): the tester spawn gets the reviewer's session
    id;
  - BUILDING then BUILDING (both `team/build`): the second spawn gets the first spawn's session
    id;
  - `agent_role_of` gives `reviewer` for `team/review` and for `quality/reviewer`, and `builder`
    for `builder`.
- `python -m pytest tests/runner_supervisor/test_supervisor.py tests/fsm_flows -q -p no:cacheprovider`
  still passes (session continuity for other roles, and `build_prompt` after the helper swap).
- `python scripts/check_file_size.py` exits 0 (`orchestrator.py` did not pass 400 lines).

```check
# The conductor runs this block before review.
$ python -m pytest tests/runner_supervisor/test_reviewer_fresh_session.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor/test_supervisor.py tests/fsm_flows -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- spec.md § Decisions ("What 'without the builder's summary' removes", "How the reviewer avoids
  the builder's session"), § Risks
- map.md § Decisions so far (`claude --resume` restores the conversation)
- `src/pathly_orchestrator/supervisor/orchestrator_session.py::resolve_session`,
  `supervisor/orchestrator.py::_loop` (the `resolve_session(` call),
  `supervisor/terminal_identity.py::_spawn_role`, `fsm_compose.py::build_prompt`
  (`agent_role`), `fsm_compose_tables.py::_SKILL_AGENT_ROLE`
- `src/pathly_data/core/adapters.yaml` (`resume` per adapter)
- `tests/runner_supervisor/test_supervisor.py` (`_na`, `_cs_next`, `_cs_done` and the session
  continuity tests)

## Answer
