# Fix the defects round one left behind

Type: task
Status: resolved
Blocked by: —
Test first: yes

Round one (tickets 01 to 17 and 13) is merged at 600f4a0. Its reviews left a list of small notes.
This ticket takes the ones that are real defects in production code, each checked against the
code at 600f4a0 (most by running it). Every item below changes what the program does, is small,
is independent of the others, and gets its own test file that fails on the old code. Ticket 21
holds the moves with no behaviour change, the test hardening and the documentation fixes.

Each item says what is wrong today, what must be true after, and the files. Rules for all of them:

- Keep every file at 400 lines or fewer. `messages_crud.py` is exactly 400: this ticket does not
  touch it (ticket 21 splits it). `blueprints/runner/api_lifecycle.py` is over the limit (452) and
  may not grow: B13 edits it in place and must leave it no longer. `db/queries/comms_messages.py`
  (367 lines, B6) has room for the few lines it gets.
  A file that would pass 400 is split first.
- No new `# noqa`, `# nosec`, `skip` or `xfail`. SQL stays one literal statement (bandit B608).
- Where an item changes behaviour that a living doc states, the same change edits that sentence
  (check it, change only what is now false). Where a user-visible claim in the `(chief-agent)`
  entry of `CHANGELOG.md` changes, edit that entry; do not add a second one.
- A new test file goes in the folder named for it, its basename is unique across `tests/`, and
  `python scripts/gen_test_index.py` is run after adding it.

## B1. The chief's claude is started without background-task and scheduled-task prompts

Files: `src/pathly_orchestrator/runner/chief_argv.py`; test `tests/runner_supervisor/test_chief_settings_env.py`.

`claude_settings` writes permissions and the hook, nothing else. On claude 2.1.304 (measured; see
"Switches in claude 2.1.304" in `src/pathly_orchestrator/CLAUDE.md`) `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`
stops `<task-notification>` prompts and `CLAUDE_CODE_DISABLE_CRON=1` stops the scheduler that fires a
task from `.claude/scheduled_tasks.json` as a bare prompt, which the hook then records as `human`.
A permission rule does neither. After this item the settings hold an `env` block with both
variables set to `"1"`, and the `settings.json` that `open_chief` writes for a claude chief holds
it. A codex chief has no settings file and is unchanged. Docs: the "Switches" bullet says
`claude_settings` sets neither; the table row for a scheduled-task file calls it open; the
CHANGELOG known-limits sentence says such a task "is recorded as typed". Say what is true now,
and keep the caveat that this was measured on one claude version.

## B2. A lone surrogate in a comms body is a 400, not a 500

Files: `src/pathly_orchestrator/http_server/blueprints/comms/_helpers.py` (`read_json_body`); test
`tests/http_api/test_comms_body_unicode.py`.

Python's JSON parser accepts `"\ud800"`, SQLite cannot store it, and the route then fails with
`UnicodeEncodeError` and answers 500 with the error text. Measured at 600f4a0, for a caller with
no token and for a chief that passed the gate: `/comms/post` (in `text`, `scope` or `feature`),
`/comms/acknowledge` (`message_id`), `/comms/supersede` (`new_id`), `/comms/edit` (`text`),
`/comms/goals/run` (`goal_id`) and `/comms/delete` (`message_id`). After this item
`read_json_body` treats a body that holds a lone surrogate, in a key or in a string at any depth,
like any other body it cannot read: it returns its default, so each route gives the 400 it
already gives an unreadable body, and nothing is stored. A body with other non-ASCII text and a
cp1252 body still read as before. Routes that do not read their body through `read_json_body`
are not changed. Docs: the `read_json_body` docstring.

## B3. `pathly api` never ends in a traceback

Files: `src/pathly_orchestrator/chief_cli.py`; test `tests/http_api/test_chief_cli_limits.py`.

