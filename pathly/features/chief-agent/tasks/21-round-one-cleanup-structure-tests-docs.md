# Round-one clean-up: moves, test hardening and documentation

Type: task
Status: resolved
Blocked by: 20
Test first: no

Ticket 20 fixed the defects. This ticket holds the rest of what the round-one reviews left, each
item checked against the code at 600f4a0: code that moves without changing what it does (S),
tests that let a changed line pass unnoticed or that leave a mess behind (T), and sentences in
docs, docstrings and comments that are now false (D). Nothing here is a feature and nothing
here changes an answer a route gives, with two small exceptions named in S4 and S6.

Rules for all of them:

- Keep every file at 400 lines or fewer. Split first any file an item would take past 400. The
  files already over the limit (the list in `scripts/file_size_baseline.txt`) may not grow.
- Ticket 20 is merged first. Names it adds (`ChiefClosedWhileOpening`, `post_message(binding=)`,
  the startup probe, `wait_started_or_result`) are used as they stand.
- No new `# noqa`, `# nosec`, `skip` or `xfail`. A test is never changed to make it pass: where an
  item changes a test on purpose, the item says so and why.
- Documentation items: check each claim against the code first and change only what is now
  false. Do not rewrite a paragraph that is right. Point-in-time records (`pathly/features/*/SPEC.md`,
  retros, the answers in the other tickets, `.archive/`) are not edited.
- A new test file goes in the folder named for it, with a basename that is unique across `tests/`;
  run `python scripts/gen_test_index.py` after adding, moving or removing a test.

## S1. `messages_crud.py` is split before anything else touches it

Files: `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py` (exactly 400 lines),
new `.../comms/messages_read.py`, `.../comms/messages.py`.

Move `comms_get` (`GET /comms`) and `comms_search` (`GET /comms/search`) with the constants and
helpers only they use to `messages_read.py`. `messages.py` loads the new module the way it loads
the others, without a new `# noqa` (bind the three modules to names and use them in a tuple,
for example). No URL, method, body, status or log line changes. The writers stay where they are
(`tests/comms_board/test_binding_retire_writers.py` names `messages_crud.py` by path for them).
Update the module docstrings of `messages.py` and `messages_crud.py` to say where each route is.

## S2. `BINDING_REFUSED` lives in `comms/_helpers.py`

Files: `.../comms/_supersede_on_post.py`, `.../comms/messages_crud.py`, `.../comms/_helpers.py`.

