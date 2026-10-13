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
  exports whole rows, so `binding` appears in `BOARD.json`; hydration must not trust it, and
  ticket 16 makes it store 0.
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
  `role` on. `comms_context.py` is at 370 lines since #63; keep it at or under 400 (move the
  merge into `comms_governance.py` as above).
- Render: since #63 one function, `runner/comms_formatters.render_governance_lines(decisions,
  escalations)`, renders governance for both the flow path (`comms_context.py`) and board runs
  (`supervisor/board_run.py`). It sorts decisions by tier, then newest first, and tells the agent
  "the one listed FIRST wins" and "to replace one, post a decision with `supersedes`". A binding
  row must sit outside that rule, so a newer ordinary decision cannot outrank a standing order in
  the prompt. Render binding rows in their own block before the decisions, for example
  `**Standing orders (binding; a newer decision does not override them):**` with one line per row,
  `  • BINDING for builder: <text>  [id: …]` (`for all roles` when `to_agent` is `*`), and leave
  them out of the ranked list. The block says only the human, through the chief, replaces a
  standing order, and drops the "post a decision with `supersedes`" hint for these rows.
  `comms_formatters.py` is at 305 lines.
- Callers: `fsm_compose.build_prompt` passes `role=agent_role`; `supervisor/task_prompt.py` passes
  `role=_TASK_ROLE` to `board_context_for`. `board_run.py` already passes `role=agent`.
- Role names: `agent_role` comes from `fsm_compose_tables._SKILL_AGENT_ROLE`, which knows six
  skills. A stage whose skill is not in it (for example quick-fix or debug FIXING) composes with
  an empty role and gets only `*` directives. That is the safe direction (no directive leaks to
  the wrong role), but a `builder` directive then misses a fixer. Say so in the living doc, and
  add a test that pins the empty-role behaviour so a later change to the table is deliberate.

Living docs: the governance part of "Prompt assembly" in `src/pathly_orchestrator/CLAUDE.md`
says binding decisions stay in prompts after acknowledgement and are filtered by role.

## Not in this ticket

- Posting a binding decision (`POST /comms/directives`) and refusing edits of one: ticket 12.
- Who may retire one, and hydration storing `binding = 0`: ticket 16.
- Re-queueing a stage that finished across a newer directive: round two.

## Done when

- `python -m pytest tests/comms_board/test_binding_directives.py -q -p no:cacheprovider` passes
  and covers, with rows inserted through `post_message` and `binding` set directly: an
  acknowledged binding decision for `*` appears in `retrieve_board_context(..., role="builder")`
  and for `reviewer` and `tester`; one for `builder` appears for the builder only; a superseded
  or deleted one appears for nobody; an acknowledged non-binding decision appears for nobody (as
  today); a project-board directive still appears when the project tier is off; the migration runs
  twice; `fsm_compose.build_prompt` for the `team/build`, `team/review` and `team/test` agents
  carries an acknowledged `*` directive's text; the directive renders in the standing-orders
  block and not in the ranked decision list, and a newer ordinary project decision on the same
  topic is listed below it without displacing it; a board-run prompt (`board_run.py`) renders the
  same block; a prompt composed with an empty role carries `*` directives only.
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
- `src/pathly_orchestrator/runner/comms_formatters.py::render_governance_lines` and
  `tests/comms_board/test_governance_decision_precedence.py` (#63; keep it passing)
- Previous plan's directive design: `git show 72292b35:pathly/features/chief-agent/tasks/07-binding-directives.md`
  (read-only)

## Answer
