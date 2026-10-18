# Refuse every chief call its tier does not allow

Type: task
Status: open
Blocked by: 04, 05, 07
Test first: yes

Add `src/pathly_orchestrator/http_server/chief_gate.py::chief_gate()` and register it in
`http_server/app.py` with `app.before_request(chief_gate)` right after `_log_request` (so the
secret check and rate limit run first). It acts only on requests that carry
`X-Pathly-Run-Token`; everything else passes untouched. Flask runs `before_request` hooks in the
order they were registered and stops at the first one that returns a response, and it matches the
URL rule before any hook runs (map.md § Decisions so far, docs: Flask `before_request`,
`Request.url_rule`).

1. Look the token up with `run_tokens.lookup_run_token` (live or revoked). Not found, or a role
   other than `chief`: pass (`caller_identity` handles it as today). A revoked chief token: 401
   `{"error": "chief session closed"}`. Never let a chief token fall back to anonymous.
2. Load the session (`queries.chief.get_session`); missing or closed: 401 as above.
3. When `request.url_rule` is None (no route matched), pass. Flask then answers 404 or 405 and
   runs no view. Otherwise map the request to an action from `request.method`,
   `request.url_rule.rule` and, for `/comms/post`, the body's `type`. GET requests are `read`,
   except `/events/*` and `/db/settings` (spawn tokens, stored secrets), which are refused.
   Non-GET routes are refused unless listed:
   - read: `/comms/search`, `/code/query`
   - post: `/comms/post` (any type not below)
   - plan: `/comms/post` type `goal` or `task`; `/comms/goals/decompose`,
     `/comms/features/decompose`, `/comms/project/decompose`
   - decide: `/comms/post` type `decision` or `constraint` (a `supersedes` list included);
     `/comms/acknowledge` on any row that is not a human-addressed escalation;
     `/comms/supersede`, `/comms/directives`
   - run: `POST /runs`, `/comms/goals/run`, `/comms/run`, `/comms/tasks/run`,
     `/runs/<run_id>/<action>` for `pause|resume|advance|reroute|retry`
   - stop: `/runs/<run_id>/stop`, `/runs/<run_id>/<action>` for `abort`, `/comms/goals/stop`,
     `/comms/run/stop`, `/comms/tasks/stop`
   - answer: `/runner/agent-answer`, `/comms/answer`, and `/comms/acknowledge` on an escalation
     with `to_agent = "human"` (#63's human escalation gate, `fsm_human_gate.py`; the gate looks
     the row up by `message_id`). Ticket 10 adds the cite rule to every `answer` call.
   Unlisted (for example `/db/query`, `/skills/prompts`, `/chief/open`, `/chief/close`,
   `/chief/human-messages`, `/comms/edit`, `/comms/delete`, `/comms/hydrate`,
   `/comms/tasks/status`, and the FSM routes that take `force_past_gate`): 403. The chief never
   forces past a human gate and never marks tasks done itself.
4. Refuse with 403 `{"error", "action", "tier", "allowed"}` when the action is not in
   `chief_tiers.actions_for(session tier)`. A body that carries a non-empty `prompt_override` or
   `stage_overrides` (on any route, the decompose routes included) also needs `run`, and the 403
   names `run` as its `action`. This is the user's decision for the Planner style: it may
   call the decompose routes, which start plan-only planner or consultation agents, but may not
   pass verbatim prompt text to the agents they spawn, and it never starts build runs or run
   control (it has neither `run` nor `stop`).
5. Bind the project: when the body or query string names `project_root`, its project board scope
   (`fsm_compose.resolve_board_scope("project", value, "")`) must equal the session's, else 403.
   On `/comms/post`, a `from` other than `chief` is 403.

Keep the action table as data the test can import (rule string and method → action), not as
branches spread through the gate, so the property test below can tell listed rules from unlisted
ones.

Read the body with `blueprints/comms/_helpers.read_json_body({})`. It reads `request.get_data()`,
which Werkzeug caches by default, and `get_json()` reads through that same cache, so the route
still gets the body (map.md § Decisions so far, docs: Werkzeug `get_data`). Keep the route table
in its own module (for example `http_server/chief_routes.py`) if the gate would pass 400 lines.
Imports of `db` and `supervisor` stay lazy inside the function.

Add `chief` to `blueprints/comms/_helpers._PROJECT_WRITERS` and to
`db/queries/app_settings._DEFAULT_WRITE_PERMISSIONS["project"]` (keep the two in step; not the
global tier), so a chief can post goals and decisions on the project board.

Living docs: a "Chief gate" paragraph in `src/pathly_orchestrator/CLAUDE.md` next to "Who wrote a
board row, and who may read it", listing the tiers and actions.

## Not in this ticket

- Binding calls that name a run or a message by id (`/runs/<run_id>/...`, `message_id`,
  `question_id`, `old_id`) to the chief's project: ticket 14.
- The cost and run ceiling on `POST /runs`: ticket 15.