The refusal text is defined in `_supersede_on_post.py` and imported by a sibling route module.
A constant shared by route modules belongs in `_helpers.py` (rule 5 of the repo's SOLID rules).
Define it there with the same string; both modules import it from there.

## S3. One author-source check, and the re-export at the top

Files: `src/pathly_orchestrator/db/provenance_values.py`, `.../db/queries/comms_messages.py`,
`.../db/queries/comms_edit.py`.

`post_message` and `update_message_text` each carry the same `if author_source ... not in
AUTHOR_SOURCES: raise ValueError(...)`. Put the check once in `provenance_values.py` (message text
unchanged: `unknown author_source ...; expected one of [...]`) and call it from both. In
`comms_messages.py` the `from .comms_edit import update_message_text` re-export sits at the
bottom of the file; move it to the import block at the top (it needs no `# noqa`).

## S4. One way to write a project root, and a bare root stays a root

Files: `src/pathly_orchestrator/scope_names.py` (new `normalise_root`),
`.../supervisor/chief_session.py` (`normalise_project_root`), `.../http_server/blueprints/comms/_helpers.py`
(`norm_project_root`), `.../runner/comms_context.py` (`_norm_root`), `.../runner/board_scope.py`;
new test `tests/storage_paths/test_normalise_root.py`.

Four modules each spell `root.replace("\\", "/").rstrip("/")` themselves, and the chief's copy
(a fifth, with a different fallback) turns a bare drive root `C:\` into `C:`, which names the
current folder of drive C, not the root. Add one `normalise_root(value)` to `scope_names.py`:
backslashes become `/`, trailing `/` are dropped, and a root that is only a separator or a drive
(`/`, `C:/`) keeps one `/`; the empty string stays empty. The four callers use it
(`normalise_project_root` stays as a name, so its users and tests do not change). The other
copies of the idiom (`board_mirror.py`, `fsm_compose_paths.py`, `db/queries/skill_composition.py`,
`db/queries/prompt_library.py`, `comms/project.py`, `fsm_ops.py`) return `None` or another
fallback and are left for a later pass. The one change in behaviour is the bare-root case, which
no real project root is; the new test pins it with `/p/`, `/p`, `C:\Users\Yafit\proj\`, `C:\`, `/`
and `""`.

## S5. `resolve_run_token` is `lookup_run_token` plus a revoked check

File: `src/pathly_orchestrator/db/queries/run_tokens.py`.

The two functions run the same query and build the same dict. `resolve_run_token` returns the
`lookup_run_token` row when it is live (`revoked_at` is null) and `None` otherwise; it runs no SQL
of its own.

## S6. One module owns `BINDING_MARK` and what "binding" means for a row

Files: new `src/pathly_orchestrator/runner/comms_binding.py`, `.../runner/comms_governance.py`,
`.../runner/comms_formatters.py`, `.../runner/comms_context.py`; new test
`tests/comms_board/test_binding_row_predicate.py`.

`comms_governance` defines `BINDING_MARK` and imports `comms_formatters` inside a function, while
`comms_formatters` imports `BINDING_MARK` from `comms_governance` at the top: a cycle hidden by a
lazy import. The new leaf module holds `BINDING_MARK` and `is_binding_row(row)`, true only when
`row["binding"] == 1`; the three modules import from it, and `comms_governance` imports
`render_governance_lines` at the top of the file. Today the standing-orders query takes `binding=1`,
while the pending filter in `comms_governance` and the check in `comms_context` take any truthy
value; both use `is_binding_row`. The one change in behaviour is a row whose `binding` is neither 0
nor 1, which no code writes: it is an ordinary row everywhere. The test pins the predicate for
`1`, `0`, `None`, `2`, `"1"` and a missing key, and a pending row with `binding` 2 staying in the
pending half.

## T1. Pin the gate checks that a changed line passed unnoticed

Files: new `tests/http_api/test_chief_gate_pins.py`; `tests/http_api/test_chief_bind_edges.py`.

Reviewers changed one line each in a scratch copy and the existing tests still passed. Add a test
for each:

- `chief_gate._cite_refusal` applies the cite rule when any reading of the body is an `answer`,
  not only when all are. Use `/comms/acknowledge` (an answer only for a human-addressed
  escalation) with two readings, one naming an escalation to `human` and one an ordinary row;
  the refusal must apply. (Changing `any(` to `all(` in `_cite_refusal` makes it fail.)
- `chief_bind._in_project` reads an empty or missing `board` as the feature board, as the routes
  do (`row["board"] or "feature"`): a row with an empty board on a feature the project owns is
  the project's, one on a feature it does not own is refused. (Replacing `board or "feature"` by
  `board` makes it fail.)
- A scope with padding, `" demo"` and `"demo "`, is refused though `demo` is a feature of the
  project: add both to the parametrisation in `test_chief_bind_edges.py`.
- `chief_bind._placed_run` looks a run up in the registry in any status (`statuses=None`): a
  registry entry that is not active and has no history row still places the run. (Dropping the
  `statuses=None` makes it fail.)

## T2. Pin that the gate fails closed, and that the two cost defaults agree

File: new `tests/http_api/test_chief_gate_fail_closed.py`.

Set `app.config["PROPAGATE_EXCEPTIONS"] = False` (under `TESTING` Flask re-raises instead of
answering). With an operator chief starting a flow:

- `get_setting` raising `sqlite3.OperationalError`: the answer is 500, `start_run` is not called,
  and `runs_started` is 0.
- `take_run_slot` raising: the same.
- `placement.message_board_scope` raising while the gate checks an id: 500 and the route does not run.
- `give_back_run_slot` raising after a 4xx start (a missing field): the 4xx stands (it does not
  turn into a 500), a warning is logged, and the slot stays used.
- `DEFAULT_FLOW_COST_USD` equals the default of `supervisor.api.start_run`'s `max_cost_usd` and of
  `RunnerState().max_cost_usd` (today three copies of `1.0` that nothing keeps equal).

## T3. Pin what hydration does to every kind of stamp

File: new `tests/comms_board/test_hydrate_unverified_rows.py`.

A review changed `comms_hydrate._unverified` so that `binding` was reset only for a row that
claimed the `token` source, and the tests passed. Parametrise over `author_source` (absent,
`none`, `legacy`, `system`, `token`) and `author_role` (none, `chief`, `builder`), each with
`binding` 1, through `insert_message_row` and through `hydrate_board`: `binding` is stored as 0 every
time; `none` stays `none`; `legacy`, `system` and `token` are stored as `legacy`; an absent source
is stored as `legacy` once `hydrate_board` has run its backfill. The role and run id are stored as
the file names them (documented, so pinned).

## T4. Tighten the tests of the directive route and the governance block

Files: `tests/comms_board/test_comms_directives_route.py`, `test_comms_directives_fields.py`,
`test_binding_directive_hardening.py`.

- A builder token, no token, and the server secret alone, each with an invalid body (not an
  object, a blank `project_root`, a bad `to_agent`), get 403, not 400: the caller is checked
  before the body is read. (Moving the body check ahead of the identity check makes it fail.)
- A bad `to_agent` (upper case, padded, 41 characters) is a 400 in `test_comms_directives_route.py`
  too, so the command that runs that file covers it.
- A text of exactly 8,192 bytes with whitespace on both sides is 201, and 8,193 bytes after
  stripping is 400 (the cap is on the stripped text).
- `test_a_body_that_is_not_an_object_posts_nothing` accepts `(400, 403)`; for a chief it is always
  400. Assert 400.
- `test_binding_directive_hardening.py` has a literal U+2028 character in two lines; write it as
  the escape `\u2028`. The fail-soft test (`test_when_the_query_fails_a_pending_binding_row_...`)
  asserts that one "standing orders unavailable" warning was logged, not "at least one".

## T5. One guard against a chief watcher that outlives its test

Files: new `tests/chief_session_guard.py` (a helper at the root of `tests/`, importable by bare
name like `_paths.py`); `tests/http_api/chief_cli_support.py`, `tests/http_api/test_chief_routes.py`,
`tests/runner_supervisor/test_chief_session.py`, `tests/comms_board/chief_human_support.py`,
`tests/comms_board/chief_acceptance_support.py`; new `tests/consistency/test_chief_tests_use_the_guard.py`.

`_no_watcher_outlives_its_test` is defined five times with small differences. A watcher left
running wakes 30 seconds later in another test and opens the developer's real `~/.pathly`
(see the comment on `_isolate_db` in `tests/conftest.py`). Define the guard once (it closes the
chiefs a test left open while the patched home is still in place, drains the two mirrors, and
fails the test if a thread it started is alive) and import it in the five places. At the end of a
test the guard asserts `board_lock._held` is empty instead of clearing it; a scenario that leaves
a lock held releases it in its own teardown. The new consistency test fails for any test module
that opens a chief (it contains `/chief/open` or `open_chief(`) and does not import the guard
(removing the import from `test_chief_cli.py` is caught by nothing today).

## T6. Tidy the acceptance test

Files: `tests/comms_board/test_chief_acceptance.py`, `tests/comms_board/chief_acceptance_support.py`.

- The comment "Quotes and a line break: ..." before the scenario 4 test describes nothing near it;
  move it next to the constant it explains, or delete it.
- The scenario that has the chief `PUT` the ceiling setting sends 5,000, which is the value
  already stored, so only the 403 status guards it. Send a different value and assert that
  `GET /chief/session` still reports the old ceiling.
- Replace the literals `10.0` and `20` that stand for the defaults by
  `chief_budget.DEFAULT_CEILING_USD` and `DEFAULT_RUN_LIMIT`, and give the other cost numbers
  names.
- `SpawnHost.seen` is filled and never read: remove it.
- The lines that read `own.get_json()["run_id"]` before asserting the status is 200 assert first.

## T7. Pin what the chief's command and texts promise

Files: `tests/http_api/test_chief_cli_edges.py`, `test_chief_help_routes.py`,
`test_chief_prose_rules.py`, `test_chief_prompt_text.py`, `test_chief_cli_input.py`.

Mutants of the command and the texts survived. Add a test for each:

- The help lines for `POST /comms/answer` and `POST /runner/agent-answer` show exactly the keys
  `{question_id, cite}` and `{topic, cite}`.
- The help says a chief never sends an answer of its own (a phrase, pinned the way
  `test_chief_prose_rules.py` pins the others).
- A subprocess runs `pathly` with `PYTHONIOENCODING=cp1252` and `PYTHONUTF8=0` and a non-ASCII
  body and answer: it reads and prints UTF-8 (the test for `_use_utf8`).
- `DEFAULT_HOST == "127.0.0.1"`.
- The token never appears in stdout or stderr for any input in the list of bad usages, not only
  for the ones tested so far.
- The "may not ..." sentences in the status and planner texts are derived from `TIERS` in a
  test: it fails when the tier table and the text disagree.
- The `/comms/supersede` example in the texts is run with real ids.
- The test that expects "no server" uses port 1; use a port that was bound and released.

## T8. Small test fixes

Files as named.

- `tests/db/test_chief_tables.py::test_message_id_unique_in_the_schema` uses `pytest.raises`
  instead of try/except around `AssertionError`.
- `tests/runner_supervisor/test_chief_session.py::test_bad_input_is_a_value_error_and_leaves_nothing_behind`
  is parametrised on the input pairs it checks, not on `range(10)`.
- A test leaves an empty directory named `C:\Users\Yafit\demo\` (with `pathly/project` inside) in
  the folder tests run from. Find the test (the likely one posts that root to
  `/comms/project/decompose` in `tests/dag_goals/test_project_decompose.py`) and make it use
  `tmp_path` or a patched path, so no such folder is made. Delete the stray folder that exists now.
- In `tests/http_api/test_chief_gate_audit.py` the `climbing` value is the literal
  `../../../../proj-b/planted`. No `proj-b` exists in the sandbox (the other project is
  `elsewhere`), so the value cannot reach the other project. Build it from the sandbox's paths
  (the relative path from the directory the routes open files from to a file in the other
  project) and add an assertion that the normalised join of that directory and the value lies in
  the other project. The audit must still pass.
- `chief_tiers._front_matter_tier` depends on the block it reads being exactly what
  `strip_front_matter` removes. Pin it in `tests/comms_board/test_chief_tiers.py`: for a front
  matter that ends at the end of the text, one with CRLF, one with trailing blank lines and one
  with no front matter, `text[:len(text) - len(strip_front_matter(text))]` is the block the tier
  is read from. Say in the docstring that a quoted value (`tier: "operator"`) is `status`, and
  test it.

## D1. Say "recorded as typed", not "typed"

Files: `src/pathly_orchestrator/CLAUDE.md` ("Cited answers" and "What a citation proves");
`src/pathly_orchestrator/http_server/chief_cite.py` (module docstring); `src/pathly_hooks/chief_prompt.py`
(first line); the root `CLAUDE.md` (the `chief/` entry of the blueprint map).

A `human` message is what the hook recorded as a prompt that reached the tab, not proof that a
person typed it (the same docs say so a few lines later). The lead of "Cited answers" says the
chief names "a message the person typed"; "What a citation proves" says it "proves" the words
"reached the chief's tab"; the `chief_cite.py` docstring says it proves "the words are the
person's"; the hook's first line says it records "what the human types"; the root entry says the
same. Reword each to what the hook knows ("recorded by the hook as typed", "shows" instead of
"proves", "the prompts that reach the tab"), leaving the caveats that follow as they are.

## D2. Three small facts

Files: root `CLAUDE.md`; `docs/ARCHITECTURE.md`; `docs/API.md`.

- Root `CLAUDE.md` says "the 19 files already over the limit"; `python scripts/check_file_size.py`
  reports 18 and `scripts/file_size_baseline.txt` has 18 entries. Say 18.
- `docs/ARCHITECTURE.md` lists the hook scripts of `src/pathly_hooks/` as `classify_feedback.py` and
  `inject_feedback_ttl.py`, "deployed by install". `stop_telemetry.py` is deployed too
  (`adapters/claude/_meta/install.yaml`), and `chief_prompt.py` is not deployed by install: the
  server writes its command into a chief session's own settings. List all four and say which is which.
- `docs/API.md` says `/code/query` results are cached by `(op, target, content-hash)`. The key is
  the project root, the op, the target, the content hash and the backend
  (`blueprints/code/query.py`, `_QUERY_CACHE`). Say that.

## D3. The CHANGELOG and the acceptance test name spike 19 as the live check

Files: `CHANGELOG.md` (the `(chief-agent)` entry); `tests/comms_board/test_chief_acceptance.py`
(module docstring).

Both say spike 19, "a hand run with" a real claude, is "the planned live check". When they were
written that was false: spike 19 (`tasks/19-daycap-guard-coverage-spike.md`) asked only whether
the daycap guard fires on headless spawns. It now has a Part B, eight yes or no questions run with
a real claude against the chief's restricted flags, its hook, `pathly api`, the cite flow, its
limits and close, so the claim is true. Reword both sentences to say "spike 19 part B" and to say
what stays unmeasured until it has been run. Second, the
entry says two settings "bound a session" and that a run start above the cost ceiling is refused;
only `POST /runs` of a flow and the `retry` verb state a cost. Say that goal, board and task
runs are bounded by the run count alone (a goal's own cap is `goal.max_cost_usd`, when set).

## D4. Five gaps in `src/pathly_orchestrator/CLAUDE.md`

Files: `src/pathly_orchestrator/CLAUDE.md`; `.../blueprints/comms/directives.py` (docstring).

Check each against the code, then fix it:

- The `POST /comms/directives` entry and the route docstring say a blank `project_root` is a 400.
  An empty string is a 400; a string of spaces is the chief gate's 403 (`that is not this chief's
  project`) because it is not the session's root. Say both.
- The paragraph on ids says feature boards are keyed by name only, so a feature that exists in two
  projects is in both. Add that a planner or operator chief can create that folder itself
  (find which routes create `<root>/pathly/features/<name>` before saying which), so for a name
  that exists in another project the folder check can be made true by the chief.
- "What a spent citation costs": two chief requests that cite two different messages for one
  waiting question, both before the run's poll takes the first answer, spend both messages and the
  second answer overwrites the first. Read `_await_agent_question` (or write the test) to confirm
  it, then add it.
- The hydration paragraph: a clone at a different path or letter case imports no project-board
  rows (every row names the exporter's root; feature boards are keyed by name and are unaffected),
  and, since ticket 20, `hydrate_project` lists that scope under `skipped`.
- The scope gate paragraph says a builder "cannot widen its scope by posting a task and claiming
  it". Since ticket 03 an edit re-stamps the row to the editor, so editing a task has the same
  effect as posting it (a task a builder edited is stamped `builder` and does not count). Say
  "posting or editing". Check first that `/comms/edit` changes only the text.

## D5. Docstrings and descriptions that are wrong or use build vocabulary

Files: `src/pathly_orchestrator/runner/chief_argv.py`; `.../http_server/blueprints/chief/session.py`;
the docstrings of `tests/http_api/test_chief_cli_input.py`, `test_chief_help_routes.py`,
`test_chief_prose_rules.py`, `chief_text_support.py`, `tests/comms_board/test_binding_directive_hardening.py`
and `test_board_hydrate_hostile.py`; the generated `tests/http_api/INDEX.md` and `tests/comms_board/INDEX.md`.

- `claude_settings` says "Every Bash command other than `pathly ...` asks the human". It does not:
  under `--restricted --tools` claude runs read-only commands without asking and asks for the rest.
  Say what claude does (check it in the chief's tab or against the 2.1.304 measurements in
  "Human messages"), and mention the `env` block ticket 20 added.
- The module docstring of `chief/session.py` calls open and close "Studio's launcher". Studio has
  no Chief button yet; today `POST /chief/open` is called directly. Say so.
- Six test docstrings, and the INDEX rows made from them, open with "round 2" or "review round
  2". That is how the work was done, not what the test checks. Describe the check, then run
  `python scripts/gen_test_index.py`.

## D6. The chief's text: apostrophes in a root, `-`, and "if your tier holds `answer`"

Files: `src/pathly_data/core/skills/fragments/chief-connect.md`;
`src/pathly_orchestrator/supervisor/chief_presets.py` (`ROOT_LINE`);
`tests/http_api/test_chief_prose_rules.py`, `test_chief_prompt_text.py`.

Three sentences of what the chief reads are wrong or unusable:

- The list of characters of the root to percent-encode in a query string is `+ & % space`. A root
  with an apostrophe ends the single quotes the path is in: add `'` as `%27`. And "a JSON body keeps
  it exactly as written" is false for a root that holds `"` or `'` (they need the JSON escape:
  `\"`, `\u0027`). Change the fragment and `ROOT_LINE`, and test it by running `shlex.split`
  on each `pathly api` example in the texts with a root that holds an apostrophe and a space:
  each parses to the arguments intended.
- The fragment says `-` in place of the body reads standard input, but its own rule forbids the
  pipe that would feed it, and the one form that works under `Bash(pathly *)` is unchecked. Drop
  the `-` sentence from the fragment. The command still accepts `-` and `pathly help` still
  describes it. Change the pin in `test_chief_prose_rules.py` that held the sentence.
- "Answer with `cite=<id>`" in "Answering an agent" does not say that only a chief whose tier
  holds `answer` may. Say "if your tier holds `answer`".

## D7. The skill text that agents read

Files: `src/pathly_data/core/skills/fragments/comms-post.md`;
`src/pathly_data/core/skills/planning/prd-import.md`; `.../planning/project-decompose.md`; the
golden snapshots in `tests/snapshots/` that carry the fragment.

- `comms-post.md` lists the reasons `supersede_skipped` can hold as `not_found`,
  `already_superseded`, `not_a_decision` and `other_board`. The code
  (`_supersede_on_post.apply_supersedes`) also gives `binding`, `self_reference` and `error`.
  List all of them.
- `prd-import.md` (two commands) and `project-decompose.md` (three) show
  `GET /comms?board=project&scope=$PROJECT...` with no `feature`, which the route answers with
  a 400. Add `&feature=project` to each (the same form the chief texts use).
- The golden snapshots under `tests/snapshots/` carry the fragment text. Regenerate the ones that
  change and check the diff is only the sentence above. Then `pathly-setup claude --apply --repair`
  copies the new text to a machine that has the skills installed (not part of the repo's checks).

## Not in this ticket

- No Studio change and no HQ change.
- No round-two feature: the friendly `pathly` commands (`overview`, `inbox`, `answer --cite`, ...),
  `GET /chief/overview` and `GET /chief/inbox`, Studio paste-without-Enter, the Chief button, the
  inbox badge, re-queueing stale directives, billing the chief's own session.
- No version bump and no release.
- Behaviour fixes: ticket 20.
- The decisions left for the person (see the report that came with these tickets). They are not
  made here.

## Done when

- Each item's check below passes; each documentation check fails on the code at 600f4a0 and
  passes after.
- The route table is the one it was (S1): 177 rules, the same fingerprint as at 600f4a0.
- No test was edited to make it pass, apart from the ones the items name (T1, T4, T5, T7, T8,
  D6, D7's snapshots).
- The whole suite and the checks pass; the floor guard is clean (its check starts from the commit
  whose subject is `docs(chief-agent): plan base for ticket 21`).

```check
$ python -c "import sys; from pathly_orchestrator.http_server import app; v=app.view_functions; ok=all(v['comms_messages.'+n].__module__.endswith('.messages_read') for n in ('comms_get','comms_search')) and v['comms_messages.comms_acknowledge'].__module__.endswith('.messages_crud'); sys.exit(0 if ok else 1)"
exit 0
$ python -c "import sys,hashlib; from pathly_orchestrator.http_server import app; r=sorted((x.rule, tuple(sorted(x.methods))) for x in app.url_map.iter_rules()); sys.exit(0 if (len(r), hashlib.sha256(repr(r).encode()).hexdigest()[:16]) == (177, 'fa1e371ebe797dc5') else 1)"
exit 0
$ test "$(wc -l < src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py)" -lt 340
exit 0
$ python -c "from pathly_orchestrator.http_server.blueprints.comms._helpers import BINDING_REFUSED"
exit 0
$ ! grep -n '^BINDING_REFUSED' src/pathly_orchestrator/http_server/blueprints/comms/_supersede_on_post.py
exit 0
$ test "$(grep -rl 'unknown author_source' src/pathly_orchestrator | wc -l)" = 1
exit 0
$ python -c "import ast,sys; t=ast.parse(open('src/pathly_orchestrator/db/queries/comms_messages.py').read()); d=min(n.lineno for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))); sys.exit(1 if [n for n in t.body if isinstance(n,ast.ImportFrom) and n.module=='comms_edit' and n.lineno>d] else 0)"
exit 0
$ python -m pytest tests/storage_paths/test_normalise_root.py -q -p no:cacheprovider
exit 0
prints passed
$ ! grep -n 'rstrip("/")' src/pathly_orchestrator/supervisor/chief_session.py src/pathly_orchestrator/http_server/blueprints/comms/_helpers.py src/pathly_orchestrator/runner/comms_context.py src/pathly_orchestrator/runner/board_scope.py
exit 0
$ python -c "import inspect,sys; import pathly_orchestrator.db.queries.run_tokens as m; s=inspect.getsource(m.resolve_run_token); sys.exit(0 if 'execute' not in s and 'lookup_run_token' in s else 1)"
exit 0
$ python -m pytest tests/comms_board/test_binding_row_predicate.py tests/comms_board/test_binding_directives.py tests/comms_board/test_binding_directive_hardening.py -q -p no:cacheprovider
exit 0
prints passed
$ ! grep -n '    from .comms_formatters import' src/pathly_orchestrator/runner/comms_governance.py
exit 0
$ ! grep -n 'get("binding")' src/pathly_orchestrator/runner/comms_governance.py src/pathly_orchestrator/runner/comms_context.py
exit 0
$ python -m pytest tests/http_api/test_chief_gate_pins.py tests/http_api/test_chief_bind_edges.py tests/http_api/test_chief_gate_fail_closed.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_hydrate_unverified_rows.py tests/comms_board/test_comms_directives_route.py tests/comms_board/test_comms_directives_fields.py tests/comms_board/test_binding_directive_hardening.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import sys; sys.exit(1 if '\u2028' in open('tests/comms_board/test_binding_directive_hardening.py', encoding='utf-8').read() else 0)"
exit 0
$ test "$(grep -rn 'def _no_watcher_outlives_its_test' tests --include='*.py' | wc -l)" = 1
exit 0
$ python -m pytest tests/consistency/test_chief_tests_use_the_guard.py tests/comms_board/test_chief_acceptance.py tests/http_api/test_chief_routes.py tests/runner_supervisor/test_chief_session.py -q -p no:cacheprovider
exit 0
prints passed
$ ! grep -n '\.seen' tests/comms_board/chief_acceptance_support.py
exit 0
$ grep -n 'DEFAULT_CEILING_USD' tests/comms_board/test_chief_acceptance.py
exit 0
$ python -m pytest tests/http_api/test_chief_cli_edges.py tests/http_api/test_chief_help_routes.py tests/http_api/test_chief_prose_rules.py tests/http_api/test_chief_prompt_text.py tests/http_api/test_chief_cli_input.py -q -p no:cacheprovider
exit 0
prints passed
$ grep -n 'pytest.raises' tests/db/test_chief_tables.py
exit 0
$ ! grep -n 'range(10)' tests/runner_supervisor/test_chief_session.py
exit 0
$ python -m pytest tests/http_api/test_chief_gate_audit.py tests/comms_board/test_chief_tiers.py -q -p no:cacheprovider
exit 0
prints passed
$ ! grep -n 'message the person typed in its' src/pathly_orchestrator/CLAUDE.md
exit 0
$ ! grep -n 'It proves the words an agent receives' src/pathly_orchestrator/CLAUDE.md
exit 0
$ ! grep -n "What this proves is that the words are the person's" src/pathly_orchestrator/http_server/chief_cite.py
exit 0
$ ! grep -n 'record what the human types' src/pathly_hooks/chief_prompt.py
exit 0
$ ! grep -n 'records what the human types' CLAUDE.md
exit 0
$ ! grep -n 'the 19 files already over the limit' CLAUDE.md
exit 0
$ grep -q 'chief_prompt' docs/ARCHITECTURE.md
exit 0
$ grep -qF 'project root, op, target, content hash, backend' docs/API.md
exit 0
$ grep -n 'spike 19 part B' CHANGELOG.md
exit 0
$ grep -n 'spike 19 part B' tests/comms_board/test_chief_acceptance.py
exit 0
$ grep -n 'goal, board and task runs' CHANGELOG.md
exit 0
$ ! grep -nF 'a blank `project_root`' src/pathly_orchestrator/CLAUDE.md
exit 0
$ grep -n 'can create that folder' src/pathly_orchestrator/CLAUDE.md
exit 0
$ grep -n 'spend both' src/pathly_orchestrator/CLAUDE.md
exit 0
$ grep -n 'different path' src/pathly_orchestrator/CLAUDE.md
exit 0
$ python -c "import re,sys; t=open('src/pathly_orchestrator/CLAUDE.md', encoding='utf-8').read(); sys.exit(0 if re.search(r'posting or editing\s+a\s+task', t) else 1)"
exit 0
$ ! grep -n 'Every Bash command other than' src/pathly_orchestrator/runner/chief_argv.py
exit 0
$ ! grep -n "Studio's launcher" src/pathly_orchestrator/http_server/blueprints/chief/session.py
exit 0
$ ! grep -n -i 'round 2' tests/http_api/INDEX.md tests/comms_board/INDEX.md
exit 0
$ grep -qF '%27' src/pathly_data/core/skills/fragments/chief-connect.md
exit 0
$ ! grep -n 'reads it from standard input' src/pathly_data/core/skills/fragments/chief-connect.md
exit 0
$ grep -n 'if your tier' src/pathly_data/core/skills/fragments/chief-connect.md
exit 0
$ python -m pytest tests/http_api/test_chief_cli.py tests/http_api/test_chief_prose_rules.py tests/http_api/test_chief_prompt_text.py tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import sys; t=open('src/pathly_data/core/skills/fragments/comms-post.md').read(); w=t.split('supersede_skipped',1)[1][:700]; sys.exit(0 if all(r in w for r in ('not_found','already_superseded','not_a_decision','other_board','binding','self_reference','error')) else 1)"
exit 0
$ python -c "import sys; fs=('src/pathly_data/core/skills/planning/prd-import.md','src/pathly_data/core/skills/planning/project-decompose.md'); bad=[(f,i) for f in fs for i,l in enumerate(open(f),1) if 'comms?board=project' in l and 'feature=' not in l]; sys.exit(1 if bad else 0)"
exit 0
$ python -m pytest tests/install_skills -q -p no:cacheprovider
exit 0
prints passed
$ FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 21 $(git log --format=%H -n1 --grep='^docs(chief-agent): plan base for ticket 21$')
exit 0
prints floor guard: clean
$ python -c "import pathlib,shutil; [shutil.rmtree(p) for p in pathlib.Path('.').iterdir() if p.name.startswith('C:')]"
exit 0
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib,sys; sys.exit(1 if [p for p in pathlib.Path('.').iterdir() if p.name.startswith('C:')] else 0)"
exit 0
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
$ python scripts/check_adapters.py
exit 0
$ bandit -q -r src/ -ll -x src/pathly_data/
exit 0
```

## Reference

- Where each note came from: the reviews of tickets 03 to 17, kept in the build's notes. The
  items checked and dropped are listed in the report that came with these tickets.
- `scripts/file_size_baseline.txt`, `scripts/check_file_size.py`, `scripts/gen_test_index.py`.
- `tests/conftest.py` (`_isolate_db`) for why a stray watcher is harmful (T5).
- `src/pathly_orchestrator/CLAUDE.md`: "Human messages", "Cited answers", "Cost and run limit",
  the hydration paragraph under "Binding directives".
- Flask raises instead of answering 500 under `TESTING=True`; to see the real answer in a test set
  `app.config["PROPAGATE_EXCEPTIONS"] = False` (T2).

## Answer

### NOT DONE

- **D5, first bullet: what claude does with a Bash command that is not `pathly ...` was not checked.** The ticket says to check it in the chief's tab or against the 2.1.304 measurements. "Human messages" has no measurement of Bash permissions, and no real claude was run for this ticket (a tab and a paid session; spike 19 part B, question 1 is the place for it). The docstring of `claude_settings` now says what the settings do (only `Bash(pathly *)` is allowed ahead of time, `curl` and `wget` are denied, nothing else is said), says that for every other command claude applies its own rule under `--restricted --tools` ("a read-only command runs without asking and the rest ask the human", which is the ticket's statement and not my measurement), and says in the same place that this has not been run against this argv in a real tab. The CHANGELOG sentence from D3 says the same ("every other command is claude's to run or ask about"). `claude --version` here is 2.1.308, not 2.1.304.
- The last sentence of D7 (`pathly-setup claude --apply --repair` copies the new text to an installed machine) is a step for a machine that has the skills installed; it is not part of the repo's checks and was not run.

Nothing else in S1-S6, T1-T8 or D1-D7 is left. That is one item of the fifteen-plus, so the ticket stays `resolved`.

### Built

Commits (all local, none pushed): `0c7ee9f` S1-S6, `0da843f` T1-T8, `f412deb` D1-D7, `d262742` the living-doc entries for the files S1-S6 added, `225cdc9` the HOME fix of the audit test module (below), and the commit with this Answer, `map.md` and `learnings.md`. The work started at `fa1732c`. The message of `0da843f` paraphrases the T items loosely (its T1 and T4 lines are not what those items are); the lines below are the record.

**S (moves, no behaviour change; the route table is the same 177 rules, fingerprint `fa1e371ebe797dc5`)**

- **S1** `comms/messages_read.py` (new, 145 lines) holds `comms_get` (`GET /comms`) and `comms_search` (`POST /comms/search`; the ticket says GET) with what only they use; `messages_crud.py` is 278 lines (was exactly 400); `messages.py` binds `messages_read`, `messages_write`, `messages_crud` and lists them in `ROUTE_MODULES` (no `noqa`); both docstrings say where each route is.
- **S2** `BINDING_REFUSED` is defined in `comms/_helpers.py`; `_supersede_on_post.py` and `messages_crud.py` import it from there.
- **S3** `db/provenance_values.check_author_source` is the one `unknown author_source ...; expected one of [...]` check, called by `post_message` and `update_message_text`; the `update_message_text` re-export is in the import block of `comms_messages.py`.
- **S4** `scope_names.normalise_root` (backslashes to `/`, trailing `/` dropped, a bare `/` or `C:/` keeps one, `""` stays) is used by `chief_session.normalise_project_root`, `comms/_helpers.norm_project_root`, `runner/comms_context` and `runner/board_scope`; `tests/storage_paths/test_normalise_root.py` pins `/p/`, `/p`, `C:\Users\Yafit\proj\`, `C:\`, `/` and `""`.
- **S5** `resolve_run_token` returns the `lookup_run_token` row when `revoked_at` is null, else `None`, and runs no SQL.
- **S6** `runner/comms_binding.py` (new leaf) holds `BINDING_MARK` and `is_binding_row` (`binding == 1`); `comms_governance`, `comms_formatters` and `comms_context` import from it, `comms_governance` imports `render_governance_lines` at the top; `tests/comms_board/test_binding_row_predicate.py` pins `1`, `0`, `None`, `2`, `"1"`, a missing key, and a pending row with `binding` 2 staying pending.

**T (tests; each new test was run against a one-line mutant of the code it guards, see Proof)**

- **T1** `tests/http_api/test_chief_gate_pins.py` (new, 9 tests): the cite rule applies when only one reading of the body is an `answer` (`/comms/acknowledge`, two readings); an empty or missing `board` is the feature board in `_in_project` (own feature kept, other feature refused); `_placed_run` places a run only the registry knows in any status. `test_chief_bind_edges.py`: `" demo"` and `"demo "` added to the padded-scope parametrisation.
- **T2** `tests/http_api/test_chief_gate_fail_closed.py` (new, 8 tests, `PROPAGATE_EXCEPTIONS` off): `get_setting`, `take_run_slot` and `message_board_scope` raising give 500 and the route does not run (`runs_started` stays 0); `give_back_run_slot` raising leaves the 4xx standing, logs a warning and keeps the slot used; `DEFAULT_FLOW_COST_USD` equals the defaults of `start_run` and `RunnerState`. Each failure has a control without the failure.
- **T3** `tests/comms_board/test_hydrate_unverified_rows.py` (new, 31 tests): over `author_source` (absent, `none`, `legacy`, `system`, `token`) by `author_role` (none, `chief`, `builder`), each with `binding` 1, through `insert_message_row` and `hydrate_board`: `binding` is 0, `none` stays `none`, the other sources are `legacy`, an absent one is `legacy` after the backfill, role and run id as the file names them.
- **T4** `test_comms_directives_route.py`: a builder token, no token and the server secret get 403 (not 400) for an invalid body (not an object, a blank `project_root`, a bad `to_agent`); a bad `to_agent` (upper case, padded, 41 characters) is 400; 8,192 bytes of text with whitespace on both sides is 201 and 8,193 bytes stripped is 400. `test_comms_directives_fields.py`: the not-an-object test asserts 400 (it accepted `(400, 403)`). `test_binding_directive_hardening.py`: U+2028 written as `\u2028`; the fail-soft test asserts exactly one "standing orders unavailable" warning.
- **T5** `tests/chief_session_guard.py` (new) defines `_no_watcher_outlives_its_test` once (closes open chiefs, waits up to 5 s for the threads the test started, fails if one is alive, fails on a board lock the test itself left held, drains the two mirrors); the five places import it (`chief_cli_support.py`, `test_chief_routes.py`, `test_chief_session.py`, `chief_human_support.py`, `chief_acceptance_support.py`, plus `chief_open_support.py`, which had a sixth copy); `tests/consistency/test_chief_tests_use_the_guard.py` (new, 32 tests) fails for a test module that opens a chief (`open_chief(`, `open_with(`, `open_session(` or `"/chief/open"`) and does not import the guard by name, and for a support module that stops importing it; `test_chief_cli.py` without the import is one of its cases.
- **T6** `test_chief_acceptance.py` / `chief_acceptance_support.py`: the stray "Quotes and a line break" comment is deleted; the `PUT` of the ceiling sends a different value and `GET /chief/session` still reports the old ceiling; `10.0` and `20` are `chief_budget.DEFAULT_CEILING_USD` and `DEFAULT_RUN_LIMIT`, the other cost numbers have names (`ABOVE_THE_CEILING`, `BELOW_THE_CEILING`, ...); `SpawnHost.seen` is removed; the status is asserted before `own.get_json()["run_id"]` is read.
- **T7** help lines of `/comms/answer` and `/runner/agent-answer` show exactly `{question_id, cite}` and `{topic, cite}`; the help says a chief never sends an answer of its own; a subprocess with `PYTHONIOENCODING=cp1252`, `PYTHONUTF8=0` and a non-ASCII body and answer reads and prints UTF-8 (`_use_utf8`); `DEFAULT_HOST == "127.0.0.1"`; the token is absent from stdout and stderr for every bad usage; the "may not" sentences of the status and planner texts are checked against `TIERS`; the `/comms/supersede` example is run with real ids (placeholders replaced by name, so a swapped pair fails); "no server" uses a port that was bound and released (`released_port()`).
- **T8** `pytest.raises` in `test_chief_tables.py`; `test_bad_input_is_a_value_error...` is parametrised on `BAD_INPUTS` (ten ids), not `range(10)`; the `C:\Users\Yafit\demo\` folder came from `test_project_decompose.py` (the route makes `<root>/pathly/project` for a Windows-style root), which now records the `makedirs` call and asserts it, and the stray folder is gone; the audit's `climbing` value is `os.path.relpath(world.other / "planted", world.server)` with a test that the normalised join lies in the other project; `test_chief_tiers.py` pins that the front-matter block the tier is read from equals what `strip_front_matter` removes (end of text, CRLF, trailing blank lines, none), and that a quoted tier is `status` (said in the `_front_matter_tier` docstring too).

**D (docs; each check fails at `fa1732c` and passes now, see Proof)**

- **D1** "recorded as typed" / "shows" in `src/pathly_orchestrator/CLAUDE.md` ("Cited answers", "What a citation proves"), `chief_cite.py`, the first line of `pathly_hooks/chief_prompt.py` and the `chief/` entry of the root `CLAUDE.md`.
- **D2** root `CLAUDE.md` says 18 files; `docs/ARCHITECTURE.md` lists the four hook scripts and which is which (`stop_telemetry.py` is wired by install, `chief_prompt.py` by the server into a session's settings, `classify_feedback.py` and `inject_feedback_ttl.py` ship with the package and no install file wires them); `docs/API.md` gives the `/code/query` cache key as project root, op, target, content hash, backend.
- **D3** the `(chief-agent)` entry of `CHANGELOG.md` and the acceptance test's docstring say "spike 19 part B" and list what stays unmeasured; the CHANGELOG says only `POST /runs` of a flow and the `retry` verb state a cost, so goal, board and task runs are bounded by the run count alone (a goal's own cap is `goal.max_cost_usd`).
- **D4** five edits in `src/pathly_orchestrator/CLAUDE.md` and the `comms_directives` docstring; findings in Decisions.
- **D5** `claude_settings` and `chief/session.py` docstrings; the six test docstrings describe what the test checks; `gen_test_index.py` regenerated; no "round 2" is left in the two INDEX files.
- **D6** `chief-connect.md` and `ROOT_LINE`: `'` is `%27` in a query string, `"` and `'` take the JSON escape in a body, the `-` sentence is gone, "if your tier holds `answer`" (and "If your tier does not hold `answer`, or Pathly gave you no number ... tell them where to answer"); `test_chief_prose_rules.py` pins all of it, and a `shlex.split` test runs every `pathly api` example of the four texts with the root `/home/o'brien/my proj` written the way the text says, plus a negative control (a bare apostrophe makes `shlex.split` raise); `test_chief_help_routes.py` has an end-to-end test of a root with `'` and `"` through a real chief.
- **D7** `comms-post.md` lists the seven `supersede_skipped` reasons (`not_found`, `already_superseded`, `self_reference`, `not_a_decision`, `other_board`, `binding`, `error`); `prd-import.md` (2) and `project-decompose.md` (3) read the project board with `&feature=project` (without it the route answers `400 Query parameter 'feature' is required`, measured); six golden snapshots changed by exactly that sentence (`git diff -U0 tests/snapshots` shows only it).

Also: `d262742` adds to `src/pathly_orchestrator/CLAUDE.md` what S1-S6 added (the three message modules, `comms_binding.py`, `check_author_source`, `normalise_root`); the S commit left those entries as they were. `225cdc9`: `test_chief_gate_audit.py` left `~/.pathly/pathly.db` in an empty HOME in 3 of 3 runs at the plan base (a mark queued by its last test, written by `board-mirror-flusher` after the home was no longer patched; found with an audit hook that printed the thread); it now imports the existing per-test drain `mirror_drain_support._mirrors_are_drained`: 0 of 4 runs leave anything. The same commit moves a comment in `test_chief_session.py`.

Existing tests changed, and why: T1 `test_chief_bind_edges.py` (two cases added to a parametrisation); T4 `test_comms_directives_route.py` (new tests only), `test_comms_directives_fields.py` and `test_binding_directive_hardening.py` (the 400 assertion, the `\u2028` escape, the exact warning count); T5 the six support/test modules that defined or copied the guard; T6 the acceptance pair; T7 `chief_cli_support.py`, `test_chief_cli_edges.py` (port), `test_chief_cli_input.py`, `test_chief_help_routes.py`, `test_chief_prompt_text.py` (new tests; the port test); T8 the five files named above; D5 six docstrings (no code); D6 `test_chief_prose_rules.py` (the stdin pin replaced by "the fragment does not offer standard input but `pathly help` still does", the encoding and root-line pins extended); D7 six golden snapshots; `225cdc9` one import. No test was loosened to pass.

### Proof

Test first: no, so there is no test-only commit. The tree at each commit passes its own folders; the proof below is on the final tree (the commit that holds this Answer changes only `map.md`, `learnings.md` and this file).

**Mutants (one-line changes to a scratch copy of `src/`, or to the real file for a test that runs a subprocess; each restored).** Each was killed by the new test named:

- T1 `any(` to `all(` in `chief_gate` (`_cite_refusal`): 1 failed, `test_the_cite_rule_applies_when_only_one_reading_of_the_body_is_an_answer`. `board or "feature"` to `board` in `chief_bind._in_project`: 3 failed. `statuses=None` dropped in `_placed_run`: 3 failed.
- T2 `get_setting` error swallowed in `chief_budget._number_setting`: 2 failed. `take_run_slot` error swallowed: 1 failed. The give-back `except Exception` narrowed to `KeyError`: 1 failed (`..._leaves_the_4xx_standing`). `DEFAULT_FLOW_COST_USD` 1.0 to 2.0: 1 failed.
- T3 `binding` reset only for a `token` row in `comms_hydrate._unverified`: 25 failed of 31.
- T4 the body read before the caller is checked in `comms_directives`: 3 failed (`test_the_caller_is_checked_before_the_body_is_read[not an object-builder|nobody|secret]`).
- T5 the import removed from any one module, from a support module, or aliased: the cases of `test_chief_tests_use_the_guard.py` (32 tests) fail by construction (each case edits the text it scans).
- T7 `_use_utf8` turned into a no-op in the real `chief_cli.py`: 3 failed (the three code-page tests). `DEFAULT_HOST` to `"localhost"`: 1 failed (`test_the_token_goes_to_this_machine_and_to_no_other_address`).
- T8 `_front_matter_tier` reading the whole text instead of the block `strip_front_matter` removes: 5 failed.
- A leak hunt with a throwaway plugin (`pytest_runtest_teardown`, `trylast`) over `tests/comms_board` found one leaker of a board lock: see For later tickets.

**Documentation checks.** All 40 non-test-running commands of the `check` block (greps, `python -c` file reads, the S-item import checks) were run on `git archive fa1732c` with `PYTHONPATH` at its `src`: 39 fail, the route fingerprint passes (it must). On the final tree all 40 pass (`PYTHONDONTWRITEBYTECODE=1`, see Shortcuts).

**The `check` block, on the final tree.** Every command exits as written: the S, T and D checks, `black --check src/ tests/` (702 files unchanged), `mypy src/ --ignore-missing-imports --no-strict-optional` (no issues in 345 files), `lint-imports` (1 kept, 0 broken), `check_file_size.py` (`18 known over 400 lines, none new, none grown`), `check_no_mirror_reads.py`, `check_version_sync.py` (2.24.1), `check_adapters.py`, `check_entry_points.py`, `bandit -q -r src/ -ll -x src/pathly_data/` (exit 0), `gen_test_index.py --check`, the route table (177 rules, `fa1e371ebe797dc5`, the same as at the base), `messages_crud.py` 278 lines (check: under 340). The `C:*` check passes before and after the full suite (no stray folder). Floor guard: `floor guard: clean`, run from the commit `docs(chief-agent): plan base for ticket 21` (`fa1732c`).

**commands.md.** Build `python -m build --wheel`: exit 0 (`pathly_adapters-2.24.1-py3-none-any.whl`). Smoke: exit 0. Lint: the chain above, exit 0 for every link. Test (the four folders) is a subset of the full suite below.

**Full suite**, `python -m pytest tests/ -q -p no:cacheprovider`, on the final production tree: `6467 passed, 14 skipped in 1461.89s (0:24:21)`, exit 0. The first run, one commit earlier, was `1 failed, 6466 passed`: `tests/dag_goals/test_prd_import_new.py::test_prd_import_requires_idempotency_before_feature_and_goal_posts` pins `board=project&scope=$PROJECT&type=feature`, which D7 had changed. The four folders of the Test command do not read that file; only the full suite found it. Fixed by appending the parameter (`cca0678`, Decisions), not by editing the test. A detached `pathly_orchestrator.http_server` was left on 127.0.0.1:8765 by each full run (as `learnings.md` (20) says); killed by pid after each, and before the second run.

**Python 3.11 / 3.12 / 3.13, empty HOME.** The 34 test files that are new, changed, or import a changed support module (1,161 tests) passed on 3.11.17, 3.12.3 and 3.13.16, each in its own venv, with `HOME` set to an empty folder. On the first pass 3.11 and 3.13 left the folder empty and 3.12 left `.pathly`: the cause was `test_chief_gate_audit.py` (bisected by file; an audit hook showed `board-mirror-flusher` opening the home) and it left the same folder at the plan base (3 of 3), so it was there before; fixed in `225cdc9`. After `225cdc9`, on the final tree: all 34 files pass on 3.12.3 (1,161 tests, `355.60s`) and leave the folder empty; the two files changed since the first pass, `test_chief_gate_audit.py` and `test_chief_session.py`, pass on 3.11.17 and on 3.13.16 (60 tests each) and leave it empty. The first pass had already left it empty on 3.11 and 3.13 for the other 32 files.

### Decisions

- **T5, the guard asserts against the start of the test, not an empty table.** The ticket says the guard asserts `board_lock._held` is empty. With that rule 46 tests of `test_comms_directives_route.py` errored in a run over `tests/comms_board`: `test_comms_body_encoding.py::test_every_comms_post_route_reads_a_cp1252_body` leaves `('project', 'project')` held (found with the leak-hunt plugin) and the guard blamed every later test. The guard keeps a copy of `board_lock._held` at the start of the test and fails the test for a lock that is held at the end and was not held (by that run) at the start; it still never clears one. A scenario that takes a lock still has to release it in its own teardown. The leaker is not touched (below).
- **T5, one exemption in the scan.** `http_api/test_chief_gate.py` contains `/chief/open` as the name of a route a non-chief is refused, and never opens a chief. `EXEMPT` names it with the reason, and a test checks the reason is still true (it still matches the scan, calls no opener, imports no guard). A support module's copy of the guard (a sixth, in `runner_supervisor/chief_open_support.py`) was replaced too. The guard asks for the module's own `chief_root` fixture when there is one, so the sessions folder is still patched when the chiefs are closed.
- **T7 / D6, `-` stays in the command and in `pathly help`;** only the fragment's sentence went. The pin is now "the fragment does not say `standard input`, and `pathly help` does".
- **D4 findings (Check first).** (1) An empty `project_root` reaches the route and is 400 (`test_a_chief_that_names_no_project_gets_a_400[empty]`); a string of spaces is truthy and not the session's root, so `chief_project._foreign_root` answers 403 `that is not this chief's project` before the route is reached. Both are in the docstring and in `src/pathly_orchestrator/CLAUDE.md`. (2) The route that makes `<project_root>/pathly/features/<name>` is `POST /comms/features/decompose` (`plan`, so a planner or operator chief), at every rigor, for any single-folder `feature`; a post to a feature board makes no folder. (3) The two-cites window is real by reading, not by a test: `supply_agent_answer` only checks that the run still awaits an answer and stores the new one, and `_await_agent_question` clears the flag after its 50 ms poll sees an answer. (4) `hydrate_project` lists the project scope under `skipped` for a clone at another path or another letter case (ticket 20); feature boards are keyed by name and are unaffected. (5) `/comms/edit` goes through `update_message_text`, which changes the text and re-stamps the row's three author columns to the editor, so "posting or editing" is right.
- **D5, wording of the Bash sentence.** It says what the settings do, what claude does by the ticket's account, and that it is unmeasured on this argv (NOT DONE above). The `chief/session.py` docstring says "today a person (or a script they run) calls `POST /chief/open` directly".
- **D6, `ROOT_LINE` says "a double quote or an apostrophe", not the escapes.** The escapes are in the fragment the line follows; a backslash is not mentioned because a stored root has none (`normalise_root`). `chief_cli.HELP` was not changed (not in the ticket's files; see For later tickets).
- **D7, `&feature=project` goes after `type=feature`, not before.** The chief texts write `feature=project&type=...`; the three `type=feature` reads in the skills write `type=feature&feature=project`, because `test_prd_import_new.py` (not an item the ticket lets me edit) pins the substring `board=project&scope=$PROJECT&type=feature`. The query means the same either way; the check (no `comms?board=project` line without `feature=`) passes.
- **Extra work beyond the items,** each for a reason: `d262742` (the S moves left `src/pathly_orchestrator/CLAUDE.md` without their files, which the repo's documentation-sync rule asks for) and `225cdc9` (a changed test that left `~/.pathly` behind with an empty HOME).

### Shortcuts taken

- No real `claude` was started: D5's Bash behaviour and D6's text are checked against the code and the tests, not against a live tab (spike 19 part B).
- T1-T8 were mutation-checked with one or two mutants per new test (list in Proof), not exhaustively; T5's scan is tested by editing the text it scans rather than by running a chief without the guard.
- The `check` line `test "$(grep -rl 'unknown author_source' src/pathly_orchestrator | wc -l)" = 1` counts `__pycache__/*.pyc` files, which hold the message as a constant: with bytecode on disk (any earlier import in the same checkout, or a stale `cpython-311` file) it prints 2 or more. It passes on a tree with no bytecode (`PYTHONDONTWRITEBYTECODE=1`, or `find src -name __pycache__ -prune -exec rm -rf {} +` first; the S3 code is right: one `.py` holds the message). `grep -rl --include='*.py'` would not depend on it. I did not change the ticket's check.
- The `0da843f` message describes T1 and T4 loosely (see Built); history was not rewritten.

### For later tickets

- `tests/comms_board/test_comms_body_encoding.py::test_every_comms_post_route_reads_a_cp1252_body` leaves the `('project', 'project')` board lock held after it ends (and, on 3.13, writes the real HOME, as before). Release the lock in its teardown; then `chief_session_guard` could assert an empty table again.
- `chief_cli.HELP` tells a chief to write a `+`, `&` or `%` of the root as `%2B`, `%26`, `%25` in a query string and nothing about `'` (`%27`) or the JSON escape; the fragment and `ROOT_LINE` now do. Add it to `HELP` (and to `test_chief_help_routes.py`).
- `src/pathly_orchestrator/CLAUDE.md` still says "typed after" in the table row "a human gate is closed" (line ~486) and in the `chief_cite.py` entry of the file map (line ~1653); D1 named other places. `CLOSE_REASON = "closed from Studio"` in `chief/session.py` is a string the server stores while Studio has no way to close a chief yet.
- The other copies of the root idiom S4 left (`board_mirror.py`, `fsm_compose_paths.py`, `db/queries/skill_composition.py`, `db/queries/prompt_library.py`, `comms/project.py`, `fsm_ops.py`) still spell `replace("\\", "/").rstrip("/")`.
- The Test command (four folders) does not read `tests/dag_goals` or `tests/install_skills`, which pin the text of skills and fragments. A ticket that edits a skill or a fragment should run them as well; the full suite is what found it here.
- Not in this ticket, noticed: the iterative-walker 900-deep test, `_printable` trim edge cases, and the other duplicated drain-mirror helpers (`chief_audit_sandbox.drain_the_mirrors`, `mirror_drain_support.drain_mirrors`, `binding_guard_support`) were left as they were.
