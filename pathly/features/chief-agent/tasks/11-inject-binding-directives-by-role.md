# Keep binding decisions in the prompts of the roles they target

Type: task
Status: open
Blocked by: —
Test first: yes

Today a decision reaches worker prompts only while it is `pending`: `retrieve_board_context`
fetches `get_pending_decisions`, and `/comms/acknowledge` sets the row `active`, so the next
prompt no longer carries it. A standing order has to survive that.

- Schema: add `("comms_messages", "binding", "INTEGER NOT NULL DEFAULT 0")` to the column list in
  `db/migrations_incremental._add_additive_migrations`. Existing rows read 0. The board mirror
  exports and hydrates whole rows, so the column round-trips with no mirror change.
- Query: new `db/queries/comms_directives.py::get_binding_decisions(conn, boards, scopes, role)`
  returning rows with `type = 'decision'`, `binding = 1`, any `status`, `deleted_at IS NULL`,
  `superseded_by` NULL or empty, and `to_agent` equal to `role` or `'*'` (only `'*'` when `role`
  is empty), oldest first. Static SQL with `board IN (SELECT value FROM json_each(?))` and the same
  for scopes, the list passed as one JSON string; no f-strings, no `# nosec`. Nothing in the repo
  uses `json_each` yet; SQLite builds it in by default since 3.38.0 (map.md § Decisions so far,
  docs: SQLite JSON functions).
- Merge: new `runner/comms_governance.py::governance_decisions(conn, boards, scopes, role,
  project_scope)`: the pending decisions as today plus the binding ones for `role` from the given
  boards and, always, from the project board (`project`, `project_scope`) even when the project
  tier is off for this role; de-duplicated by id, each binding row marked so the formatter can tell.
- `runner/comms_context.py::retrieve_board_context` gains `role: str = ""` and calls
  `governance_decisions` where it now calls `get_pending_decisions`. `board_context_for` passes its
  `role` on. `comms_context.py` is at 394 lines: move code out (for example into
  `comms_governance.py`) so it stays at or under 400.
- `runner/comms_formatters._format_decision` renders a binding row as a standing directive, for
  example `- [project] BINDING for builder: <text>` (`for all roles` when `to_agent` is `*`).
- Callers: `fsm_compose.build_prompt` passes `role=agent_role`; `supervisor/task_prompt.py` passes
  `role=_TASK_ROLE` to `board_context_for`. `board_run.py` already passes `role=agent`.

Living docs: the governance part of "Prompt assembly" in `src/pathly_orchestrator/CLAUDE.md`
says binding decisions stay in prompts after acknowledgement and are filtered by role.

## Not in this ticket

- Posting a binding decision (`POST /comms/directives`) and refusing edits of one: ticket 12.
- Re-queueing a stage that finished across a newer directive: round two.

## Done when

- `python -m pytest tests/comms_board/test_binding_directives.py -q -p no:cacheprovider` passes
  and covers, with rows inserted through `post_message` and `binding` set directly: an
  acknowledged binding decision for `*` appears in `retrieve_board_context(..., role="builder")`
  and for `reviewer` and `tester`; one for `builder` appears for the builder only; a superseded
  or deleted one appears for nobody; an acknowledged non-binding decision appears for nobody (as
  today); a project-board directive still appears when the project tier is off; the migration runs
  twice; `fsm_compose.build_prompt` for the `team/build`, `team/review` and `team/test` agents
  carries an acknowledged `*` directive's text.
- `python scripts/check_file_size.py` and `bandit -q -r src/pathly_orchestrator -ll` exit 0.

```check
$ python -m pytest tests/comms_board/test_binding_directives.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
$ bandit -q -r src/pathly_orchestrator -ll
exit 0
```

## Reference

- spec.md § Decisions ("Directive reach"), § Edge cases
- map.md § Decisions so far (docs: SQLite JSON functions, `json_each`)
- `src/pathly_orchestrator/db/queries/comms_messages.py::get_pending_decisions` (the pending query;
  note its `# nosec` placeholder style is not to be copied)
- `src/pathly_orchestrator/fsm_compose.py::build_prompt`, `fsm_compose_tables._SKILL_AGENT_ROLE`
- Previous plan's directive design: `git show 72292b35:pathly/features/chief-agent/tasks/07-binding-directives.md`
  (read-only)

## Answer