- The cite rule inside the `answer` action: ticket 10 adds it to this gate.
- Refusing anonymous callers: that is the UI token and read-wall work (RRP-2b, RRP-4/5).
- `/comms/directives` itself: ticket 12 (this table already maps it to `decide`).
- Checking what a decompose run then does: the routes and `goal_decomposer` are unchanged; the
  gate only decides whether the chief may call them.

## Done when

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` passes and covers,
  with sessions created directly through `queries.chief`: a status token gets 200 on
  `GET /comms?feature=<f>` and 403 on `/comms/post` type `note`; a planner token posts a `goal`
  (200) but gets 403 on `POST /runs`; a planner token on `/comms/goals/decompose` with a
  `prompt_override`, and on `/comms/features/decompose` with `stage_overrides`, gets the gate's 403
  with `action: "run"`, and the same calls without them get a response with no `allowed` key (the
  gate let them through); an operator token passes the gate on `POST /runs`; any tier
  gets 403 on `/db/query`, `/chief/open`, `GET /events/spawn` and `GET /db/settings`; another
  project's `project_root` is 403; `from: "builder"` is 403; an operator token on
  `/comms/delete`, `/comms/hydrate` and `/comms/tasks/status` is 403; an operator token
  acknowledging a `to_agent: "human"` escalation is classed `answer` (a status token gets the 403
  with `action: "answer"`); a revoked chief token gets 401 on
  `GET /comms?feature=<f>`; a status token on an unknown path gets 404; a builder token and no
  token are unaffected. The refusal of unlisted routes is tested as a property, not only for the
  routes named here: the test walks `app.url_map.iter_rules()`, and for every non-GET method of
  every rule the gate's table does not list (path converters filled with dummy values such as
  `x`), an operator token gets the gate's 403. A route added later is then refused to the chief
  until someone lists it, and the test fails if the table lists a rule that no longer exists.
- `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p no:cacheprovider` still
  passes.

```check
$ python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_comms_write_perm.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("Tier table", "How the server enforces the tier", "Which reads the chief
  may make", "Revoked chief tokens"), § Edge cases
- The routes the gate names (read-only): `blueprints/comms/goals.py::comms_goals_decompose` reads
  `prompt_override` and `stage_overrides`; `features.py::comms_features_decompose` and
  `project.py::comms_project_decompose` read `stage_overrides`
- `/chief/open` exists from ticket 07; without it the gate passes the unmatched path and the
  403 test cannot pass
- map.md § Decisions so far (docs: Flask `before_request` and `Request.url_rule`, Werkzeug
  `get_data`)
- `src/pathly_orchestrator/http_server/middleware.py::_log_request` (secret and loopback rules)
- `src/pathly_orchestrator/http_server/run_identity.py` (`RUN_TOKEN_HEADER`)
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py::comms_post` (the
  existing write-permission check the chief still passes through)

## Answer

**Built**

- `src/pathly_orchestrator/http_server/chief_routes.py` (new, 117 lines): the route table as
  data. `ROUTE_ACTIONS` (`(rule, method)` to action, a read-only mapping), `READ_REFUSED_PREFIXES`
  (`/events/`) and `READ_REFUSED_RULES` (`/db/settings`), `POST_TYPE_ACTIONS`, `RUN_VERB_ACTIONS`,
  `POSTS_AS_CHIEF`, and `action_for(rule, method, view_args, body, is_human_escalation)`, which
  applies the three refinements (a post by its `type`, `/runs/<run_id>/<action>` by its verb, an
  acknowledgement by the row it names) through a small `_REFINERS` dict.
- `src/pathly_orchestrator/http_server/chief_gate.py` (new, 118 lines; 147 after round 2):
  `chief_gate()`.
- `src/pathly_orchestrator/http_server/app.py`: `app.before_request(chief_gate)` right after
  `_log_request`.
- `blueprints/comms/_helpers.py::_PROJECT_WRITERS` and
  `db/queries/app_settings.py::_DEFAULT_WRITE_PERMISSIONS["project"]` gain `chief` (not the
  global tier), kept in step.
- `tests/http_api/test_chief_gate.py` (new, 132 tests with parameters; committed alone first as
  `c19ab46` `test(chief-agent): 08 failing test`; 313 tests after round 2);
  `tests/INDEX.md` and `tests/http_api/INDEX.md` regenerated.
- `tests/comms_board/test_comms_write_perm.py`: one word, `"chief"` added to the `expected` set of
  `test_comms_write_perm_project_writers_constant` (see Decisions).
- `src/pathly_orchestrator/CLAUDE.md`: a "Chief gate (chief-agent)" section next to "Who wrote a
  board row, and who may read it" (tiers, the action table, deny by default, overrides, project
  and poster rules, what is not here yet), the two files in the package tree, and the "Chief
  endpoints" sentence that said the gate was "a later ticket".
- Round 2 (see **Review fixes**): `http_server/chief_project.py` (new, 45 lines: which project a
  request names and whether it is the session's), `chief_routes.NAMES_PROJECT_ROOT`, `chief_gate.py`
  split into `_bodies` / `_refusal` / `_project_refusal`, and the "Chief gate" section rewritten
  for the body and project rules and the residual writes of a read.

**Proof** (each run fresh, after the last edit to code or tests)

- Test first: at `c19ab46`, `python -m pytest tests/http_api/test_chief_gate.py
  tests/comms_board/test_comms_write_perm.py -p no:cacheprovider -q` -> `111 failed, 57 passed`:
  the status chief got 200 where 403 was expected, `ImportError` for the missing
  `chief_routes`, and the constant test saw no `chief`. (Three of those failures were
  `/chief/human-messages` cases that I removed afterwards; see Decisions.) The 57 that pass
  without a gate are the "unaffected" and "passes the gate" cases.
- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `132 passed in
  35.88s`, exit 0. It covers every Done-when item: a status token gets 200 on `GET
  /comms?feature=demo` and 403 `{error, action: "post", tier: "status", allowed: ["read"]}` on a
  `note` (nothing stored); a planner token posts a `goal` (200, stamped `chief`/`token`) and gets
  403 `action: "run"` on `POST /runs`; a planner on all three decompose routes, with
  `prompt_override` or with `stage_overrides`, gets the gate's 403 `action: "run"`, and the same
  calls without them get a response with no `allowed` key; an empty `prompt_override` or
  `stage_overrides` needs nothing; an operator passes the gate on `POST /runs` and on the
  decompose routes with both overrides; 14 unlisted calls (`/db/query`, `/chief/open`,
  `/chief/close`, `GET /events/spawn`, `GET /events/runner`, `GET /db/settings`, `PUT
  /db/settings/<key>`, `/skills/prompts`, `/comms/edit`, `/comms/delete`, `/comms/hydrate`,
  `/comms/tasks/status`, `/complete_stage` with `force_past_gate`, `/runner/start`) are 403 for each
  of the three tiers with the tier's own `allowed` list; another project's `project_root` is 403
  in a body, in a query string and on `GET /chief/session`, the chief's own root passes spelled as
  given, with a trailing slash and with backslashes, and a non-string, list, dict or blank root is
  403 while null and `""` are left to the route; `from: "builder"` and a missing `from` are 403, a
  `from: "chief"` decision on the project board is 200 (and a saved project write list that omits
  `chief` still gets the route's own 403 with `allowed_roles`); an operator is 403 on
  `/comms/delete`, `/comms/hydrate` and `/comms/tasks/status`; a status token acknowledging a
  `to_agent` of `human`, `Human` or ` human ` is classed `answer`, and one acknowledging any other
  row or an unknown id is `decide`; an operator acknowledging an ordinary row gets 200, and on a
  human escalation passes the gate and meets the route's own human-gate 403; a revoked chief token
  gets 401 `{"error": "chief session closed"}` on `GET /comms`, `POST /db/query` and an unknown
  path, and so does a live token of a closed session and a chief token with no session; a status
  token on an unknown path gets 404 and on a wrong method 405; builder, unknown and absent tokens
  get 200 on `/db/query`, `/db/settings` and a `note`, and a revoked builder token is still 200.
  Beyond the list: the post type table (10 cases: `note`/`status`/`escalation`/non-string = post,
  `goal`/`task` = plan, `decision`/`constraint` in any case or with spaces = decide), each listed
  route's action probed with a status token, all seven run verbs (`pause|resume|advance|reroute|
  retry` = run, `abort` and `stop` = stop; an unknown verb is unlisted), the read rules (every GET
  is read except `/events/*` and `/db/settings`), and `chief` as a default project writer and not a
  global one.
- The property test, `test_every_unlisted_non_get_route_is_refused_to_an_operator`: walks
  `app.url_map.iter_rules()`, fills each converter with `x`, checks the built path matches the
  intended rule, and sends the operator token to every non-GET `(rule, method)` the table does not
  list; every one is the gate's 403. It also asserts that the unlisted set contains `/db/query`,
  `/chief/open`, `/shutdown`, `/comms/delete` and `PUT /db/settings/<key>`, that the listed and
  unlisted sets partition the non-GET routes, and that `os._exit` (which `/shutdown` calls on a
  timer) was never reached. `test_every_listed_rule_exists` fails if the table lists a rule
  that is not in `app.url_map`, except the one in `PLANNED` (`/comms/directives`, ticket 12).
- `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p no:cacheprovider` -> `33
  passed in 7.06s`, exit 0.
- Mutation checks, each run against `test_chief_gate.py` with `-x` (source edited, run, restored):
  a revoked token falling through, the override check off, the project check off, the `from` check
  off, no human-escalation refinement, `/events/` readable, `/db/settings` readable, `/db/query`
  listed as `read`, `abort` classed `run`, a no-match path refused, `decision` classed `post`,
  an unknown run verb falling back to the route's base action: all 12 made a named test fail.
- Test command from `commands.md` (`tests/comms_board tests/db tests/runner_supervisor
  tests/http_api -x`) -> `1505 passed, 2 skipped in 308.11s`, exit 0 (the 2 skips are not mine).
  `tests/consistency tests/local_operator tests/hq_copilot` -> `155 passed` (the last two walk
  `app.url_map`).
- Lint chain from `commands.md`, run piece by piece, all exit 0: `black --check src/ tests/` (586
  files unchanged), `mypy src/ --ignore-missing-imports --no-strict-optional` (`Success: no issues
  found in 323 source files`), `check_file_size.py` (`none new, none grown`), `check_no_mirror_
  reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0 broken`), `bandit -q -r src/
  -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`. Smoke exit 0; `python -m
  build --wheel` exit 0. No `# noqa`, `# nosec` or `type: ignore` added.

**Decisions**

- `tests/comms_board/test_comms_write_perm.py` had to change by one word. The ticket's second
  Done-when says the file "still passes", but `test_comms_write_perm_project_writers_constant`
  pins `_PROJECT_WRITERS` to an exact set, so adding `chief` (which the ticket requires) makes it
  fail until `expected` names `chief`. I added `"chief"` to that set and touched nothing else in the
  file; no assertion was loosened. A reviewer should treat this as a deliberate expectation update.
- Every gate refusal carries all four keys, `{error, action, tier, allowed}`, including the
  project and `from` refusals and an unlisted route (`action` is `null` there). The tests then
  tell "the gate refused" (403 with `allowed`) from "the route answered" with one check. Spec
  § Interfaces lists that shape for the tier refusal; using it for the others is my choice.
- Order inside the gate: token row, then the 401 checks, then `url_rule is None`, then the action,
  then the override rule, then the project, then `from`. So a revoked chief token on an unknown
  path is 401, not 404, as the ticket's order says. A base action the tier lacks is named in the
  403 before the override rule is looked at (a status chief posting `prompt_override` to a decompose
  route is told `plan`, a planner is told `run`).
- The override rule runs on every non-GET chief request, read routes included (the ticket says
  "on any route"). "Non-empty" is plain truthiness, so a whitespace-only `prompt_override`
  counts.
- A `project_root` is "named" when it is truthy. A truthy value that is not a string, or a string
  that does not resolve to the session's project, is 403; null, `""` and other falsy values are
  left to the route (the routes read them as "not given"). The comparison is
  `resolve_board_scope("project", value, "")` on both sides, as the ticket says, so it is textual
  after the board code's own normalisation (forward slashes, no trailing slash); `..` segments,
  symlinks and case differences are refused (fail closed), and the chief has to use the spelling it
  was opened with. (Round 2: the comparison is now `normalise_project_root`, and a run or
  decompose route refuses an unnamed root; see **Review fixes**.)
- `from` on `/comms/post` must be exactly `chief`; a missing `from` is 403 too (the route would
  400 it, but the gate does not rely on that).
- A post's `type` is stripped and lower-cased before it is classed, so `Decision` or ` constraint `
  is `decide` (stricter than the route, which stores the type as sent).
- The "human-addressed escalation" test is a small `SELECT type, to_agent FROM comms_messages
  WHERE id=?` in `chief_gate.py`, the same rule as `_helpers.refuse_agent_on_human_gate`, which
  builds a response and so cannot be reused as a predicate. I did not refactor that helper (it is
  outside the ticket). A database error propagates as a 500 for that request, which fails closed.
- HEAD is read as GET. An unknown `/runs/<run_id>/<verb>` is unlisted (403), though the route
  would 400 it.
- `/chief/human-messages` is in the ticket's list of 403 examples, but ticket 09 creates it. Until
  then it is an unmatched path (the gate passes, Flask answers 404), so I left it out of the test's
  unlisted-call list. When 09 adds it, the property test covers it with no change here: it is not
  in the table, so a chief token on it is 403 (the hook posts with no run token and is untouched).
- `/comms/directives` is in the table (`decide`, as the ticket says) before its route exists.
  `test_every_listed_rule_exists` allows exactly that rule through its own `PLANNED` set, so the
  "table lists a rule that no longer exists" check stays strict for everything else. Ticket 12 may
  delete the `PLANNED` entry; the test passes either way.
- An autouse fixture in the test replaces every `/events/*` view with a stub. The test client
  waits for a streaming view's first chunk, so without a gate a call to `GET /events/spawn` hung
  the run (found when the first failing run did not return) instead of failing.

**Shortcuts taken**

- The gate reads and parses the body of every non-GET chief request, twice since round 2 (once
  with `read_json_body`, once with `get_json`; `get_data` is cached, so the route pays nothing
  twice). Cheap for the chief's traffic; it would matter only for a very large body.
- A status chief can still cause two small writes through `read` routes: `GET
  /comms/artifacts/section?scope=<feature>&trail=x` posts a "context pull" `status` row on that
  feature's board, and `GET /menu/<name>` broadcasts a menu push. Feature boards are keyed by
  feature name only, so the gate cannot tell whose feature it is. Stated in the "Chief gate"
  section of `src/pathly_orchestrator/CLAUDE.md`. It stops working if a deployment reads that row as
  a signal that an agent worked on the feature; the upgrade is to bind the feature name to the
  chief's project (ticket 14's id-binding is the closest home) or to list the two routes as `post`.
- A chief's `/code/query` must give a parenthesized marker such as `(interactive)`, no scope, or
  its own root as `scope`: a feature name is refused, because the route logs a project-board row at
  whatever scope it is given. It stops being right if the chief needs its code queries logged under
  a feature name; the fix is then to bind the logged row, not to drop the check.

**Review fixes** (round 1, quality review; the round starts at `c2de8da`. Test-only commits first:
`b5014df` and `286bb1e`, each run red before any source change.)

1. *blocker, an encoded body hides the project binding.* Reproduced as the finding says (red run at
   `b5014df`: 94 failed, 210 passed; each failure was the gate letting an encoded body through, an
   unbound project on `/runs`, `/runner/agent-answer`, `/code/query`, `/runs/x/retry` and
   `/runs/x/reroute`, or a `decision` class read as `post`). Fixed in `chief_gate._bodies()`: the
   gate parses the body with `read_json_body` (what the comms routes read) and with
   `request.get_json(silent=True, force=True, cache=False)` (what `/runs`, `/runner/*`,
   `/code/query` and the run-control verbs read), and `_refusal` runs every check (action,
   overrides, project, `from`) over each non-empty result. `cache=False` matters: with the default
   cache the forced parse would store the dict, and a route that ignores a non-JSON content type
   would then read it (`test_the_gate_does_not_change_what_a_route_reads` fails with `cache=True`).
   Tests, each of the 7 encodings (`utf-8-sig`, `utf-16`, `-le`, `-be`, `utf-32`, `-le`, `-be`) plus
   plain JSON as the control: `/runs` refuses another project's root and hands `start_board_run` the
   whole body of its own, `/runner/agent-answer` and `/code/query` and `/runs/x/retry|reroute` refuse
   it, `/comms/post` is classed by its type. I did not add a branch for the two readers returning
   different non-empty objects (both are checked, which is the stricter reading): no input does that,
   because a body valid as UTF-8 gives both the same object and the other encodings parse in one
   reader only.
2. *major, the project is bound only by `project_root`.* Fixed. `chief_project.py` reads every value
   the routes use as a project: `project_root` (body, and each value of a repeated query key), the
   `scope` of a call with `board: "project"` (`/comms/post` falls back to `feature` for a missing or
   blank scope, as the route does), the `project` override of `/comms/project/decompose`, and the
   `scope`/`feature` of `/code/query` unless blank or a marker such as `(interactive)` (found while
   fixing this: the route logs a `discovery` row on the project board at that scope, so a status
   chief could write to another project's board; `286bb1e`). All must be the session's after
   `normalise_project_root`. `chief_routes.NAMES_PROJECT_ROOT` (`/runs`, `/comms/goals/run`,
   `/comms/run`, `/comms/tasks/run`, the three decompose routes) also refuses a call that names no
   `project_root` (absent, null, empty, `0`, `[]`): I refused rather than taking it from the session,
   because the route reads the request's own body, which a `before_request` hook should not rewrite.
   Tests: nine project-board posts that name another project or none, three spellings of the own
   scope that pass, a feature-board post that stays unbound, the same post in every encoding,
   `/runs`, `/comms/run` and `/comms/run/stop` on another project's board, the decompose override, 35
   missing-root cases over the seven routes, the same for a planner, the query-string form, and a
   property test that `NAMES_PROJECT_ROOT` equals the listed `run` and decompose rules (id-addressed
   `/runs/<run_id>/<action>` excepted, that is ticket 14). Four existing tests that call run and decompose
   routes now send `project_root` (`test_planner_overrides_need_run`,
   `test_empty_overrides_do_not_need_run`, `test_operator_passes_the_decompose_routes_with_overrides`,
   `test_operator_passes_the_gate_on_a_run_start`); their assertions did not change, because without
   it the gate now (rightly) refuses them.
3. *minor, `read` routes with side effects.* Took the recommended path: `/comms/artifacts/section`
   and `/code/query` stay `read` (a status chief must read artifact sections and query code), and
   the "Chief gate" section of `src/pathly_orchestrator/CLAUDE.md` now says plainly (bullet "Reads
   are not all pure") what a read can still write: the "context pull" status row, the menu push, the
   re-index and the code-query `discovery` row. The last two are bound to the chief's project (item
   2); the first two are listed under Shortcuts.
4. *minor, missing cases.* Added: non-UTF-8 text bodies (cp1252, an em-dash is byte 0x97) classed by
   type, refused when they name another project on `/comms/search`, `/runs` and `/code/query`, and
   stored whole for an operator post; HEAD read as GET (`/comms` 200, `/events/spawn`,
   `/events/runner`, `/db/settings` 403) and no HEAD on a POST-only route (405); the 308 redirect of
   `/db//query`, `/comms//post`, `/events//spawn`, `/db//settings` (no view runs, and the followed
   request is gated, or posts normally for the allowed route); eight look-alike paths of `/db/query`
   (`/DB/query`, trailing slash, dot segment, double slash, `..`, `;x=1`, `%00`, `%2F`) never
   reach a view; PUT, DELETE and PATCH on three unlisted routes are 405. These pass before and after
   the fix, as regression cases, except where item 1 applies.

Proof after the fixes (each run fresh, after the last edit to code, tests and docs):

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `313 passed in
  84.34s`, exit 0. `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p
  no:cacheprovider` -> `33 passed in 7.40s`, exit 0.
- Mutation checks, each against the matching tests, each failing: `cache=True`, no `get_json`
  reading, the missing-root rule off, the project-board scope off, the `/code/query` scope off, the
  decompose override off, the `/comms/post` `feature` fallback off.
- Test command from `commands.md` -> `1686 passed, 2 skipped in 350.69s`, exit 0 (the 2 skips are
  not mine). `tests/consistency tests/local_operator tests/hq_copilot` -> `155 passed`.
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (587 files
  unchanged), `mypy` (`no issues found in 324 source files`), `check_file_size.py` (`none new, none
  grown`; `chief_gate.py` 147, `chief_project.py` 45, `chief_routes.py` 132 lines),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0 broken`),
  `bandit -q -r src/ -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`. Smoke
  and `python -m build --wheel` exit 0. No `# noqa`, `# nosec` or `type: ignore` added.

**For later tickets**

- Ticket 09: no change to the table is needed for `/chief/human-messages`. Its hook posts with no
  run token, so the gate does not see it.
- Ticket 10: call the cite rule from `chief_gate._refusal()` after the action check (it runs once
  per reading of the body, so a cite rule that reads the body reads the one it is given). The `answer` action is
  already assigned to `/runner/agent-answer`, `/comms/answer` and to `/comms/acknowledge` on a
  human escalation (classed in `chief_routes._acknowledge_action` through the `is_human_escalation`
  predicate `chief_gate._human_escalation_check(conn)` builds), so the rule has one place to hook.
  `chief_gate.py` is 147 lines, so a new `chief_cite.py` fits as the ticket plans.
- Ticket 12: `/comms/directives` is already mapped to `decide`, `chief` is already a project
  writer, and `test_chief_gate.py::PLANNED` may drop its entry once the route exists. The living-doc
  "Chief gate" section says the route arrives with ticket 12; fix that sentence then.
- Ticket 14: add `chief_bind.target_in_project(...)` after the action check in
  `chief_gate._refusal()` (`request.view_args` and the body are already in hand there);
  `chief_project` covers the project a request names (`project_root`, a project board's `scope`,
  a code query's scope, the decompose override), not a run or message id. Update the "Not here yet"
  bullet of the "Chief gate" section when it lands. The feature-board "context pull" row (Shortcuts)
  is the other unbound write.
- Ticket 15: `POST /runs` is the `("/runs", "POST")` entry; ticket 15's ceiling can key on it. The
  `GET /chief/session` route is already a `read` for the chief, so its new fields reach it.
- Ticket 17: the chief's prompt must tell it to post with `"from": "chief"` and to name its
  project by the exact spelling it was opened with (`project_root` is compared textually, after
  `normalise_project_root`). It must also say: send `project_root` on every run, goal and decompose
  call (a call without it is 403); give the project root as `scope` on a project-board post and a
  run on the project board (a missing scope is read as `feature`, which is 403); use a
  parenthesized scope such as `(interactive)` on `/code/query` (a feature name is 403). `pathly api`
  may fill `project_root` in from the session itself.
- Ticket 13: `test_status_chief_reads_and_is_refused_a_note` already checks "a Status-style token
  is refused on a write" at the HTTP level; the operator "starts a run" scenario is not covered
  here beyond the operator passing the gate on `POST /runs`.

## Review findings (round 1, quality review)

QUALITY
1. blocker src/pathly_orchestrator/http_server/chief_gate.py: a UTF-8 BOM or UTF-16/32 JSON body hides the whole body from the gate, so the project binding is skipped.
   - Cause: the gate reads the body with `read_json_body`, which decodes only utf-8 or cp1252 as text. Routes that call `request.get_json(...)` hand the raw bytes to `json.loads`, which accepts a BOM, UTF-16 and UTF-32. For such a body the gate sees `{}` and the route sees the real fields.
   - Reproduced with an operator chief on project A and `Content-Type: application/json`: `POST /runs` with `project_root` set to project B returned the gate's 403 as plain JSON. With a BOM or UTF-16 body it returned 200, and `start_board_run` was called with project B's root. `POST /runner/agent-answer` showed the same: gated as plain JSON, then reached the route (404 "No run found") with a BOM or UTF-16 body.
   - Status tier too: `POST /code/query` is `read`, so a status chief is also affected. A plain body with another `project_root` got the gate's 403. With a BOM or UTF-16 body it returned 200, so the status chief can query, and trigger a reindex of, another project's code graph.
   - Other routes at risk: `/runs/<id>/retry` and `/runs/<id>/reroute` read their bodies with `get_json` as well.
   - Not affected: the routes that use `read_json_body` (`/comms/*`, decompose) fail identically in gate and route. This also means the `prompt_override` and `stage_overrides` check is not bypassed for the planner today, only because those routes share the gate's parser.
   - Fix: make the gate parse exactly as the route will. For example, parse with both `read_json_body` and `request.get_json(silent=True, force=True)` and run every body check on both results. Or refuse a non-GET whose non-empty body the two parsers read differently. Add tests with BOM, UTF-16 and UTF-32 bodies on `/runs`, `/runner/agent-answer` and `/code/query`.
2. major src/pathly_orchestrator/http_server/chief_gate.py: the project binding applies only when the caller names `project_root`, and no ticket owns the rest.
   - Reproduced: an operator chief on project A posted `type: decision`, `board: "project"`, `scope: "<project B root>"` to `/comms/post` and got 200. The row landed on project B's board with `author_role=chief`, so it feeds B's governance block.
   - Documented but unowned: the author's "Not here yet" paragraph admits this. Ticket 14 covers only ids (`run_id`, `message_id`, `question_id`, `old_id`), so no ticket closes it.
   - Also unbound: run and decompose routes with `project_root` omitted fall back to the server's working directory, which can be a different project.
   - Fix: on `/comms/post` with `board: "project"`, require `scope` to equal the session's project scope. For the chief on run and decompose routes, refuse a missing `project_root`, or take it from the session rather than the body.
3. minor src/pathly_orchestrator/http_server/chief_routes.py: some `read`-classed routes have side effects. `GET /comms/artifacts/section?scope=<any feature>&trail=x` posts a board `status` row ("context pull · <artifact>") when the hydrate succeeds, so a status chief can write. `GET /menu/<name>` broadcasts a menu push over SSE. `POST /code/query` can log to the board and reindex. The spec lists `/code/query` as `read`. Consider listing the other two as exceptions, or at least stating the residual write in the CLAUDE.md "Chief gate" section.
4. minor tests/http_api/test_chief_gate.py: the tests have no case for non-UTF-8 text bodies (finding 1), HEAD, or the 308 redirect and 404 paths. Add them with the fix for finding 1.

Routes, paths and headers tried that did not get around the gate (each refused by the gate, 404, 405 or a 308 redirect, none executed): unlisted POST routes `//db/query`, `/db//query` (308), `/db/query/`, `/DB/query`, `/db/qu%65ry`, `/db/./query`, `/comms/../db/query`, `%00`, `%2F` and `;x=1` variants; `/events/*` with the same variants, including `HEAD` (`HEAD /events/spawn` is refused with 403, `GET /events//spawn` redirects); PUT, DELETE, PATCH and TRACE on `/db/query` and `/events/spawn` (OPTIONS is answered by `_log_request` before the gate runs and has no side effect); the `X-Pathly-Run-Token` header (the gate reads and strips it exactly as `caller_identity` does); the post `type` normalisation (the gate's is wider than the route's, so it classes a post at least as high); `supersedes` (accepted only on exact `decision` or `constraint` posts).

Not rated, because the ticket scopes it out (RRP-2b, RRP-4/5): a chief that simply omits `X-Pathly-Run-Token` is anonymous and unrestricted.

Range reviewed: 570a6ee..03801f5, the ticket's own last commit and HEAD. I did not read the Answer. I re-ran both Done when commands (132 passed, 33 passed); black, mypy, lint-imports, check_file_size and gen_test_index --check are clean. I left no files in the repo; my probe tests are in the scratchpad.

REVIEW: FAIL

## Review findings (round 2, quality review)

QUALITY

Range reviewed: 570a6ee..7c9340c. That is the ticket's own last commit and also HEAD, so no later commits were left out. I read the ticket as it stood at 570a6ee, its `## Review findings (round 1)` section, and the diff. I did not read `## Answer`.

Both Done when commands pass: 313 passed for `tests/http_api/test_chief_gate.py` and 33 passed for `tests/comms_board/test_comms_write_perm.py`. black, mypy, lint-imports, check_file_size and `gen_test_index --check` are clean. The repo working tree is clean. My probes are under the scratchpad `rv2/`: `test_h1.py`, `test_h2.py`, `test_h2b.py`, `test_h3.py`, `diff_cache.py`, `conftest.py`.

1. major src/pathly_orchestrator/http_server/chief_gate.py (`_project_refusal`) and chief_project.py: a `project_root` in the query string satisfies the "must name its project_root" rule, but the run and decompose routes read the body only. This is round-1 finding 2b, still open under a different spelling.
   - Repro (`test_h1.py`): an operator chief on project A, with `start_goal_run` and `start_board_run` patched to record what they receive.
     - `POST /comms/goals/run?project_root=<A>` with body `{"goal_id":"g1"}` passes the gate, and `start_goal_run` receives `project_root=""`.
     - `POST /comms/run?project_root=<A>` with `{"scope":"s","board":"feature"}` passes, and `start_board_run` receives `""`.
     - `POST /runs?project_root=<A>` with `{"kind":"single","scope":"s"}` passes with `""`, and the same URL with `{"kind":"goal","goal_id":"g"}` passes with `""`.
     - With no `project_root` anywhere, the gate correctly refuses (control).
   - Cause: `root_values(body, args)` merges the query string into `roots`, then `not roots` is the "names a project" test. None of the seven `NAMES_PROJECT_ROOT` routes reads `request.args`.
   - The test `test_a_project_named_in_the_query_string_counts` asserts the hole as intended behaviour.
   - Fix: for `NAMES_PROJECT_ROOT`, require a truthy `project_root` in the parsed body. Keep checking query-string values for the binding only, so they do not count as naming. Flip that test to expect the 403.
2. major src/pathly_orchestrator/http_server/chief_project.py (`board_values`): the gate does not check every value a route uses as a project board, so a chief can read another project's board. This is the same class as round-1 finding 2, on the read side.
   - `/comms/search` reads `scope = data.get("scope") or feature`. `board_values` applies the `feature` fallback only when `rule == "/comms/post"`.
   - Repro (`test_h2.py`, `test_h2b.py`): with another project B's board seeded with a decision, `POST /comms/search` with `{"query":"zebra","board":"project","feature":"<B root>","mode":"keyword"}` returns B's decision text to status, planner and operator chiefs. `scope` is absent, or `0`, `null` or `""`, in these variants. With `scope=<B>` the gate refuses, so only the fallback is missed.
   - GET routes are checked with an empty body and only `project_root` from the query string. `GET /comms?feature=x&board=project&scope=<B>` returns B's rows to every tier (reproduced, same seeded decision text). `GET /comms/tasks?board=project&scope=<B>` passes the gate (200) with the same query.
   - `src/pathly_orchestrator/CLAUDE.md` says "Every value the call uses to name a project must be the session's". That is not true for these routes.
   - Fix: fix `/comms/search` at least (use `scope or feature` when `board == "project"`). For GET, check `board=project` plus `scope` from the query string. Or decide that reads are fleet-wide, since `GET /runs` and `/db/*` already are, and then say so in the ticket and CLAUDE.md. Do not keep a partial binding that implies otherwise.
3. minor chief_project.py and chief_routes.py: `board_values` hard-codes `/comms/post`, `/code/query` and `/comms/project/decompose` in a branchy function, while the action table is data.
   - This is why `/comms/search` was missed (finding 2).
   - Make the per-route fields the route reads as project or scope, with their fallbacks, a table next to `ROUTE_ACTIONS`. Then a test can compare it with the routes the way the url_map walk does for actions.
4. minor src/pathly_orchestrator/http_server/blueprints/code/query.py via the gate: an absolute `target` into another project passes with `project_root` omitted or set to the chief's own project. The graph is keyed by file path, so the advisory block is read from project B. This is not covered by `project_root` binding. Bind it, or add it to the "Not here yet" paragraph for ticket 14.
5. minor tests/http_api/test_chief_gate.py: no case for a `project_root` only in the query string on a run route, or for `board=project` read routes. Add both with the fixes for findings 1 and 2.

Ways around the gate I tried that were refused or harmless:
- Repeated query keys (A then B, and B then A).
- A percent-encoded key (`project%5Froot`).
- A body `project_root` of A with a query `project_root` of B.
- `project_root` given as a number, bool, list or dict, or with leading whitespace, a trailing newline or upper-case letters.
- A list body, a string body, and a nested `project_root`.
- Trailing slashes and backslash spellings of the session root, which pass only as the same project.
- BOM, UTF-16, UTF-32 and cp1252 bodies, and a missing or wrong `Content-Type`.
- HEAD, 308 redirects and `//` paths.
- Unlisted methods.
- `/runs/<id>/<verb>` case and encoding variants.
- A mismatch between the type the gate classes and the type the route stores.

`cache=False` on the forced parse does not change what a later route handler sees. I ran a Flask app with and without the gate's `_bodies()` call across 12 content-type and body combinations (valid, invalid, empty, BOM, UTF-16, list, form, multipart, cp1252), reading `get_json` with and without `silent`/`force`, `request.json` and `get_data`, and the responses were identical. The one difference, for form content types, appears only when a route reads `request.form` before `get_data()`. No real route does, and `read_json_body` caches first.

REVIEW: FAIL
