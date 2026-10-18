# Refuse every chief call its tier does not allow

Type: task
Status: resolved
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
- `src/pathly_orchestrator/http_server/chief_gate.py` (new, 118 lines): `chief_gate()`.
- `src/pathly_orchestrator/http_server/app.py`: `app.before_request(chief_gate)` right after
  `_log_request`.
- `blueprints/comms/_helpers.py::_PROJECT_WRITERS` and
  `db/queries/app_settings.py::_DEFAULT_WRITE_PERMISSIONS["project"]` gain `chief` (not the
  global tier), kept in step.
- `tests/http_api/test_chief_gate.py` (new, 132 tests with parameters; committed alone first as
  `c19ab46` `test(chief-agent): 08 failing test`); `tests/INDEX.md` and `tests/http_api/INDEX.md`
  regenerated.
- `tests/comms_board/test_comms_write_perm.py`: one word, `"chief"` added to the `expected` set of
  `test_comms_write_perm_project_writers_constant` (see Decisions).
- `src/pathly_orchestrator/CLAUDE.md`: a "Chief gate (chief-agent)" section next to "Who wrote a
  board row, and who may read it" (tiers, the action table, deny by default, overrides, project
  and poster rules, what is not here yet), the two files in the package tree, and the "Chief
  endpoints" sentence that said the gate was "a later ticket".

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
  was opened with.
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

- A chief's `POST /comms/post` that names another project's board in `scope` (with
  `board: "project"`) rather than in `project_root` is not bound: the ticket binds only a
  `project_root` the call names, and `POST /runs` (`board`/`scope` fields) is the same. This is the
  hole ticket 14 is closest to; it covers calls that name a run or message by id, not a project
  board named by `scope`. It stops working when a chief posts to a project board by scope with no
  `project_root`; the fix is one more key in `_names_another_project`, or ticket 14 owning it.
- The gate reads and parses the body of every non-GET chief request (`get_data` is cached, so the
  route pays nothing twice). Cheap for the chief's traffic; it would matter only for a very large
  body.

**For later tickets**

- Ticket 09: no change to the table is needed for `/chief/human-messages`. Its hook posts with no
  run token, so the gate does not see it.
- Ticket 10: call the cite rule from `chief_gate()` after the action check. The `answer` action is
  already assigned to `/runner/agent-answer`, `/comms/answer` and to `/comms/acknowledge` on a
  human escalation (classed in `chief_routes._acknowledge_action` through the `is_human_escalation`
  predicate `chief_gate._human_escalation_check(conn)` builds), so the rule has one place to hook.
  `chief_gate.py` is 118 lines, so a new `chief_cite.py` fits as the ticket plans.
- Ticket 12: `/comms/directives` is already mapped to `decide`, `chief` is already a project
  writer, and `test_chief_gate.py::PLANNED` may drop its entry once the route exists. The living-doc
  "Chief gate" section says the route arrives with ticket 12; fix that sentence then.
- Ticket 14: add `chief_bind.target_in_project(...)` after the action check in `chief_gate()`
  (`request.view_args` and the body are already in hand there); `_names_another_project` covers
  `project_root` only. Update the "Not here yet" bullet of the "Chief gate" section when it lands.
- Ticket 15: `POST /runs` is the `("/runs", "POST")` entry; ticket 15's ceiling can key on it. The
  `GET /chief/session` route is already a `read` for the chief, so its new fields reach it.
- Ticket 17: the chief's prompt must tell it to post with `"from": "chief"` and to name its
  project by the exact spelling it was opened with (`project_root` is compared textually).
- Ticket 13: `test_status_chief_reads_and_is_refused_a_note` already checks "a Status-style token
  is refused on a write" at the HTTP level; the operator "starts a run" scenario is not covered
  here beyond the operator passing the gate on `POST /runs`.
