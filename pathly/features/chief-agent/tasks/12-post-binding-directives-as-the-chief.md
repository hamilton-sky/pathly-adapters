# Let the chief post a binding directive, and never edit one in place

Type: task
Status: resolved
Blocked by: 03, 08, 11
Test first: yes

Add `POST /comms/directives` in a new `blueprints/comms/directives.py` (added to
`blueprints/comms/__init__.py::all_blueprints`), the only write path that sets `binding = 1`.

- Body `{project_root, to_agent, text}`. `to_agent` is `*` or a role name (`^[a-z][a-z0-9_-]{0,39}$`),
  `text` a non-empty string of at most 8 KiB; 400 otherwise.
- Caller: only a live run with role `chief` per `caller_identity(request)`. The chief gate has
  already checked that the session's tier has `decide` and that `project_root` is the session's
  project. Everything else is 403: no token, a builder or any other role's token, and a token-less
  request that carries the server secret (what Studio sends today). This is the brief's pending
  default: the "(or the UI)" path waits for the UI token (RRP-2b), because until then the server
  cannot tell Studio from any local process that reads the server secret file. If the user replaces
  the default, the other option is in map.md § Open questions ("Directives from the UI").
- Write: `db/queries/comms_directives.py::post_directive(conn, scope, to_agent, text, **author)`
  calls `post_message(board="project", scope=scope, from_agent="chief", to_agent=to_agent,
  type="decision", text=text, **author)` and then sets `binding = 1` on that row under
  `_get_write_lock`. `scope` is the project board scope
  (`fsm_compose.resolve_board_scope("project", project_root, "")`), `author` is
  `stamp(caller_identity(request))`. Return 201 `{id}` and broadcast the same `COMMS_UPDATE` that
  `comms_post` sends for a new row, through `sse._broadcast_comms`.
- A directive is replaced with the existing `/comms/supersede`, which the gate maps to `decide`.
  Ticket 16 makes the chief the only caller that may retire one.

