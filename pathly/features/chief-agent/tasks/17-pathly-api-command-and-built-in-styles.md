# Make round one usable: a `pathly api` command and built-in style texts

Type: task
Status: resolved
Blocked by: 06, 07, 08
Test first: yes

Without this ticket, nobody can use the chief at the end of round one. The claude chief may run
only `Bash(pathly *)` without asking (ticket 06), but no `pathly` command exists, and no style has
any text. Ticket 06 also denies curl. This ticket adds the smallest command that reaches every
route and three plain style texts. Round two keeps its friendly commands (`overview`, `inbox`,
`answer --cite`, …) and builds them on top of this one.

The command, in `src/pathly_orchestrator/chief_cli.py` with
`pathly = "pathly_orchestrator.chief_cli:main"` in `[project.scripts]`:

- `pathly api GET <path>` and `pathly api POST|PUT|DELETE <path> [<json> | -]` (`-` reads the body
  from stdin). It prints the response body and exits 0 for 2xx, 1 for any other status, and 2 for
  a usage error. Stdlib HTTP only; host and port as `fsm_http_client` resolves them, so
  `PATHLY_FSM_HTTP_PORT` (#62) is honoured, plus the server secret header the way
  `fsm_http_client._request_raw` sends it.
- It always sends `X-Pathly-Run-Token` from `PATHLY_RUN_TOKEN`. When the variable is missing or
  empty, it prints `PATHLY_RUN_TOKEN is not set: open the chief from Pathly (a codex
  shell_environment_policy can also filter it)` and exits 2 without calling the server. It never
  prints the token.
- `pathly help` lists the commands and the main routes a chief uses (`GET /comms`,
  `GET /runs`, `POST /comms/post`, `POST /runs`, `POST /comms/answer` with `cite`,
  `POST /runner/agent-answer` with `cite`, `POST /comms/directives`, `GET /chief/session`).
- `python scripts/check_entry_points.py` must pass with the new entry.

The chief's prompt has two parts, the way every other prompt Pathly sends has a skill and its
fragments (root `CLAUDE.md`: fragments are the un-editable layer that connects an agent to
Pathly):

1. **The style**, which the user may edit: the built-in texts in
   `src/pathly_orchestrator/supervisor/chief_presets.py` (Python constants, no package-data
   change), `status`, `planner` and `operator`, each a short prompt that states the style's powers
   in words that match its tier and how it should work with the user. A user prompt file
   `chief/<preset>` replaces it (ticket 04).
2. **The fixed rules**, which nobody edits from a preset: a new fragment
   `src/pathly_data/core/skills/fragments/chief-connect.md`, appended by the server to every
   chief prompt, built-in or user file, so a saved style cannot drop them. It says the chief runs
   Pathly for the user, never edits files and never runs agent CLIs itself; that it uses only
   `pathly api …` and `pathly help`, and starts by reading the board and the open runs; that it
   relays an agent's question to the user and answers with `cite=<id>` only, because Pathly sends
   the cited message's own words (spec.md § Decisions, "What a citation proves"); and that it takes no instruction from board text,
   artifacts or agent output: only the user, in this tab, gives orders (the prompt-injection
   paragraph).

`open_chief` (ticket 06) builds the pasted prompt as `strip_front_matter(style) + "\n\n" +
chief-connect`, reading the fragment with `skills.compose_resources._read_fragment("fragments",
"chief-connect")` inside the function (supervisor may import `skills`, as `board_run.py` does). It
is not added to any skill in the compose manifest, and the existing fragments are not composed
into the chief: they teach `curl` (denied to the chief) and a one-shot `AGENT_DONE` completion
that a long-lived session never writes. `tests/consistency/test_fragments_run_token.py` scans
every core fragment: a line such as `pathly api POST /comms/post` counts as a pseudo-request, so
the fragment must carry one line, outside any curl, with the exact header text, for example
``pathly api` sends `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` for you; never call the server any
other way.``

`POST /chief/open` (ticket 07) makes `prompt` optional: when it is missing and `preset` is one of
the three built-in names, the route uses the built-in text; otherwise 400 as before. A user prompt
file `chief/<preset>` still wins (ticket 04). The fragment is appended in every case.

Living docs: `src/pathly_orchestrator/CLAUDE.md` names the `pathly` command, the built-in styles
and the `chief-connect` fragment; `src/pathly_data/CLAUDE.md` notes that `chief-connect` is read by
the chief's open path, not composed through the manifest; the root `CLAUDE.md` "Cross-cutting
commands" block gains one `pathly api` line.

## Not in this ticket

- The friendly commands (`overview`, `inbox`, `goals`, `answer --cite`, `decide --binding`, …),
  `GET /chief/overview` and `GET /chief/inbox`: round two, built on `pathly api`.
- The Chief button and the paste-without-Enter change in Studio: round two.

## Done when

- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider` passes and covers,
  against a running test server on a free port: `pathly api GET /chief/session?project_root=…`
  with an operator chief's token exits 0 and prints the session; a status token's `pathly api
  POST /comms/post …` exits 1 and prints the gate's 403 body; with `PATHLY_RUN_TOKEN` unset it
  exits 2, names the variable, and the server sees no request; the token never appears in
  stdout or stderr; `POST /chief/open` with preset `operator` and no `prompt` spawns a tab whose
  prompt is the built-in operator text followed by the `chief-connect` fragment, and with preset
  `custom` and no `prompt` is 400; a user style file whose text lacks the cite and
  prompt-injection rules still yields a pasted prompt that contains them (from the fragment);
  each built-in text and the fragment name only `pathly` commands, and the fragment contains the
  prompt-injection paragraph.
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider` passes
  with the new fragment.
- `python scripts/check_entry_points.py` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_entry_points.py
exit 0
```

## Reference

- `src/pathly_orchestrator/fsm_http_client.py` (`_base_url`, `_load_secret`, `_request_raw`)
- `src/pathly_orchestrator/skills/compose_resources.py::_read_fragment`;
  `tests/consistency/test_fragments_run_token.py` (`_PSEUDO`, the header instruction line);
  spec.md § Decisions ("The chief's fixed rules")
- ticket 06 (`claude_settings`: `Bash(pathly *)` allowed, curl and wget denied), ticket 07
  (`POST /chief/open`), ticket 04 (`resolve_preset_tier`, `strip_front_matter`), ticket 10 (the
  cite rule the operator text explains)
- map.md § Round two, items 1 to 3 (what stays for round two)

## Answer

### Built

Source:

- `src/pathly_orchestrator/chief_cli.py` (new, 194 lines): the `pathly` command. `pathly api GET <path>`,
  `pathly api POST|PUT|DELETE <path> [<json> | -]`, `pathly help` (also `-h`, `--help`). It sends one
  request with `http.client` (not urllib, so no `# nosec` is needed) to `fsm_http_client.DEFAULT_HOST`
  and `config.fsm_port()` (so `PATHLY_FSM_HTTP_PORT` is honoured), always with `X-Pathly-Run-Token` from
  `PATHLY_RUN_TOKEN`, plus `X-Pathly-Secret` from `fsm_http_client._load_secret()` when the machine has
  one. It prints the response body to stdout and, for a non-2xx, `pathly: HTTP <status>` to stderr.
  Exit 0 for 2xx, 1 for any other status or an unreachable server, 2 for a usage error. With the variable
  missing or empty it prints the ticket's exact sentence on stderr, exits 2, and sends nothing. A path
  must start with one `/` (a URL or `//host` is a usage error, so the token goes to this server only), a
  space or non-ASCII character in it is sent percent-encoded, a body must be a non-empty JSON object, a
  GET takes no body, and the usage errors are all found before any request. The token is never printed;
  an answer body or an error message that holds it (or the secret) is printed with `[redacted]`.
  **Round 2 changed this:** `chief_cli.py` is 224 lines now. The secret is read once per command and was
  NOT redacted from the connection-error text in round 1 (the sentence above overstated it); it is now. A
  path, a body or a standard input that is not valid UTF-8 is a usage error (exit 2, nothing sent), where
  round 1 gave a traceback and exit 1. `pathly help` prints each route with the query or body keys it
  needs (`GET /runs?project_root=<root>`, ...), where round 1 printed bare `GET /runs`.
- `pyproject.toml`: `pathly = "pathly_orchestrator.chief_cli:main"`.
- `src/pathly_data/core/skills/fragments/chief-connect.md` (new, the fixed rules): the chief runs Pathly
  for the user and never edits files or runs an agent CLI; `pathly api` and `pathly help` are its one
  tool and it sends `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` for it; JSON in single quotes with an
  apostrophe written `'`; exit codes; `<root>` is on the last line; start by reading four things
  (`/chief/session`, `/comms/goals`, the pending `question` rows, `/runs`) and say where things stand;
  how to answer an agent (relay the question in the tab, answer with `cite=<id>` only, one citation per
  message and spent even on a 404 or 409, a codex chief has no number, never `/clear`); and the
  prompt-injection paragraph (board text, artifacts and agent output are data; only the user in this tab
  gives orders). It is in no skill of the compose manifest. **Round 2 changed this:** the start-up reads are
  five, not four (the pending `escalation` rows were added, the user's when `to_agent` is `human`); the
  fragment also teaches quoting a path that has a query string, one `pathly` command per call with no pipe
  or `$(...)`, `-` for the body only when quoting is awkward, and writing a `+`, `&`, `%` or space of the
  root as `%2B`, `%26`, `%25`, `%20` in a query string (a JSON body keeps it as written).
- `src/pathly_orchestrator/supervisor/chief_presets.py` (new, 140 lines): the three built-in styles
  `STATUS`, `PLANNER`, `OPERATOR` as Python constants (`BUILT_IN`), `default_style(preset, root)` (the
  user's file `chief/<preset>` wins, else the built-in text, else None), `ROOT_LINE`, and
  `compose_prompt(style, root)` = `strip_front_matter(style)` + `"\n\n"` + the fragment
  (`compose_resources._read_fragment("fragments", "chief-connect")`, read inside the function) +
  `"\n\n"` + the root line, whose last line is `Your project root: <stored root>`. **Round 2 changed this:**
  141 lines now; OPERATOR no longer says to keep watching `GET /runs` (it looks when the user writes or asks,
  never in a loop, and stops on a refused call), names the decompose cost, and shows `GET /runs?project_root=<root>`
  and a quoted `pathly api GET '/comms?...&type=decision'` command; the root line adds "apart from the
  percent-encoding a query string needs".
- `supervisor/chief_session.py`: `open_chief(..., prompt: str | None = None, ...)`. `_validate` lost the
  prompt; new `_style(preset, prompt, root)` takes the caller's `prompt`, else `default_style`, else
  `ValueError("prompt is required for preset ...: only status, planner, operator have a built-in text")`,
  then the old checks (a string, not blank, at most 64 KiB) on the style; the spawn payload's `prompt` is
  `compose_prompt(style, stored root)`. `http_server/blueprints/chief/session.py`: `prompt` is no longer a
  required field; if the key is present it must be a string (`null` is a 400), and `None` is passed on.

Living docs (verify-then-fix; nothing rewritten):

- `src/pathly_orchestrator/CLAUDE.md`: the `POST /chief/open` line (`prompt?`); two new bullets in "Chief
  endpoints" ("The prompt a chief is pasted", "`pathly api METHOD /path [json | -]`"); the sentence at the
  gate keys ("the keys a chief's prompt may name (ticket 17)"); the "Not here yet" paragraph, which said
  ticket 17 must teach the root, the keys, the artifact path and the `/code/query` target, and must hand
  the chief the stored root: it now says what is done (`ROOT_LINE`) and what is still not taught; the
  package tree (`chief_presets.py`, `chief_cli.py`, and the `chief_session.py` line that said "prompt
  non-empty" and "prompt without front matter"); "CLI shortcuts".
- `src/pathly_data/CLAUDE.md`: `root-cause-debug.md` is now "one of two fragments outside
  `composition.yaml`", and a bullet says `chief-connect` is read by the chief's open path, not composed.
- Root `CLAUDE.md` "Cross-cutting commands": one `pathly api` line.
- Checked and left alone: `README.md`, `studio/CLAUDE.md`, `docs/WHAT_IS_PATHLY.md` carry no claim this
  ticket makes false (the Studio launcher still sends a `prompt`, which is still accepted).

Tests (test-only commit `e44893d`, then changed in this commit):

- `tests/http_api/chief_cli_support.py` (the `server` fixture: the real Flask app on a free port behind a
  wrapper that records each request; `stub`; `pathly`; `host`), `test_chief_cli.py` (the Done-when
  tests), `test_chief_cli_edges.py` (usage errors, help routes exist and a chief may call them, bodies
  and stdin, statuses, redaction, secret header, unreachable server, PUT and DELETE refused by the gate,
  a cited answer end to end through the command, console-script entry, a real subprocess, the
  apostrophe rule), `test_chief_prompt_text.py` (every `pathly api` example in a text against the gate's
  tables, and run against a real server).
- Two existing tests changed on purpose, because they pinned the old behaviour: `tests/runner_supervisor/
  test_chief_session.py` (the pasted prompt was the style alone; the 64 KiB test now reads the style; a
  missing `prompt` was an error for every preset, now only for a preset with no text) and
  `tests/http_api/test_chief_routes.py` (`prompt` dropped from the missing-field list).
- `tests/INDEX.md`, `tests/http_api/INDEX.md`, `tests/runner_supervisor/INDEX.md` regenerated.
- **Round 2 added** (test-only commit `51c4651`, then the fix commit): `tests/http_api/test_chief_cli_input.py`
  (non-UTF-8 input, the secret), `test_chief_help_routes.py` (what each help route needs, checked against the
  routes; a root with `+ & %` in a query), `test_chief_prose_rules.py` (the rules pinned by phrase, quoting,
  one command per call, the start-up reads), `chief_text_support.py` (helpers). `chief_cli_support.py`: the
  `server` fixture closes its socket and `pathly(..., stdin=bytes)` decodes like a pipe. The guard
  `_no_watcher_outlives_its_test` is now imported by `test_chief_cli.py`, `test_chief_cli_edges.py` and
  `test_chief_prompt_text.py`; `_routes_in` in `test_chief_cli_edges.py` drops a help line's query before it
  compares the route (the assertions are the same). `tests/http_api/INDEX.md` and `tests/INDEX.md` again.

### Proof

Round-1 numbers (Python 3.12.3); the round-2 numbers are under "Review fixes (round 2)":

- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider`: `23 passed`, exit 0.
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider`: `41 passed`,
  exit 0.
- `python scripts/check_entry_points.py`: `Entry points OK: 17 checked` (lists
  `pathly = pathly_orchestrator.chief_cli:main`), exit 0.

Also run:

- `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`
  (the commands.md Test command): `4059 passed, 2 skipped` (the skips are not in my files), exit 0. After
  it I added three tests, strengthened one assertion, and changed one sentence of the fragment (the
  apostrophe rule), so I re-ran `tests/consistency`, `tests/runner_supervisor/test_chief_session.py` and
  `tests/http_api -k "chief or fragment or consisten"`: `2263 passed, 155 deselected`, exit 0;
  `tests/consistency` alone: `57 passed`.
- Python 3.13.16 (`venv313`), the five new or changed chief files plus the fragment test: `177 passed`.
- `black --check src/ tests/` (672 files unchanged), `mypy src/ --ignore-missing-imports
  --no-strict-optional` (343 files, no issues), `check_file_size.py` (`none new, none grown`),
  `check_no_mirror_reads.py` OK, `gen_test_index.py --check` up to date, `lint-imports` (1 kept, 0
  broken), `bandit -q -r src/ -ll -x src/pathly_data/` exit 0, `check_adapters.py` OK,
  `check_entry_points.py` OK, `check_version_sync.py` OK (2.24.1).
- `python -m build --wheel`: built `pathly_adapters-2.24.1`; the wheel holds `pathly_orchestrator/chief_cli.py`,
  `pathly_orchestrator/supervisor/chief_presets.py`, `pathly_data/core/skills/fragments/chief-connect.md`
  and the `pathly = pathly_orchestrator.chief_cli:main` entry point. With the unzipped wheel alone on
  `sys.path` (`python -I`), `compose_prompt(BUILT_IN["status"], "/proj/root")` reads the fragment and ends
  with `Your project root: /proj/root`.
- Test first: `e44893d` holds only test files; on the base source its run failed (missing `chief_cli`,
  `chief_presets` and the fragment), not on a collection typo. The floor guard scan of the whole diff
  against the base found no `skip`, `xfail`, `noqa`, `nosec` or `type: ignore` added, and the only test
  lines removed are the three assertions named above.
- Mutation checks, in a scratch copy (`scratchpad/rv17`), 50 mutants of my own code and texts, one per
  behaviour: exit code of 2xx, of a non-2xx and of a usage error; the missing-token path (still sends,
  exits 1, message changed, printed to stdout); body and error-message redaction removed; the token
  header and the secret header not sent; `PUT` not accepted; method not upper-cased; a URL accepted as a
  path; a body not checked as JSON; `-` ignored; a GET body allowed; an unreachable server raising;
  the content type not sent; the path not percent-encoded; `prompt` required again by the route;
  `null` accepted; a custom preset given a built-in text; the user file ignored; the fragment dropped
  (always, for a given prompt, for a user file); the root line dropped or not last; front matter not
  stripped; the 64 KiB limit loosened; a blank style accepted; each fragment rule removed (injection
  paragraph, header line, cite rule, `/clear`, apostrophe, limit field names); fragment, planner and
  status examples turned into a refused call (a write, a key not listed, a post not `from` the chief, an
  unknown route, an answer with words of the chief's, an agent answer without `cite`, a run without
  `project_root`, an unlisted `PUT`). Five survived the first pass and are fixed: `error redaction
  removed` (new test `test_an_error_that_holds_the_token_is_printed_without_it`), `fragment: header line
  removed` (my first mutation list left out the consistency test; `test_fragments_run_token.py` kills it
  and I added the exact header line to `test_the_fragment_teaches_the_command_and_its_help`), `fragment:
  clear rule removed` (the assertion `"/clear" in prompt` was too weak, now `never run /clear`), and two
  equivalent mutants (`limit` and `model` are listed keys), redone with an unlisted `bogus` key and
  killed. All 50 are killed in the final run.
- Reading the texts as a model would, I found a real mistake the tests did not catch at first: the
  fragment told the chief to write an apostrophe inside the single-quoted JSON as `'`, which ends the
  quotes in a shell. It now says the JSON escape `'`, and a test posts a goal through the command with
  one and reads the decoded text back.

### Prompt-text claims, each checked against code

(The examples themselves are also read against `ROUTE_FIELDS`, `action_for` and the tier actions by
`test_chief_prompt_text.py`, and run through the real command.)

- A chief reaches the server only with `pathly`: `Bash(pathly *)` allowed, `curl` and `wget` denied
  (`runner/chief_argv.py:13`, `:24-25`); the token reaches the process through `PATHLY_RUN_TOKEN`
  (`runner/chief_argv.py:6`).
- A refused call is a 403 whose body names the actions the tier holds: `{error, action, tier, allowed}`
  (`http_server/chief_gate.py:35`); tiers: status = read, planner = read, post, plan, operator = all seven
  (`supervisor/chief_tiers.py:18-26`).
- The gate compares `project_root` with the stored spelling (`scope_names.py:62` `root_spelling`;
  `chief_sessions.project_root`), which is why the last line of the prompt is the stored root
  (`chief_presets.py` `ROOT_LINE`; pinned with a trailing-slash root by
  `test_the_operator_prompt_ends_with_the_root_exactly_as_the_session_stores_it`).
- `GET /chief/session` reports `runs_started`, `max_runs_per_session`, `max_cost_usd_per_run`
  (`blueprints/chief/session.py:186-188`); `chief_budget.py:83-102` `ceiling_usd`, `run_limit`. The texts
  name the fields and no number. A run start that answers non-2xx hands the slot back
  (`chief_budget.py:182` `refund_run_slot`), shown by the 404 test.
- `GET /comms` needs `feature` even for the project board (`blueprints/comms/messages_crud.py:22-24`
  answers 400 without), so every example carries `board=project&scope=<root>&feature=project`; `board`
  defaults to `feature` and `scope` to the feature name (`messages_crud.py:26-29`), so the project board
  must name both.
- Reads a status chief may make: `/comms`, `/comms/goals`, `/comms/tasks`, `/runs`, `/runs/<run_id>`,
  `/chief/session` (`chief_field_reads.py:107-116`; `chief_routes.py` `ROUTE_ACTIONS`).
- Posts: `POST /comms/post` is a planner action, with `from` `chief` (`chief_routes.py:69`
  `POSTS_AS_CHIEF`, `:74-77` `_post_action`; keys at `chief_field_calls.py:57`); the answer carries
  `message_id`, and a task's may carry `ref_warning` (`blueprints/comms/messages_write.py:393`); a chief
  writes the project board only (`blueprints/comms/_helpers.py:63` `_PROJECT_WRITERS`, `:79`
  `_GLOBAL_WRITERS` lacks `chief`), so no text sends anything to the global board.
- Decompose: `POST /comms/goals/decompose` is a `plan` action (`chief_routes.py:23`; keys
  `chief_field_calls.py:92`); mode `planner` is the default and starts one planner agent, and a goal that
  already has tasks is refused (`supervisor/goal_decomposer.py:60`, `:77-79`, `:121`; the route maps
  `already_decomposed` to 409 at `blueprints/comms/goals.py:402`).
- Runs: `POST /runs` kinds are flow, single, evaluator, goal (`blueprints/control/_helpers.py:189`); a
  goal run needs `goal_id` and `project_root`, answers `{ok, run_id, kind}` (`:296-318`); stop is
  `POST /runs/<run_id>/stop` (`blueprints/control/runs_control.py:53`; action `stop`, `chief_routes.py:34`).
  `pause` and `resume` are not taught: a goal run is a board-lock run and they answer
  `unsupported_for_kind` (`runs_control.py:16-17`, `:105`).
- A run's pending question is not readable: `RunnerState._agent_question` is private
  (`supervisor/state.py:80`) and `public_dict` (`:154-179`) does not carry it, so the operator text shows
  `/runner/agent-answer` only for a topic the user names (`blueprints/runner/api_control.py:157`).
- Cited answers: the hook tells the chief the number (`pathly_hooks/chief_prompt.py:53-54`); a message
  is citable once, and it is spent when the gate lets the call through, whatever the route then answers
  (`http_server/chief_cite.py:12`, `:35-39`); the three answer routes are `/comms/answer`,
  `/comms/acknowledge` (an escalation to `human`) and `/runner/agent-answer`
  (`chief_routes.py:26,38,39`; `chief_field_calls.py:115,185,188`); a codex session has no claude session
  id, so it records nothing (`blueprints/chief/human.py:96`); `/clear` gives claude a new session id and
  every later prompt is a 403 (`blueprints/chief/human.py:13`).
- Standing orders: `POST /comms/directives` answers 201 `{id}` (`blueprints/comms/directives.py:56-118`);
  only a chief retires one, by `POST /comms/supersede` (`blueprints/comms/_supersede_on_post.py:50,71`);
  `GET /comms?...&type=decision` lists them with `binding` 1; hydration stores `binding = 0`, so a copy
  of the project on another machine starts without them (`db/queries/comms_hydrate.py:18-20,42`).

### Decisions

1. The root goes on the last line, after the fragment, so the prompt is `style + "\n\n" + fragment +
   "\n\n" + root line` and still starts with the style the way the ticket says. The ticket allowed an
   environment variable or the text; review 08 asked for the stored root and the text is the one place
   every engine reads.
2. With no `prompt`, the user's file `chief/<preset>` wins over the built-in text (the ticket says so);
   with a `prompt` in the body, that is the style and neither is read.
3. `prompt: null` is a 400 (a key that is present must be a string); only an absent key means "use the
   default". The 64 KiB limit is on the style, before the fragment and the root line, so a style that
   fit before still fits.
4. The composition lives in `supervisor/chief_presets.py`, not inside `open_chief`, which keeps
   `chief_session.py` at 287 lines and lets a test read the same function the server runs.
5. Errors and the usage text go to stderr and the response body to stdout, so a chief that pipes the
   answer reads only the answer. A non-2xx still prints its body to stdout, as it came.
6. The texts name no cost or run number; they point to `GET /chief/session` (a number in a text goes stale
   the day `chief.max_runs_per_session` changes). They teach neither `pause`/`resume` (unsupported for goal
   runs) nor anything on the global board (a chief cannot write it).
7. Token redaction on the printed answer and error is defence in depth: the server does not echo the
   token, but a proxy or a route could, and the chief's transcript is kept.
8. `-` (body from stdin) is built as the ticket says, but is of little use to a claude chief, whose
   settings allow the single command `pathly *` and not a pipeline or a here-document; the texts teach the
   quoted argument. **Round 2:** the fragment now names `-` as a fallback for a body that is awkward to
   quote. Whether a here-document passes the `Bash(pathly *)` rule was claimed above in round 1 and has not
   been verified in either round, so no text promises a way to feed `-`; the decision stands.

### Shortcuts taken

- The built-in texts are not translated to the other adapters' idioms; all three are written for a chief
  that has only `pathly` (true for claude by its settings, and for codex by the prompt alone).
- `pathly help` is a fixed string (checked by a test that every route in it exists and a chief may call
  it), not generated from the gate's tables.
- I did not add the carried review minors that belong to the chief's argv and environment
  (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, `CLAUDE_CODE_DISABLE_CRON=1`); they are ticket 06 code, not
  this ticket's.

### Review fixes (round 2)

Every finding of "Review findings (round 1, quality review)", and the four spec-review minors the
orchestrator named (they are not in the ticket's list, so I number them "spec minor 1" to "4" here),
with what I did. Test-first: the test-only commit is `51c4651` (no source file); on the base source its
six chief files gave 21 failed and 119 passed, and the 21 fail for the reason the finding names (a
`UnicodeEncodeError` / `UnicodeDecodeError` traceback, `_load_secret` called twice, the help line without
its query, `keep watching` in OPERATOR, the missing sentences, `StopIteration` for the missing escalation
read). The fix is the commit after it.

- **Finding 1 (major, tests): fixed.** Reproduced first: `pytest tests/http_api/test_chief_cli.py` with `HOME`
  set to an empty scratch dir and a throwaway plugin (`-p chk_watchers`, `pytest_sessionfinish` sleeps 40 s,
  past the watcher's 30 s `start_timeout`, then lists the `chief-watch-*` threads and what exists under
  `$HOME`): 7 watchers alive at the end, and after the 40 s `.pathly/pathly.db` (+ `-shm`, `-wal`) and
  `.pathly/global/BOARD.json` created under the empty `$HOME`. Fix: `_no_watcher_outlives_its_test` is now
  imported by `test_chief_cli.py` (the only one of the three that opens a chief), `test_chief_cli_edges.py` and
  `test_chief_prompt_text.py`, and the `server` fixture calls `httpd.server_close()`. This is the repo's own
  pattern (`chief_gate_support` and `chief_human_support` are imported by name into each module; there is
  no conftest in `tests/http_api`, and `tests/conftest.py`'s `_isolate_db` patches `Path.home()` per test:
  the guard is a module-level autouse fixture, so it is torn down before `_isolate_db` and `close_chief`
  still reaches the test's own database). After: the same command ends with 0 threads at the end, 0 after
  40 s and nothing under `$HOME` (25 passed); the same over all six chief-17 modules (142 passed): nothing.
  **Mutation:** the import removed from `test_chief_cli.py` (scratch copy `rv17b/repo_g`): 9 watchers alive
  at the end and the same four files created, so the check fails without the import. `server_close()` is not
  visible to any test (no ResourceWarning, and the port is refused with or without it): it is hygiene and
  I could not mutation-test it.
- **Finding 2 (minor) and spec minor 1: fixed.** `pathly help` prints `GET /runs?project_root=<root>`,
  `GET /comms?board=project&scope=<root>&feature=project` and `GET /chief/session?project_root=<root>`, and
  gives the POST routes that need a root or board their keys (`POST /comms/post` with `board`, `scope`,
  `feature`; `POST /runs` and `POST /comms/directives` with `project_root`). OPERATOR says
  `GET /runs?project_root=<root>`, `GET /chief/session?project_root=<root>`, and its decision list is a
  quoted `pathly api GET '/comms?...&type=decision'` command in the fenced block, as the fragment's and
  STATUS's are. I checked what each route needs against the route code before writing the table, and
  `test_chief_help_routes.py` runs it: bare `GET /comms` is a 400 for `feature`; `GET /comms?feature=project`
  alone reads the feature board `project` and answers `[]`; bare `GET /runs` is 200 `[]` with a run
  recorded; bare `GET /chief/session` is a 400; `POST /runs` without `project_root` is the gate's 403 and
  `POST /comms/directives` without it a 400; a `POST /comms/post` with a `board` and `scope` but no
  `feature` is refused, and one with `feature` alone lands on a feature board. `POST /comms/post` does
  **not** need `project_root` (the PLANNER example sends it anyway), so the table does not list it for
  that route. The tests: every help route is in the table; every help line carries its needs; the table
  matches the real routes; each GET form in the help runs and answers with what the project holds; the keys a
  help line shows are keys the gate lets a chief send; and no text names `GET /comms`, `GET /runs` or
  `GET /chief/session` without them. I changed `_routes_in` in `test_chief_cli_edges.py` to drop the query
  from the path it compares (the existing assertions are unchanged and as strong).
- **Finding 3 (minor): fixed.** `_bad_target` checks the path encodes, `_body_text` reads stdin or takes the
  argument and encodes it, and `_api` turns a `UnicodeError` into `_usage("the body is not valid UTF-8")`:
  exit 2, nothing sent. Tested in process (a lone surrogate, which is what the shell's `\xff` becomes, and a
  stdin `TextIOWrapper` over invalid bytes) and as a real process (`input=b"\xff{}"`, and the argument as
  `os.fsdecode(b'{"a":"\xff"}')`).
- **Finding 4 (minor, cap on what is printed): carried** to the cleanup PR, as decided. No cap added.
- **Finding 5 (minor): fixed.** `_api` reads `_load_secret()` once and hands it to `_send`; the
  connection-error text goes through `_redact(text, (token, secret))` like the answer. Tested: the error
  text without the secret and without the token, the answer without the secret, and `_load_secret` called
  once for an answered and for an unreachable server.
- **Finding 6 (minor, text): fixed.** OPERATOR now says to look at `GET /runs?project_root=<root>` and the
  board when the user writes or asks, never to check in a loop on its own, and to tell the user and stop when
  Pathly refuses a call. "keep watching" is gone (a test fails if it comes back).
- **Finding 7 (minor, text): fixed.** I checked first: `goal_decomposer.start_goal_decompose` with
  `mode="planner"` (the default) runs one planner agent, and `chief_budget` does not count the decompose
  routes, so the text is the only brake. OPERATOR now says `POST /comms/goals/decompose` "starts a planner
  agent to write them: an agent costs money, so ask the user first", the same words PLANNER has.
- **Finding 8 (minor, text) and spec minor 4: fixed in the fragment.** It says to quote a path that has a query
  string (an `&` ends the command, a `?` may be read as a wildcard), to run ONE `pathly` command per call with
  no pipe, no `&&` or `;` and no `$(...)` (only a single `pathly` command is approved ahead of time; more waits
  for the user), and that `-` in place of the body reads standard input and is for a body that is awkward to
  quote. Every `pathly api` command with a `?` or `&` in a text is quoted (a test). For the root: the gate
  compares what the server decoded from the query string with the stored root by `root_spelling`, and the
  command's `quote()` leaves `%` alone, so `%2B` arrives as `+` while a raw `+` arrives as a space and a raw
  `&` ends the value; the fragment says to write a `+`, `&`, `%` or space of the root as `%2B`, `%26`, `%25`,
  `%20` in a query string and to leave it as written in a JSON body (and `ROOT_LINE` now carries "apart from
  the percent-encoding a query string needs", because it said "send it as written"). A test shows the raw form
  refused, the encoded form accepted, a space accepted either way, and a JSON body with the same root
  accepted. I did **not** change `quote()`: it is right for a legitimate root. I say nothing about PowerShell
  (not verified). I did not verify that a here-document passes `Bash(pathly *)`, so the text promises no way
  to feed `-`.
- **Spec minor 2: pinned, behaviour kept.** `default_style` uses a user file `chief/custom` for a preset with
  no built-in text, so `custom` + file + no `prompt` is a 201 (the ticket says a user file `chief/<preset>`
  wins, and the tier comes from the same file's front matter, or `status` with none). It is coherent, so
  I kept it; `test_a_user_file_named_for_a_custom_preset_opens_without_a_prompt_in_the_files_tier` pins both
  cases next to the existing "custom with no file is 400" test.
- **Spec minor 3: fixed.** The fragment's start-up reads now include
  `GET '/comms?board=project&scope=<root>&feature=project&type=escalation&status=pending'` (the same command
  STATUS shows; a test compares the two) and say an escalation is the user's when its `to_agent` is `human`.
  A test runs that read as a status chief and gets a pending escalation to `human` (and one to `builder`,
  which is why the text says to look at `to_agent`: `GET /comms` has no `to` filter).
- **Finding 9 (minor, mutation gap): fixed.** `test_chief_prose_rules.py` pins by a short phrase, after
  `norm` (lower case, no backticks, one space), the start-up rule and "tell the user in a few lines where
  things stand", "do not retry in a loop", "check the question and the id first", "can be cited once" and
  "even when the route then answers 404 or 409", "never edit files", "never run an agent cli yourself", "gave
  you no number" and "cannot answer for the user", "do not look for another route around it", OPERATOR's "never
  on your own idea" and "in the user's words", and PLANNER's "ask the user first". Re-wrapping a paragraph does
  not break them.

Proof, run fresh after the last edit of code or tests (Python 3.12.3 unless said):

- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider`: `25 passed`, exit 0.
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider`: `41 passed`, exit 0.
- `python scripts/check_entry_points.py`: `Entry points OK: 17 checked` (lists `pathly = pathly_orchestrator.chief_cli:main`), exit 0.
- The commands.md Test command (`python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`): `4118 passed, 2 skipped` in 18m06s, exit 0 (the skips are not in my files). `tests/consistency`: `57 passed`.
- The six chief-17 files together: `142 passed`. Python 3.11.17 (`venv311`, built for this check) and 3.13.16 (`venv313`): `298 passed` each, for those six files plus `tests/runner_supervisor/test_chief_session.py`, `tests/http_api/test_chief_routes.py` and `tests/consistency/test_fragments_run_token.py`.
- Lint chain, each step run: `black --check src/ tests/` (676 files unchanged), `mypy src/ --ignore-missing-imports --no-strict-optional` (343 files, no issues), `check_file_size.py` (none new, none grown; `messages_crud.py` untouched), `check_no_mirror_reads.py` OK, `gen_test_index.py` then `--check` (up to date), `lint-imports` (1 kept, 0 broken), `bandit -q -r src/ -ll -x src/pathly_data/` exit 0, `check_adapters.py` OK, `check_entry_points.py` OK, `check_version_sync.py` OK (2.24.1). `python -m build --wheel` (into the scratchpad): the wheel holds `chief_cli.py`, `chief_presets.py`, the fragment (with the escalation read) and the `pathly` entry point.
- Mutation checks, scratch copy `scratchpad/rv17b` (62 mutants of the round-2 code and texts, one edit each, tests of their group `-x`): the body and path UTF-8 checks removed, `UnicodeError` not caught, usage exit 1, the secret or the token not redacted in the error, the secret not redacted in the answer, the secret read twice, the secret never sent, stdin ignored, 11 edits of the help (each route's query or body keys dropped, a key the gate refuses, a query key it refuses), 14 of OPERATOR / PLANNER / STATUS / `ROOT_LINE` (keep watching back, the loop sentence deleted in two ways, "when the user writes or asks" dropped, the decompose cost sentence deleted, "never on your own idea" and "in the user's words" deleted, `GET /runs` and `GET /chief/session` bare, the decision-list command unquoted and deleted, PLANNER's cost sentence deleted, STATUS's escalation read changed, the root-line exception dropped), 25 of the fragment (each sentence a pin names deleted, the quoting, one-command, `-` and percent-encoding sentences deleted, the escalation read and sentence deleted, its query changed, the session mention and the runs read bare, the runs read unquoted, the question and goals reads deleted), `default_style` ignoring a file for a custom preset, and `quote()` no longer passing `%`. One survived the first pass (the OPERATOR decision-list command deleted: the sentence after it then pointed at nothing); `test_the_operator_style_shows_how_to_list_the_standing_orders` kills it. All 62 are killed in the final run. The finding-1 mutation is above.

### For later tickets

- The skill docs `planning/prd-import` and `planning/project-decompose` show
  `curl ".../comms?board=project&scope=..."` without `feature`, which is a 400 on the current route
  (`messages_crud.py:22-24`). Not fixed here.
- The texts do not teach an artifact post or `/code/query`; when a later text names them: an artifact is
  posted with an absolute `artifact_path` inside the project, and `/code/query` takes a file path as
  `target` (the living doc says so under "Not here yet").
- A chief cannot learn which run is waiting on a question (no GET exposes it). Round two's inbox needs a
  read-only route for it before `/runner/agent-answer` can be offered without the user naming the topic.
- Round two (map.md § Round two) still owns the friendly commands (`overview`, `inbox`,
  `answer --cite`, ...), `GET /chief/overview` and `/chief/inbox`, and the Studio Chief button.
- Carried to the cleanup PR (not done in round 2, by decision): a cap on what `pathly api` prints and on how
  much standard input it reads (finding 4), and the `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` /
  `CLAUDE_CODE_DISABLE_CRON` environment switches (ticket 06's settings code).
- Round two's friendly commands should print the working forms the help now shows (`/runs?project_root=`,
  the project board's `board`, `scope`, `feature`), not a bare route; and whoever offers `-` to a claude chief
  must first check that a here-document passes `Bash(pathly *)` (not verified here).

## Review findings (round 1, quality review)

QUALITY
1. major tests/http_api/chief_cli_support.py:200-215 (and the import lists at test_chief_cli.py:21-29, test_chief_cli_edges.py:25, test_chief_prompt_text.py:21): the autouse guard `_no_watcher_outlives_its_test` is defined but never imported, so it never runs. Autouse fixtures only apply in modules that import them; tests/http_api/chief_gate_support.py:1-8 and the sibling modules test_chief_routes.py:78 and test_chief_session.py:100 each carry their own copy. The new tests that open a chief (7 of them in test_chief_cli.py) leave `chief-watch-*` threads alive.
   - Evidence 1: running test_chief_cli.py::test_open_without_a_prompt_pastes_the_built_in_text_then_the_fragment and the root-line test, then counting threads, shows 4 `chief-watch-*` threads still alive.
   - Evidence 2: with HOME set to an empty scratch dir, a no_pathly_autouse test that only sleeps 38s after those tests got `$HOME/.pathly/pathly.db` and `$HOME/.pathly/global/BOARD.json` created by the woken watchers (`close_chief` calls `get_db()`). The same sleep without the chief tests created nothing.
   - Consequence: a bare `pytest tests/http_api/test_chief_cli.py` writes to the developer's real ~/.pathly. In a full run the watchers wake 30s later in the middle of other tests, the 'database is locked' flake source named in tests/conftest.py (_isolate_db comment).
   - Change: import `_no_watcher_outlives_its_test` in the three modules (or make it autouse in a conftest), and add `httpd.server_close()` to the `server` fixture (chief_cli_support.py:83; the `stub` fixture already does it).
2. minor src/pathly_orchestrator/chief_cli.py:54-61 and supervisor/chief_presets.py:77: `pathly help` lists bare `GET /runs`, and OPERATOR says "keep watching `GET /runs`". I ran it with an operator token against a project that has a run. Bare `GET /runs` is exit 0 with `[]`, because the route returns an empty list without `project_root` (runs_read.py:28-33), so a chief following the help concludes there are no runs. Bare `GET /comms`, `/comms/goals` and `/chief/session` are loud 400s. This is the spec pass's bare-route minor, but `/runs` is silently wrong. Change: print `GET /runs?project_root=<root>` in help and in OPERATOR, and add a test that every help route which needs a root says so.
3. minor src/pathly_orchestrator/chief_cli.py:121 and 158: a body, path or stdin that is not valid UTF-8 escapes the usage checks. Example: `pathly api POST /x $'{"a":"\xff"}'` gives UnicodeEncodeError, and `printf '\xff{}' | pathly api POST /x -` gives UnicodeDecodeError. Both are a traceback with exit 1, which the help defines as "non-2xx or no server"; nothing was sent. Change: catch UnicodeError around the read and the encode and return `_usage(...)`, exit 2.
4. minor src/pathly_orchestrator/chief_cli.py:126 and 158: no cap on the answer or on stdin. A 50 MB answer was printed whole, and `GET /runs/<id>` can be large. Change: optionally cap what is printed and say so on stderr.
5. minor src/pathly_orchestrator/chief_cli.py:166-168: the connection-error text redacts the token but not the secret, while `_print_body` redacts both. No path puts the secret there today. Also `_load_secret()` is called twice (lines 114 and 171). Change: redact both, and read the secret once.
6. minor src/pathly_orchestrator/supervisor/chief_presets.py:77: "keep watching `GET /runs` and the board, and tell the user when a run finishes" invites a poll loop of calls that need no approval, with no stop rule. Only refused starts carry a no-loop warning (fragment line 24). Change: say to check when the user writes or asks, never in a loop.
7. minor src/pathly_orchestrator/supervisor/chief_presets.py:77: OPERATOR names `POST /comms/goals/decompose` with no cost caution, while PLANNER (line 67) says "an agent costs money, so ask the user first". Decompose is not counted by chief_budget, so the text is the only brake. Change: add the same sentence to OPERATOR.
8. minor src/pathly_data/core/skills/fragments/chief-connect.md:9 and chief_presets.py:102: only a JSON body is told to be quoted. OPERATOR line 102 prints an unquoted query URL in backticks, and help says nothing about quoting a path with `?` or `&`. Unquoted, `&` backgrounds the command and `?` globs under zsh. Nothing says "one command per call, no pipes", which `Bash(pathly *)` needs. Windows PowerShell 5.1, where a codex chief would run, strips the inner double quotes from a single-quoted JSON argument. The `-` stdin form appears only in `pathly help`, not in the fragment (I did not run PowerShell). Change: one sentence quoting paths with a query, one command per call, and `-` as the fallback.
9. minor tests (mutation gap): Prose rules the ticket requires are not pinned by any test (the prior reviewer also found this). The edit that removes one survives all three new test files. They are: the "Before you do anything else, read..." start-up rule (T04), "do not retry in a loop" (T01), "check the question and the id first" and the once-only citation sentence (T02, T10), "never edit files" (T11), the no-cite-number branch (T12), "do not look for another route around it" (T09), the OPERATOR "never on your own idea" and "in the user's words" (T05, T07), and PLANNER "ask the user first" (T06). Change: pin the start-up sentence and the retry/cite caveats the way `never run /clear` and the `'` escape already are.

Checks run
- Tests: the Done-when tests and the edited sibling tests pass, 241 passed on Python 3.12 and 241 on 3.13. The three new files also pass alone. The wider chief set (`-k "chief or binding or directive"` over tests/comms_board, http_api and runner_supervisor) gives 2575 passed. consistency, install_skills, snapshots, test_chief_gate_audit and test_config give 501 passed, 2 skipped.
- Tooling: `scripts/check_entry_points.py`, `check_version_sync.py`, `check_adapters.py`, `check_no_mirror_reads.py`, `check_file_size.py` (messages_crud.py is exactly 400) and `gen_test_index.py --check` pass. black on the changed files, mypy on src/ (343 files), lint-imports (1 kept) and `bandit -r src/ -ll -x src/pathly_data/` (exit 0) are clean. The changed files parse under Python 3.11 syntax; I could not run the tests on 3.11 (no environment).
- Packaging: the wheel built in the scratchpad contains pathly_data/core/skills/fragments/chief-connect.md and the entry point `pathly = pathly_orchestrator.chief_cli:main`.
- Import cost: `import pathly_orchestrator.chief_cli` loads only config and fsm_http_client (no flask).
- Hygiene: no skip/xfail/noqa in the new tests, and test basenames are unique. `server` and `stub` use free ports and the in-process runs patch Path.home (apart from the leak in finding 1).
- Boundary behaviour:
  - Host is the fixed 127.0.0.1 and only the port comes from the environment, so no path or env value can send the token elsewhere. http.client does not follow redirects or use proxies.
  - A 302 gives exit 1.
  - A short read gives exit 1 with an IncompleteRead message.
  - A hung server gives exit 1 "timed out".
  - Binary replies print with replacement characters.
  - Control characters in the path and a `//host` path are exit 2.
  - A token echoed by the server is redacted.
  - Nothing secret is ever in argv.
- Texts: the doc claims in the three CLAUDE.md files check out against the code. The texts' `pathly api` examples ran against the real gate and server with no gate refusal. `POST /runs` returns `run_id`, the decompose refusal for a goal with tasks and `ref_warning` exist, and `chief-connect` and `root-cause-debug` are the only fragments outside composition.yaml. No text lets a chief treat a `human` row as proof a person typed it, and none bypasses the cite rule.

Mutations (single edit, in a scratch copy; the 5 ticket test files, or the 3 new ones for the prose batch)
- Killed (30 code mutants):
  - Status mapping: 3xx counted as success, only 200 counted as success.
  - Headers: token header dropped, secret header dropped, secret never read, content-type dropped.
  - Redaction: token printed on a connection error, body redaction removed.
  - Token handling: missing-token path still calls the server, token not stripped.
  - Addressing: port hard-coded, quote() removed, method case-sensitive, stdin dash not read.
  - Usage exit code 2 changed to 1.
  - Validation relaxed: `//` authority allowed, control characters allowed, non-object body allowed, GET with a body allowed.
  - Server unreachable returns exit 0.
  - Prompt composition: front matter not stripped, user file ignored, fragment skipped, root line dropped, `prompt` read as `body["prompt"]`, non-string prompt accepted, 64 KiB limit off by one, 64 KiB limit removed.
  - Help route dropped; timeout shrunk (not a meaningful mutant, it breaks every real call).
  - Text edits: the cite rule, the injection paragraph, the header line and an operator answer example carrying its own words removed; a write example added to STATUS.
  - Prose: the `/clear` rule and the `'` escape.
- Survived:
  - M27, equivalent: the "prompt is required for preset" message is not pinned, but the outcome is still a ValueError.
  - M34, cosmetic: the fragment's `.strip()` removed.
  - M35: `_use_utf8()` removed; it is untested.
  - The prose survivors in finding 9.

REVIEW: FAIL