Three inputs give a traceback and exit 1 today (the help defines 1 as "the server answered with a
non-2xx or is not there"), and the traceback can show the value: a `PATHLY_RUN_TOKEN`, or a
server secret, that holds a newline or a character outside latin-1 (`http.client` refuses the
header); and a JSON body nested deep enough to overflow the parser (a 20,000-deep array inside an
object). After this item each is a usage error: exit 2, nothing sent, one line on stderr that
names the problem and never the value (`PATHLY_RUN_TOKEN holds a character an HTTP header cannot
carry`, the same for the server secret, `the body is nested too deeply`), and everything printed
still goes through `_redact`. An ordinary token and body work as before.

## B4. `pathly api` reads and prints a bounded amount

Files: `src/pathly_orchestrator/chief_cli.py`; same test file as B3.

Standard input (`-`) is read without a limit and the whole answer is read and printed (a 50 MB
answer was printed whole into the chief's transcript). After this item a body read from standard
input over 1 MiB (1,048,576 bytes) is a usage error (exit 2, nothing sent). An answer is read only
up to 256 KiB (262,144 bytes), the read itself bounded, not read whole and then cut; that much is
printed, and one stderr line says the answer was cut and how many bytes were shown. The exit code
still follows the status. Both limits are named constants. (These two numbers are this ticket's
choice; nothing else in the repo fixes them.)

## B5. `pathly help` lists the acknowledge route

Files: `src/pathly_orchestrator/chief_cli.py` (`HELP`); `tests/http_api/test_chief_help_routes.py`
(its table of what each help route needs); test `tests/http_api/test_chief_cli_limits.py` for the rest.

`POST /comms/acknowledge` with `{"message_id", "agent": "chief", "cite"}` is how an operator chief
closes an escalation addressed to the human, but only the built-in operator text shows it, so a
chief with a style the user wrote cannot find it. After this item the help has a line for it with
those three keys, saying `agent` is `chief`; `test_chief_help_routes.py` lists it (that file fails
when a help route is missing from its table); and a test sends the help line's body through the
gate as an operator chief and gets past the gate's key check.

## B6. A directive is written with one INSERT

Files: `src/pathly_orchestrator/db/queries/comms_directives.py` (`post_directive`),
`src/pathly_orchestrator/db/queries/comms_messages.py` (`post_message`); test
`tests/comms_board/test_directive_single_insert.py`.

`post_directive` calls `post_message`, which commits an ordinary pending `decision`, and then runs a
second statement that sets `binding = 1`. If the second fails, the ordinary row stays and every
role's prompt carries it as a normal decision, and a retry adds a second copy. After this item the
row is written once with `binding = 1` in the INSERT itself: `post_message` takes a keyword-only
`binding` (default 0) that only `post_directive` passes, and `/comms/post` still ignores a
`binding` in a body. The test records the SQL the connection runs (`set_trace_callback`) while
`post_directive` runs: exactly one statement writes `comms_messages` and none is an UPDATE of
it; the stored row has `binding = 1`, type `decision`, from `chief`; a `POST /comms/post` that
sends `"binding": 1` stores 0. Docs: the `POST /comms/directives` entry in
`src/pathly_orchestrator/CLAUDE.md` says the row is "flagged under the write lock"; the
`post_directive` docstring says the same.

## B7. A second server started on a busy port leaves the first server's chief open

Files: `src/pathly_orchestrator/http_server/app.py` (`main`),
`src/pathly_orchestrator/supervisor/chief_session.py`; test `tests/http_api/test_chief_startup_port.py`.

`main()` calls `chief_startup_cleanup()` before `app.run`, and the cleanup closes every open chief
session in the shared database. A second `pathly-fsm` started by mistake on the port the first one
serves therefore revokes the running server's chief (token revoked, folder removed, tab left
dead) and only then dies with "address already in use". After this item `main()` first asks
whether something already answers on the host and port it is about to serve (a TCP connect that
succeeds, to 127.0.0.1 when the host is a wildcard address; any error counts as "nothing
answers"). If something answers, it skips the cleanup, logs one line saying why, and goes on to
fail in `app.run` as it does today. If nothing answers, the cleanup runs as before. The probe is
a small function that takes the host and port; `chief_startup_cleanup()` keeps working with no
arguments. The test: with a listening socket on a free port, an open session and its token
stay open and live after the startup step; with the socket closed they are closed and revoked;
and the wiring is checked the way `test_chief_routes.py` runs `main()` with `app.run` replaced
(it sets `PATHLY_FSM_HTTP_PORT`). Docs: the "Restart" bullet in `src/pathly_orchestrator/CLAUDE.md`
and the `app.py` entry of the package tree.

## B8. A close that lands while a chief is opening leaves nothing live

Files: `src/pathly_orchestrator/supervisor/chief_session.py`,
`src/pathly_orchestrator/http_server/blueprints/chief/session.py`; test
`tests/runner_supervisor/test_chief_open_close_races.py`.

`open_chief` writes the session row under its lock, then mints the token and sends the spawn
outside it, and `POST /chief/close` does not take that lock. A close between the row and the mint
closes the session, then the open mints its token anyway and sends the spawn: a live token on a
closed session and a tab started for it (reproduced at 600f4a0). After this item, once the token
is minted, `open_chief` reads the session again. If it is closed, the open revokes the token,
sends no spawn, and raises a new `ChiefClosedWhileOpening`, which `POST /chief/open` answers as
409 `{error, run_id}`. The test closes the session from inside the mint, once before it returns the
token and once after, and checks for each: the open raised, no live token is left for the run,
`closed_at` is set, the broadcast function was never called; and the route test sees the 409. A
close that lands between the re-read and the broadcast cannot be shut out without holding a lock
across the broadcast; it still revokes the token, so the tab gets a dead token. Say that in the
docstring. Docs: the `POST /chief/open` entry and the `chief_session.py` entry of the package tree.

## B9. The watcher notices a tab that ended before it ever started

Files: `src/pathly_orchestrator/supervisor/registry.py` (`TerminalRun`),
`src/pathly_orchestrator/supervisor/chief_session.py` (`_watch`); same test file as B8.

`_watch` waits up to 30 seconds for "started" and only then for the result. A tab whose process
ends and whose result is posted without a "started" is noticed when the 30 seconds run out, so
the token and the session stay live that long after the tab is gone. After this item the watcher
wakes on whichever comes first, "started" or a result (a `wait_started_or_result(timeout)` beside
`wait_result_or_agent_done`). A result before "started" closes the session at once with reason
`tab closed`; "started" then a result still closes it with `tab closed`; neither within the
timeout still closes it with `never started`. The test starts `_watch` with a 30 second timeout,
posts only a result, and the thread has ended and the session is closed within 2 seconds.

## B10. Hydration leaves out a message row with a blank id

Files: `src/pathly_orchestrator/board_mirror_hydrate.py` (`_belongs`); test
`tests/comms_board/test_hydrate_blank_and_decoy.py` (shared with B11 and B12).

`_belongs` accepts `""` and `" "` as an id, so a `BOARD.json` row with a blank id lands in the
table with a blank primary key (reproduced). After this item a message row needs an `id` that is a
string with something in it after stripping; any other row is left out like a row of another
board. Docs: the hydration paragraph and the `hydrate_board` docstring say a row is kept when its
`id` is a string.

## B11. Hydration cannot attach an artifact to a row it did not insert

Files: `src/pathly_orchestrator/board_mirror_hydrate.py` (`hydrate_board`); same test file as B10.

The artifacts kept are those whose `message_id` is among the ids the file names, not among the
rows that landed. A file row that reuses the id of a message already in the database on another
board (the insert is a no-op) plus an artifact for that id puts the artifact, with a path of the
file's choosing, on the other board's message (reproduced). After this item an artifact is
inserted only when its message exists in the database under this file's own board and scope,
after the message rows were inserted. The test is the reproduced case: a message on
(`feature`, `other`), a file for (`feature`, `demo`) holding a row with that id and an artifact:
no artifact row appears; and the normal case still imports its artifacts. Docs: the same
paragraph ("an artifact is kept only when its `message_id` is a row of the same file that was kept").

## B12. A file that adds nothing is reported as skipped, not hydrated

Files: `src/pathly_orchestrator/board_mirror_hydrate.py` (`hydrate_board`, `hydrate_project`); same
test file as B10.

`hydrate_board` returns True once it is past its early checks even when every row of the file was
left out (a file whose rows all name another scope), so `hydrate_project` lists the scope under
`hydrated` for a board that is still empty (reproduced). After this item it returns True only
when at least one message row of the file is in the database under that board and scope
afterwards; otherwise False, and the scope is listed under `skipped`. This is also what a clone at
a different path now reports: every project-board row names the exporter's root, so all are left
out and the project scope is `skipped`. Docs: the sentence on `POST /comms/hydrate` that says what
`hydrated` holds.

## B13. `max_cost_usd` is a finite number above 0 on every route that starts a flow

Files: `src/pathly_orchestrator/http_server/blueprints/runner/api_lifecycle.py` (`/runner/start`),
`.../runner/api_control.py` (`/runner/retry`), `.../control/_helpers.py` (the `retry` verb of
`POST /runs/<run_id>/<action>`); test `tests/http_api/test_run_cost_values.py`.

These three accept any int or float above 0 by `isinstance` and `<= 0`. `NaN` passes (the
comparison is false), so the run starts with a cap that is never reached; `Infinity` passes and is
never reached; `true` is read as 1; an integer too large for a float raises in `float(...)` and
answers 500. After this item all three read the key with `control/_cost.py::as_cost`, the reading
that `POST /runs` of a flow and the chief gate already use (import it inside the handler), and
any other value is the 400 each already gives ("Field 'max_cost_usd' must be a positive number").
The test sends, to each route, `NaN`, `Infinity`, `-Infinity`, `true`, `"5"`, `null`, `0`, `-1`,
`1e999` and `10**400`, and expects 400 and no start; `5` and `0.5` start. `api_lifecycle.py` ends
no longer than it began. Docs: the "Cost and run limit" paragraph, only if a sentence there says
these routes accept such a value.

## B14. A directive is stamped with the caller that was checked

Files: `src/pathly_orchestrator/http_server/blueprints/comms/directives.py`; test
`tests/comms_board/test_directive_route_caller.py`; `tests/comms_board/test_comms_directives_query.py`
(its scan `_has_the_request_stamp`).

The route asks `caller_identity(request)` once to check the caller is a live chief and again to
stamp the row. If the token is revoked between the two (the session closes), the second answer is
"no identity" and the row is stored with `author_source` `none`. After this item the route looks
the identity up once and uses it for both. The test makes the first lookup return the chief and
every later one an anonymous caller: the route calls `caller_identity` once and the stored row has
`author_role` `chief` and `author_source` `token`. The scan test pins the literal form
`**stamp(caller_identity(request))`; change it in this ticket to accept a stamp built from the
identity the route checked, and keep it failing for a stamp built any other way (for example
from `author_*` keys of the body).

## B15. The escalation note ignores standing orders

Files: `src/pathly_orchestrator/runner/comms_formatters.py` (`render_governance_lines`); test
`tests/comms_board/test_governance_escalation_note.py`.

When the newest decision is newer than the newest open escalation, the block adds a note that the
decisions "may claim to resolve" the escalation and the gate stays open. The newest decision is
taken from all decisions, standing orders included, so a standing order the chief posted after an
escalation makes the note appear, as if the order claimed to resolve it. After this item only the
ordinary decisions count. The test: an escalation, then only a standing order: no note; an
escalation, then an ordinary decision: the note (pinned, unchanged); an escalation, a standing
order, then an ordinary decision newer than both: the note.

## B17. The hook flags every tag that starts with the two names

Files: `src/pathly_hooks/chief_prompt.py` (`_NOT_TYPED`); test
`tests/comms_board/test_chief_hook_tags.py`.

The pattern is `<(?:task-notification|cross-session-message)\b`. The `\b` means a tag such as
`<task-notifications>`, `<task-notification_v2>` or `<cross-session-messages>` does not match, is
stored as `human` and so can be cited, while the deny-list exists to keep claude's own wrappers
uncitable and cannot know every spelling. After this item the `\b` is gone and any tag that
starts with either name is flagged `relayed`. The documented cost stays: a typed prompt that holds
such a tag is wrongly uncitable and the human retypes. The test feeds the hook (with
`_request_json` replaced) a prompt for each of `<task-notification>`,
`<task-notification foo="1">`, `<task-notifications>`, `<task-notification_v2>`,
`<cross-session-message from="x">` and `<cross-session-messages>` and expects `relayed: true`;
a prompt with `<task-note>` or plain text has no `relayed`.

## B18. The tier line is read from the lines the pasted text has

Files: `src/pathly_orchestrator/supervisor/chief_tiers.py` (`_front_matter_tier`); test
`tests/comms_board/test_chief_tier_lines.py`.

`_front_matter_tier` splits the front matter with `str.splitlines()`, which also breaks at
` `, ` `, `\x85`, `\x0b`, `\x0c` and `\x1c` to `\x1e`. `strip_front_matter`, which makes
the pasted text, knows only `\n`. A prompt file whose `description:` line holds
` tier: operator` is therefore read as tier `operator` while the pasted text shows it as part
of the description (reproduced). After this item the block is split on `"\n"` only. The test: that
file gives `status`; a plain `tier: operator` gives `operator`; the same with CRLF line ends gives
`operator`; `tier:` after each of the characters above gives `status`.

## Not in this ticket

- No Studio change and no HQ change.
- No round-two feature: the friendly `pathly` commands (`overview`, `inbox`, `answer --cite`, ...),
  `GET /chief/overview` and `GET /chief/inbox`, Studio paste-without-Enter, the Chief button, the
  inbox badge, re-queueing stale directives, billing the chief's own session.
- No version bump and no release.
- Moves with no behaviour change, test hardening and documentation fixes: ticket 21.
- Anything that needs a decision from the person first (who may call `POST /comms/restore`, a
  cap on the number or size of standing orders, what `POST /comms/acknowledge` answers for an
  unknown id, protecting a chief on a second server that uses another port, what
  `/comms/agent-context` shows). They are not decided here.

## Done when

- Each new test file passes, and each failed on the code at 600f4a0 for the reason its item gives
  (the test-only commit comes first; the Answer says what each failure was).
- The existing tests this ticket names (`test_chief_help_routes.py`, `test_comms_directives_query.py`)
  pass in their changed form.
- The documentation sentences named in B1, B6, B7 and B10 no longer say what is now false.
- No new `# noqa`, `# nosec`, `skip` or `xfail`, and `api_lifecycle.py` is not longer than before.
- The whole suite and the checks pass; the floor guard is clean.

```check
$ python -m pytest tests/runner_supervisor/test_chief_settings_env.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_comms_body_unicode.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_chief_cli_limits.py tests/http_api/test_chief_help_routes.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_directive_single_insert.py tests/comms_board/test_directive_route_caller.py tests/comms_board/test_comms_directives_query.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_chief_startup_port.py tests/http_api/test_chief_routes.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor/test_chief_open_close_races.py tests/runner_supervisor/test_chief_session.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_hydrate_blank_and_decoy.py tests/comms_board/test_board_hydrate_hostile.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_run_cost_values.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_governance_escalation_note.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_chief_hook_tags.py tests/comms_board/test_chief_tier_lines.py -q -p no:cacheprovider
exit 0
prints passed
$ ! grep -n "sets neither today" src/pathly_orchestrator/CLAUDE.md
exit 0
$ ! grep -n "is recorded as typed" CHANGELOG.md
exit 0
$ ! grep -n "flagged under the write lock" src/pathly_orchestrator/CLAUDE.md
exit 0
$ grep -n "already answers" src/pathly_orchestrator/CLAUDE.md
exit 0
$ ! grep -nF 'whose `id` is not a string;' src/pathly_orchestrator/CLAUDE.md
exit 0
$ FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 20 $(git log --format=%H -n1 --grep='^docs(chief-agent): plan base for ticket 20$')
exit 0
prints floor guard: clean
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/gen_test_index.py --check
exit 0
$ black --check src/ tests/
exit 0
$ mypy src/ --ignore-missing-imports --no-strict-optional
exit 0
$ lint-imports
exit 0
$ python scripts/check_file_size.py
exit 0
$ python scripts/check_no_mirror_reads.py
exit 0
$ python scripts/check_version_sync.py
exit 0
$ bandit -q -r src/ -ll -x src/pathly_data/
exit 0
```

## Reference

- Where each note came from: the reviews of tickets 05, 06, 07, 09, 10, 11, 12, 14, 15, 16 and
  17, kept in the build's notes. Items checked and dropped are listed in the report that came
  with this ticket.
- `src/pathly_orchestrator/CLAUDE.md`: "Switches in claude 2.1.304", "Restart", the
  `POST /comms/directives` entry, the hydration paragraph under "Binding directives", "Cost and
  run limit".
- `tests/http_api/test_chief_routes.py` (`MAIN_SCRIPT`: runs `main()` with `app.run` replaced),
  `tests/comms_board/test_board_hydrate_hostile.py` (the hostile-file cases that already pass).
- Flask raises instead of answering 500 under `TESTING=True`; to see the real answer in a test set
  `app.config["PROPAGATE_EXCEPTIONS"] = False`.

## Answer

### Built

One change per item, each with its own test file that failed on the code at 600f4a0 (the work started at 588dc5d, which differs from it only in planning files).

- **B1** `runner/chief_argv.py`: `claude_settings` carries `"env": {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "CLAUDE_CODE_DISABLE_CRON": "1"}` (`_CLAUDE_ENV`); `open_chief` writes it into `settings.json` through the same function; a codex chief is unchanged.
- **B2** `http_server/blueprints/comms/_helpers.py`: `read_json_body` returns its default for a body that holds a lone surrogate in a key or in a string at any depth (`has_lone_surrogate`, an iterative walk, so a 300-deep body cannot make it recurse). Other non-ASCII text, a surrogate pair and a cp1252 body read as before.
- **B3** `chief_cli.py`: a token or server secret that is not latin-1 or holds a CR or LF, and a body nested too deeply (`RecursionError`), are exit 2, nothing sent, one stderr line each that names the problem and not the value (`pathly: PATHLY_RUN_TOKEN holds a character an HTTP header cannot carry`, `pathly: the server secret holds ...`, `pathly: the body is nested too deeply`).
- **B4** `chief_cli.py`: `MAX_BODY_BYTES = 1024 * 1024` and `MAX_ANSWER_BYTES = 256 * 1024`. Standard input is read with `read(MAX_BODY_BYTES + 1)` and counted in UTF-8 bytes (over the limit is exit 2); an answer is read in a loop of `answer.read(n)` that never asks for more than the limit plus one byte, printed up to the limit (not inside a character, not inside a half token), and `pathly: the answer was cut: its first N bytes are shown (the limit is 262144)` goes to stderr; the exit code follows the status.
- **B5** `chief_cli.py` `HELP`: a `POST /comms/acknowledge` line with `{"message_id", "agent": "chief", "cite"}`; `test_chief_help_routes.py` lists it; a test sends the line's body as an operator chief and the escalation is closed.
- **B6** `db/queries/comms_messages.py` `post_message(..., *, binding=0)` writes the flag in the INSERT; `db/queries/comms_directives.py` `post_directive` is one `post_message(..., binding=1)` call (no UPDATE; the lock import went with it).
- **B7** `supervisor/chief_session.py` `something_answers(host, port, timeout=1.0)`; `http_server/app.py` `main()` asks it first and, if something answers, logs `something already answers on <host>:<port>: the chief sessions are left open` and skips `chief_startup_cleanup()`.
- **B8** `supervisor/chief_session.py`: after `mint_run_token`, `open_chief` reads the session again; if it is closed it revokes the token (`revoke_run_tokens`) and raises `ChiefClosedWhileOpening(run_id)` before any spawn; `blueprints/chief/session.py` answers 409 `{error, run_id}`. The window after the re-read is in the `open_chief` docstring.
- **B9** `supervisor/registry.py` `TerminalRun.wait_started_or_result(timeout)`; `_watch` uses it.
- **B10, B11, B12** `board_mirror_hydrate.py`: `_belongs` needs an `id` that is a string with something in it after `strip()`; the message rows go in, the ids that are in the database under the file's board and scope afterwards (`landed`) are read back, and only those rows get their artifacts inserted (and their re-embed); `hydrate_board` returns False when none landed, so `hydrate_project` lists the scope under `skipped`.
- **B13** `runner/api_lifecycle.py`, `runner/api_control.py`, `control/_helpers.py`: `max_cost_usd = as_cost(...)`, `MESSAGE` for the 400, passed on as the float `as_cost` returned. `api_lifecycle.py` is 451 lines (452 before).
- **B14** `comms/directives.py`: `identity = caller_identity(request)` once, used for `is_chief_run(identity)` and `**stamp(identity)`; the scan in `test_comms_directives_query.py` accepts `**stamp(name)` where `name` was assigned `caller_identity(...)` in an enclosing function and still rejects a stamp built any other way.
- **B15** `runner/comms_formatters.py`: the newest decision for the NOTE is taken from `ranked` (ordinary decisions), not from all of them.
- **B17** `pathly_hooks/chief_prompt.py`: `_NOT_TYPED` is `<(?:task-notification|cross-session-message)` (no `\b`).
- **B18** `supervisor/chief_tiers.py`: `_front_matter_tier` splits the block on `"\n"`.

Living docs (verify-then-fix): `src/pathly_orchestrator/CLAUDE.md` (the hydration paragraph, the `POST /comms/directives` and `POST /comms/hydrate` entries, the `POST /chief/open` bullet, "Restart", the hook-tag sentence, the scheduled-task table row, "Switches in claude 2.1.304", the `pathly api` bullet, "Request bodies", "Cost and run limit", and the tree entries of `app.py`, `chief_session.py` and `comms_directives.py`); the `(chief-agent)` entry of `CHANGELOG.md` (its one known-limits sentence, edited in place); docstrings of `read_json_body`, `post_directive`, `post_message`, `open_chief`, `_watch`, `hydrate_board`, `_front_matter_tier`, the directives route, the hook module and `human.py`. Not changed: root `CLAUDE.md`, `studio/CLAUDE.md`, `README.md`, `docs/WHAT_IS_PATHLY.md` (no claim of theirs became false).

Tests: new files `tests/runner_supervisor/test_chief_settings_env.py`, `tests/http_api/test_comms_body_unicode.py`, `tests/http_api/test_chief_cli_limits.py`, `tests/comms_board/test_directive_single_insert.py`, `tests/comms_board/test_directive_route_caller.py`, `tests/http_api/test_chief_startup_port.py`, `tests/runner_supervisor/test_chief_open_close_races.py`, `tests/comms_board/test_hydrate_blank_and_decoy.py`, `tests/http_api/test_run_cost_values.py`, `tests/comms_board/test_governance_escalation_note.py`, `tests/comms_board/test_chief_hook_tags.py`, `tests/comms_board/test_chief_tier_lines.py`, and two support modules (`tests/mirror_drain_support.py` for the mirror-flusher drain and its autouse guard, `tests/runner_supervisor/chief_open_support.py`: `Host`, the project and sessions-folder fixtures, the watcher guard). Existing tests changed because the behaviour did: `test_chief_help_routes.py` (the table), `test_comms_directives_query.py` (the scan), `test_board_hydrate_hostile.py` and `test_board_mirror_hydrate.py` (a file that adds nothing is False and `skipped`), `test_comms_directives_fields.py` (a surrogate in `text` is now the unreadable-body 400, not the route's own "must be valid Unicode"), `test_chief_routes.py` (`main()` runs on a free `PATHLY_FSM_HTTP_PORT`, see Decisions). The per-folder `INDEX.md` files are regenerated.

### Proof

Test-only commit `1f23c23` (`test(chief-agent): 20 failing test`). On its tree the Test command (`python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`) exits 1: `1 failed, 293 passed`, the failure `test_board_hydrate_hostile.py::test_a_messages_value_that_is_not_a_list_imports_nothing[5]`. The 16 new and changed files together: `152 failed, 183 passed`.

What each new file did on the code at 600f4a0, at the state of the tests in this commit (run with `-o pythonpath=<git archive of 588dc5d src>`): `148 failed, 310 passed` for the 18 files, the 148 being:

- `test_chief_settings_env.py` 3 of 4 (the codex control passes): `KeyError: 'env'` and the key set `{hooks, permissions}` without `env`.
- `test_comms_body_unicode.py` 16 of 24 (the 6 gate controls and 2 ordinary-text tests pass): the 8 no-token rows and the 2 chief rows (`/comms/post` `text` and `feature`) answer 500 `UnicodeEncodeError: surrogates not allowed` (`scope` too); the key, nested and ignored-key bodies and the reader tests get 200 and a stored row, or the parsed dict instead of None.
- `test_chief_cli_limits.py` 25 of 30: `ValueError: Invalid header value` or `UnicodeEncodeError` (latin-1) from `http.client` for a bad token or secret (a traceback, exit 1); `RecursionError` for the 20,000-deep body; `AttributeError: no attribute 'MAX_BODY_BYTES'`; a standard-input body over 1 MiB is sent (exit 0); an answer over the limit is printed whole with no `cut` line; the answer is read with `read()` and no size; the help line is missing; and `UnicodeDecodeError` for a secret file that is not UTF-8.
- `test_chief_help_routes.py` 2 of 14: `pathly help has no line for POST /comms/acknowledge`, and the table set differs.
- `test_directive_single_insert.py` 5: two distinct statements write `comms_messages` (the INSERT and `UPDATE ... SET binding=1`), `not authorized` when UPDATEs are denied, `post_message() got an unexpected keyword argument 'binding'`.
- `test_directive_route_caller.py` 1 of 2 and `test_comms_directives_query.py` 1: `caller_identity` called twice; the scan rejects the route.
- `test_chief_startup_port.py` 12 of 14 (the free-port `main()` and the no-argument cleanup pass: controls): `ImportError: cannot import name 'something_answers'` for the probe tests; for the busy port `main()` leaves `open: False, token_live: False` (it closed the first server's chief).
- `test_chief_open_close_races.py` 7 of 11: `AttributeError: no attribute 'ChiefClosedWhileOpening'`; the route answers 201 with a live session; the watcher thread is still alive after 2 s; `TerminalRun` has no `wait_started_or_result`.
- `test_hydrate_blank_and_decoy.py` 21 of 24 and the two changed hydration files 8 (5 of 64 and 3 of 13): the blank id is stored (`['\t', 'first', 'second']`), the decoy artifact lands on the other board's message, `hydrate_board` is True for a file that adds nothing, `hydrate_project` lists `['demo', 'feat-ok', 'global']` as hydrated.
- `test_run_cost_values.py` 15 of 37: `NaN`, `Infinity`, `true`, `1e999` start the run (200) on `/runner/start`, `/runner/retry` and the `retry` verb, and `10**400` is a 500 `OverflowError` (`-Infinity`, `"5"`, `null`, `0`, `-1` were already 400, and `5` and `0.5` start: controls).
- `test_governance_escalation_note.py` 3 of 9: the NOTE shows after a standing order alone.
- `test_chief_hook_tags.py` 12 of 28 (`KeyError: 'relayed'`) and `test_chief_tier_lines.py` 16 of 27 (`'operator' == 'status'`).
- `test_comms_directives_fields.py` 1 (the changed message).

After the fix: the 18 files pass, `458 passed`, on Python 3.11.17, 3.12 and 3.13.16 (each in a fresh venv). With `HOME` and `USERPROFILE` set to an empty directory the run leaves that directory empty. The check block of this ticket: every pytest line exits 0 and prints `passed` (4, 24, 44, 37, 78, 62, 88, 37, 9 and 55 passed); the five greps exit 0.

Lint command, as written in `commands.md`, exit 0: `black --check src/ tests/` (693 files unchanged), `mypy src/ --ignore-missing-imports --no-strict-optional`, `check_file_size.py` (`18 known over 400 lines, none new, none grown`), `check_no_mirror_reads.py`, `gen_test_index.py --check` (`up to date`), `lint-imports`, `bandit -q -r src/ -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`; also `check_version_sync.py` (`2.24.1`).

Full suite, `python -m pytest tests/ -q -p no:cacheprovider`: exit 0, `6273 passed, 14 skipped in 1805.57s (0:30:05)`, run on the final production tree. `tests/http_api/test_comms_body_unicode.py` got its last amendment after that run had collected, so the five files amended since the test-only commit (`test_comms_body_unicode.py`, `test_chief_cli_limits.py`, `test_directive_single_insert.py`, `test_chief_routes.py`, `test_comms_directives_fields.py`) were run again on the final tree: `184 passed`. The run leaves a detached real FSM server on 127.0.0.1:8765 (see For later tickets); I killed it and port 8765 is free.

Floor guard: `FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 20 588dc5dd5e9c6f0cbe93cb1426595b32554f32f9` prints `floor guard: clean`. With the base the ticket names, `600f4a0...`, it prints `ticket-edit` findings for tickets 19, 20 and 21, because the two planning commits that added them (`dcaba2b`, `588dc5d`) come after it; no file of mine is named.

### Decisions

- B2: the reader gives up at the first reading that parses (UTF-8, else cp1252) and holds a surrogate; it does not try the other encoding. The chief rows of the test are `/comms/post` `text` and `feature` only: of the six routes the ticket lists for a chief, the gate answers 403 first for the others (a surrogate id is not an id of its project; `/comms/edit` and `/comms/delete` are no chief routes; `scope` is "not this chief's project"), so those six get a control test that pins the 403. The 500 was measured for a caller with no token on all eight bodies.
- B3: a header value is refused when it is not latin-1 or holds a CR or LF (wider than `http.client`, which folds a newline followed by a space or tab). Added, not in the ticket: a secret file that is not UTF-8 text (`Path.read_text()` raises `UnicodeDecodeError`, not `OSError`) is `pathly: the server secret cannot be read as text`, exit 2, with a test; `fsm_http_client._load_secret` itself is unchanged.
- B4: the stdin limit is on UTF-8 bytes, measured after asking the stream for `MAX_BODY_BYTES + 1` characters (which can never be fewer bytes than characters, so a body of exactly the limit passes and one byte more is refused). A body given as an argument is not bounded here (the OS bounds it). The cut line is `pathly: the answer was cut: its first N bytes are shown (the limit is 262144)`; N counts the bytes of the answer shown, after an incomplete last character and the start of a secret that the limit cut in half are dropped.
- B6: `post_directive` takes no lock of its own any more: `post_message` holds the write lock for its one INSERT.
- B7: the probe lives in `supervisor/chief_session.py` (where the ticket put the startup step), detects a wildcard host with `ipaddress.ip_address(host).is_unspecified` so that no `"0.0.0.0"` literal (bandit B104) and no `# nosec` is needed, uses a 1 second timeout, and the log line is a warning. `test_chief_routes.py` did not set `PATHLY_FSM_HTTP_PORT` (the ticket says it does; line 64 of that file sets 8123 for another test), so its two `main()` tests ran on 8765 and failed in the full suite when a server was listening there (see For later tickets): `_run_main` now sets a free port.
- B8: the re-read is right after the mint, before the argv and `create_run`, so nothing was created yet for the raise to undo; the existing `except BaseException: close_chief(run_id, "open failed")` removes the folder (it returns False for a session that is already closed and keeps the closer's reason), and the token is revoked by the new branch itself.
- B10 to B12: the artifacts and the re-embed both go only to the rows that landed. The ticket names the artifacts; the re-embed used the same list, and a row that did not land (an id that belongs to another board's message) would have had that other message re-embedded with the file's text.
- B13: the three handlers import `MESSAGE` and `as_cost` inside the function, as the ticket says; the `retry` verb takes the import at the top of `control/_helpers.py` (already imports `flow_cost` from the same module).

### Shortcuts taken

- No mutation run for this ticket (earlier tickets ran a harness); the tests were checked red against the old code and green against the new, not mutated.
- B1 stays "measured on one claude version": no real `claude` was started, as for every test of this feature.

### Review fixes

None yet: this is the first build of the ticket.

### For later tickets

- A body nested deeper than the recursion limit makes `read_json_body` raise `RecursionError` (not a `ValueError`): every comms route answers 500 (measured: a 100,000-deep array to `/comms/post`). One word in the `except` of the reader, but the ticket's B2 is the surrogate.
- The full suite leaves a real `python -m pathly_orchestrator.http_server` running on 127.0.0.1:8765 (detached, parent 1, started a few minutes into the run by some test that calls `fsm_http_client.ensure_server_running()` unmocked; I did not find which one). Since B7 any `main()` run on the default port sees it. I killed it after the run; it comes back with every full run.
- `blueprints/comms/directives.py::_text_refusal` still has the branch "Field 'text' must be valid Unicode"; since B2 a surrogate never reaches it through the route (the reader refuses the body first), so it is only defence in depth now.
- `pathly api`'s body given as an argument is bounded by the operating system only (131072 bytes on Linux); the ticket bounds standard input.
- The escalation NOTE (B15) still compares timestamps as strings; two rows written in the same second keep the old order.