Refuse in-place edits: `/comms/edit` on a row with `binding = 1` returns 409
`{"error": "binding directives are superseded, not edited"}` and changes nothing.
`messages_crud.py` is at 395 lines on master (#63) and ticket 03 keeps it there. Put the check in
the db layer: `update_message_text` (or `comms_edit.py`, if ticket 03 moved it) returns
`"binding"` for a binding row, and the route maps it to the 409 in the line it already uses for
`not_found`, so the file does not grow.

`/comms/post` keeps ignoring a `binding` field in its body; add a test that proves it.
`messages_write.py` is at exactly 400 lines, so this ticket does not touch it.

Living docs: `src/pathly_orchestrator/CLAUDE.md` lists `POST /comms/directives` under "Comms
board endpoints" (chief token only) and the edit refusal; the root `CLAUDE.md` comms domain line
names `directives`.

## Not in this ticket

- A path for Studio to post a binding directive: waits for the UI token (RRP-2b), a later plan.
- Refusing supersede, delete and `supersedes` on binding rows for everyone but the chief, and
  hydration: ticket 16.
- The `pathly decide --binding` command: round two (map.md § Round two).

## Done when

- `python -m pytest tests/comms_board/test_comms_directives_route.py -q -p no:cacheprovider`
  passes and covers: an operator chief token posts a directive (201) and the row has `binding = 1`,
  `type = "decision"`, `from_agent = "chief"`, `author_role = "chief"`, `author_source = "token"`;
  a planner chief token is 403 (gate); a builder token, a request with no token and no secret, and
  a request with no token and the right `X-Pathly-Secret` are all 403 and store nothing; a bad
  `to_agent` is 400; `/comms/edit` on the directive is 409 and the text is unchanged;
  `/comms/post` with `binding: 1` stores 0; `/comms/supersede` by the operator removes the old
  directive from `get_binding_decisions`.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/comms_board/test_comms_directives_route.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- spec.md § Decisions ("Binding directives", "Who may post a directive"), § Interfaces
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py::comms_post` (broadcast
  shape; read-only)
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py::comms_edit`,
  `comms_supersede`
- `tests/http_api/test_http_server.py` (how tests set `middleware._api_secret`)

## Answer

**Built**

- `http_server/blueprints/comms/directives.py` (new, 122 lines): `POST /comms/directives`, in `all_blueprints` through `comms/__init__.py` (`directives_bp`). Order of checks: `caller_identity(request)` must be a live run with role `chief` (else 403 `only a chief may post a directive`, before the body is read); then 400 for a body that is not a non-empty object, a blank or non-string `project_root`, a `to_agent` that is not `*` or `[a-z][a-z0-9_-]{0,39}` (`fullmatch`), or a `text` that is not a string, is blank, is over 8192 UTF-8 bytes after `strip()`, holds a control character other than newline and tab, or cannot be encoded (a lone surrogate). The write is `post_directive(get_db(), resolve_board_scope("project", project_root, ""), to_agent, text.strip(), **stamp(caller_identity(request)))`, then the `COMMS_UPDATE` that `comms_post` sends (through `sse._broadcast_comms`), then 201 `{id}`.
- `db/queries/comms_directives.py` (+29 lines): `post_directive(conn, scope, to_agent, text, **author)` calls `post_message(board="project", scope=scope, from_agent="chief", to_agent=to_agent, type="decision", text=text, **author)` and sets `binding=1` in a second statement, both under `_get_write_lock`. It is the only place in `src/` that writes `binding = 1`.
- `db/queries/comms_edit.py`: `update_message_text` selects `binding` and returns `"binding"` for a `binding = 1` row before it writes anything (text and the three author columns stay as they were).
- `blueprints/comms/messages_crud.py` (396 to 398 lines): `if result == "binding": return jsonify(error="binding directives are superseded, not edited"), 409`. `messages_write.py` is untouched (400 lines): `/comms/post` already ignored `binding`, and a test now proves it.
- `http_server/chief_field_calls.py`: `("/comms/directives", "POST")` with `roots=_ROOT` and keys `to_agent` (NAME) and `text` (TEXT). `chief_routes.py` already held `("/comms/directives", "POST"): "decide"` (ticket 03 planned it), so the action table is unchanged; this ticket added the field entry the gate needs, and `PLANNED` in `tests/http_api/chief_gate_support.py` is now empty.
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (the `POST /comms/directives` line, the `/comms/edit` 409, the `decide` row and the chief-gate paragraphs no longer say the route is coming, the "Not enforced yet" paragraph now says what ticket 16 still has to do, layout entries for `comms_directives.py`, `comms_edit.py`, `comms/directives.py`), root `CLAUDE.md` (the comms domain line names `directives`), `docs/WHAT_IS_PATHLY.md` (one stale sentence about nothing setting `binding = 1`). Docstrings of `tests/comms_board/binding_support.py` and `test_binding_directives.py` said no route writes `binding`; now accurate. `db/migrations_incremental.py` was checked and already says the right thing. `map.md` (one line under Decisions so far) and `learnings.md` (five lines): appended only.
- Tests: `tests/comms_board/test_comms_directives_route.py` (41), `test_comms_directives_fields.py` (58), `test_comms_directives_query.py` (11), `directives_support.py` (helpers); five existing `tests/http_api` chief-gate files got the new route in their lists (`chief_gate_support.py`, `test_chief_gate_actions.py`, `test_chief_gate_strict_keys.py`, `chief_audit_calls.py`, `test_chief_gate_audit.py`); `tests/INDEX.md` and `tests/comms_board/INDEX.md` regenerated.

**Proof** (everything below run fresh after the last source edit; Python 3.12.3 venv unless stated)

- Test first: commit `25077eb` holds only test files. Run against that tree (a throwaway `git worktree` at `25077eb` with `PYTHONPATH=<worktree>/src`, `pathly_orchestrator.__file__` printed from it): the three new files gave `94 failed, 7 passed` (the route does not exist, so nearly all of them are a 404 where a 201, 400, 403 or 409 was expected; the query-file failures are the missing `post_directive` and the edit not answering `"binding"`), and the chief-gate files gave `3 failed, 190 passed` (`test_every_listed_rule_exists` fails on a route in the lists that does not exist, plus `test_a_status_chief_is_refused_each_listed_route_by_its_action[/comms/directives]` and the strict-keys case for it). The 7 that pass on base code are the guards of behaviour that must not change: `/comms/post` ignores `binding` (4 values, plus the chief token being gated off `/comms/post`), a closed chief session posts nothing, an edit of a missing message is still 404. They pass with and without the change by design.
- Done when 1, `python -m pytest tests/comms_board/test_comms_directives_route.py -q -p no:cacheprovider`: `41 passed in 10.52s`, exit 0. It covers each clause: operator chief token posts (201), stored row `binding = 1`, `type = "decision"`, `from_agent = "chief"`, `author_role = "chief"`, `author_source = "token"`, board `project`, scope the normalised root; a `planner` chief token 403 (and `status`); a builder token (and the other roles, `human` included), no token and no secret, and no token plus the right `X-Pathly-Secret` (curl and with the Studio `Origin`) are all 403 and store nothing; a closed session's token is 401; another project's root is gated; a bad `to_agent` is 400 (in the fields file, 58 cases); `/comms/edit` on a directive is 409 for an anonymous caller and for a builder token, with the text and the author columns unchanged, and a chief token is gated off `/comms/edit`; `/comms/post` with `binding` as 1, true, `"1"` and 2 stores 0; `/comms/supersede` by the operator removes the old directive from `get_binding_decisions`; a directive for `builder` reaches the governance block rendered for the builder, in the standing-orders part, and the one for `reviewer`, `tester` and an empty role not at all; the broadcast is a `COMMS_UPDATE` carrying `message_id`, `board`, `scope` and `msg_type`, and nothing else is queued.
- Done when 2, `python scripts/check_file_size.py`: `OK: 1031 source files checked; 18 known over 400 lines, none new, none grown.`, exit 0.
- `Build` `python -m build --wheel`: exit 0 (`pathly_adapters-2.24.1-py3-none-any.whl`). `Smoke` (the `python -c "import ..."` of `commands.md`): exit 0.
- `Test` of `commands.md` (`python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`): `3319 passed, 2 skipped in 792.00s (0:13:12)`, exit 0. The 2 skips are not mine (no skip added; `git diff` and the test-first commit hold no `skip`, `xfail`, `noqa`, `nosec` or `type: ignore`).
- `Lint` of `commands.md`, the whole `&&` chain as one command: exit 0 (`black --check src/ tests/` unchanged, `mypy` no issues in 336 source files, `check_file_size` as above, `check_no_mirror_reads`, `gen_test_index.py --check` up to date, `lint-imports` 1 kept 0 broken, `bandit -q -r src/ -ll -x src/pathly_data/` nothing at medium or above, `check_adapters`, `check_entry_points`).
- Python 3.13.16 (`venv313`, repo editable install): the three new files, `test_binding_directives.py`, `test_binding_directive_hardening.py`, `test_comms_edit_restamp.py`, `test_comms_write_perm.py`, `test_comms_provenance.py`, `test_comms_supersede.py` and the eight `tests/http_api/test_chief_gate*.py` files: `714 passed, 1 warning in 372.46s`, exit 0 (the warning is torch's, about a CUDA kernel registration). I did not run Python 3.11 (no dependencies installed for it here); CI runs 3.11, 3.12 and 3.13 on ubuntu only. The new code uses nothing newer than 3.11 (`str | None` under `from __future__ import annotations`, `re.fullmatch`).
- Mutation check (a scratch script, every edit reverted in `finally`, `git status` clean after): 15 mutations over the route, the query, the edit refusal, the field entry, the board, the sender and the scope. All KILLED except one: dropping `roots=_ROOT` from the field entry, because the gate checks a `project_root` that is present whatever the entry says (the entry is redundant, not wrong). The call-site scan that makes up for the provenance allow-list entry was mutation-tested as well.
- Floor guard, after the feature commit: `FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 12 30852f7a46557e27cc381dd1d7da4338ead26c83` printed `floor guard: clean`, exit 0.

**Decisions**

- The route owns the role check (403 for everything but a chief run token); the chief gate owns the tier (`decide`) and the project binding, as the ticket says. The route does not repeat the gate's `project_root` check.
- `names_root` is NOT set on the field entry. The flag means "falls back to another directory when the body names no root", and `test_every_route_that_starts_an_agent_in_a_directory_names_its_root` pins it to the run, decompose and `/code/query` routes. This route 400s on a body without `project_root`, so there is no fallback. I had set it first and that test failed.
- `to_agent` is validated, not normalised: `Builder` and ` builder ` are 400, because role matching is exact and a normalised value would hide the typo. The text is stored stripped.
- Control characters are refused (everything in C0 and C1 except tab and newline, `\r` included): a NUL in a standing order makes `subprocess` raise for every spawn of the role (checked: `ValueError: embedded null byte`), and SQLite would have stored it.
- The 409 check lives in the db layer (`update_message_text`), as the ticket asked, so `messages_crud.py` grew by two lines only.
- `post_directive` forwards `**author` and takes no identity itself, so `db/` stays below `runner/`. The provenance tripwire (`tests/comms_board/test_comms_provenance.py`) accepts only a literal stamp expression, so `db/queries/comms_directives.py` is on its allow-list `_UNSTAMPED_ALLOW` with the reason, and `test_comms_directives_query.py::test_every_call_of_post_directive_passes_the_request_stamp` scans every call of `post_directive` under `src/` for `**stamp(caller_identity(request))` (with tests that the scan catches a missing and a wrong stamp). This is a loosening of an existing test, made on purpose and offset by the new scan; the second commit also edits two of my own test-first files (`directives_support._rows` counts only `type='decision'` rows after a full run showed a leaked `board-run-*` thread posting into a later test's database; the no-project test was split into the 400 case and the gate-403 case).

**Shortcuts taken**

- Between `post_message`'s commit and the `binding=1` UPDATE a plain decision row exists. The write lock keeps other writers in the process from seeing it, but a crash or a DB error between the two statements leaves an ordinary non-binding decision (and a 500 to the caller). `post_message` has no `binding` parameter and I did not add one (`comms_messages.py` is outside this ticket).
- The route does not call `check_write_permission` (the per-project write-permission table); it relies on the gate's `decide` action and the chief role.
- `to_agent` accepts any lowercase name, including a role that does not exist and `human`; nothing checks it against the roles.
- A CRLF text from a Windows chief is refused (400), not converted.
- There is no cap on the number of standing orders or the total size of the standing-orders block; the 8 KiB cap is per text. 300 orders of 8 KiB would still make a block near 2.4 MB, over a Linux argv string limit (128 KiB), as learnings (11) said. Ticket 16 or a later one should budget the block.
- The chief gate sees `project_root` before the route; the route repeats no check that it equals the token's project, so a bypass of the gate would not be caught in the route.

**For later tickets**

- Ticket 16 (refusing supersede, delete and `supersedes` on binding rows for everyone but a chief, and hydration): `/comms/supersede`, `/comms/delete` with `force` and `/comms/post` with `supersedes` still accept a binding row from any caller the gate lets through; I did not touch them. `test_comms_directives_route.py::test_the_operator_replaces_a_directive_with_supersede` is the current behaviour for the operator and should stay green. Hydration still stores a `BOARD.json` row's `binding` as given (see the (11) lines of `learnings.md`); the only writer of `binding = 1` is now `post_directive`, so hydration can store 0.
- `post_directive` returns the id and leaves `status` at `pending` (what `post_message` sets); a directive is read whatever its status.
- The "(or the UI)" path for Studio waits for the UI token (RRP-2b); `map.md` § Open questions ("Directives from the UI") still holds the other options.

**Minors noticed, not fixed**

- `get_pending_decisions` and `get_active_escalations` build SQL with f-strings and `# nosec B608` (pre-existing, from ticket 11's notes).
- `bandit` prints `Test in comment: ... is not a test name or id, ignoring` warnings for comments in `src/` (pre-existing; the run exits 0).
- The 2 skipped tests of the Test command are pre-existing.
