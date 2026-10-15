# Open a fresh CLI session for the reviewer instead of resuming the builder's

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/fsm_compose_tables.py`: `agent_role_of(agent)` (`_SKILL_AGENT_ROLE.get(agent)`, else the last `/` segment).
- `src/pathly_orchestrator/fsm_compose.py` (`build_prompt`, 390 -> 386 lines) and `src/pathly_orchestrator/supervisor/terminal_identity.py` (`_spawn_role`) call the helper instead of their inline copies.
- `src/pathly_orchestrator/supervisor/orchestrator_session.py`: `INDEPENDENT_ROLES = frozenset({"reviewer"})`; `resolve_session(..., stage_agent="")` returns `session_id=None` when `agent_role_of(stage_agent)` is in it (imported inside the function), and the `SESSION` event carries `independent`.
- `src/pathly_orchestrator/supervisor/orchestrator.py`: `_loop` passes `response.get("agent", "")` as the fifth argument; the argument line is 86 characters, the call stays three lines, the file is still 399 lines.
- `src/pathly_orchestrator/CLAUDE.md`: control diagram step 3, the `orchestrator_session.py` package-structure line, the "Same-adapter consecutive stages share a `session_id`" paragraph under "Visible runner", the `SESSION` row of the SSE table, and the "Limits" sentence in the Review packet section that said a same-adapter REVIEWING stage still resumes the builder's session.
- `tests/runner_supervisor/test_reviewer_fresh_session.py` (7 tests) plus the regenerated `tests/INDEX.md` and `tests/runner_supervisor/INDEX.md`. The test-only commit came first (`test(build-proof): 16 failing test`): 5 of 7 failed there, for the missing helper, the missing fifth argument, and the reviewer spawn getting `builder-sess`.

**Proof**

- `python -m pytest tests/runner_supervisor/test_reviewer_fresh_session.py -q -p no:cacheprovider`: `7 passed`, exit 0. Through `start_run` with `next_action`, `complete_stage` and `_run_stage_via_terminal` patched: BUILDING (`team/build`) then REVIEWING (`team/review`), both claude, gives spawn sessions `[None, None]` with the builder returning `builder-sess`, and the REVIEWING `SESSION` event has `kind` `opened`, `independent` true, `degraded` false; BUILDING, REVIEWING, TESTING (`team/test`) gives `[None, None, "reviewer-sess"]` and kinds `opened, opened, continued`; BUILDING, BUILDING gives `[None, "builder-sess"]`; `agent_role_of` gives `reviewer` for `team/review` and `quality/reviewer`, `builder` for `builder`. Three direct `resolve_session` tests cover: no `stage_agent` still continues, an independent role gets `None` with `autonomy` and `adapter_supports_resume` unchanged, and an adapter with no `resume` (copilot) still reports `degraded` true.
- `python -m pytest tests/runner_supervisor/test_supervisor.py tests/fsm_flows -q -p no:cacheprovider`: `696 passed, 9 skipped`, exit 0 (the skips are not mine).
- `python scripts/check_file_size.py`: `OK: 1008 source files checked; 19 known over 400 lines, none new, none grown.`, exit 0; `orchestrator.py` is 399 lines.
- Beyond the Done when, run fresh after the last code edit: the full Test command `python -m pytest tests/ -q -x -p no:cacheprovider` gave `2907 passed, 14 skipped`, exit 0; the Lint chain (black, mypy, check_file_size, check_no_mirror_reads, `gen_test_index.py --check`, lint-imports, bandit, check_adapters, check_entry_points) exited 0; Smoke and `python -m build --wheel` exited 0.

**Decisions**

- The `SESSION` event always carries `independent` (a bool), not only when true, so a consumer reads one shape; no test or Studio code reads that event's other keys. While in the SSE table row I also corrected its stale field list (`session_id` is not in the payload; `topic`, `adapter`, `kind` `opened`/`continued` and `degraded` are).
- `agent_role_of` is `_SKILL_AGENT_ROLE.get(agent) or agent.split("/")[-1]`. The old `build_prompt` code branched on `"/" in agent`, but `split("/")[-1]` of a name without a slash is the name, so the two agree for every input.
- The no-resume test uses `copilot`: in `core/adapters.yaml` only `copilot` and `antigravity` have `resume: null`; `codex` resumes with `--continue`.
- I also changed the stale "Limits" sentence in the Review packet section of `src/pathly_orchestrator/CLAUDE.md`, which the ticket's list of four docs did not name but which the change made false.

**Shortcuts taken**

none

**For later tickets**

- `fsm_compose_paths.resolve_stage_out_path` still has the same role mapping written inline (`_SKILL_AGENT_ROLE.get(agent)`, else `split("/")[-1]`); the ticket counted two copies and named them, so it was left alone. Replacing it with `agent_role_of` is a two-line follow-up.
- Only the reviewer's stage is independent. The stage after REVIEWING continues the reviewer's session, not the builder's (spec.md Risks); restoring the builder's session needs a second slot in `RunnerState` and a change in `orchestrator.py`, which has one line left.
- No other ticket is made wrong by this one.
