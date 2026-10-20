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
- Round 3 (see **Review fixes (round 2)**): `http_server/chief_fields.py` (new, 298 lines):
  `ROUTE_FIELDS`, one `Fields` entry per route a chief can reach (the 19 listed POST routes that
  exist, `/comms/directives` aside, and every GET the gate lets through: 84 entries), saying which
  request fields the view reads as a project root, a board scope or a file, and which ids it
  reads that the gate does not bind. `chief_project.py` rewritten
  (168 lines) to one generic function, `project_refusal(rule, method, session, body, args)`, that
  applies an entry (the old `root_values`, `board_values` and the hard-coded route branches are
  gone). `chief_routes.NAMES_PROJECT_ROOT` is gone (it is `Fields.names_root` now); `chief_gate.py`
  calls `project_refusal` and lost `_project_refusal` (137 lines). The "Chief gate" section of
  `src/pathly_orchestrator/CLAUDE.md` is rewritten for the table, with the unbound items listed
  plainly, and the package tree gains `chief_fields.py`. `tests/http_api/test_chief_gate.py`
  (483 tests; the test-only commit is `f298248`); `tests/http_api/INDEX.md` regenerated.
- Round 4 (see **Review fixes (round 3)**): `chief_fields.py` (342 lines) gains `Fields.under_root`,
  `names_root_unless`, `names_root_verbs` and `ScopeRead.segment`; `chief_project.py` (201 lines)
  applies them (`_unnamed_root` knows the verb and the "unless" rule, `project_refusal` takes the
  route's `view_args` and refuses a `segment` scope that is not one folder name); `chief_gate.py`
  (139 lines) passes `request.view_args` on. Two routes get a guard of their own:
  `blueprints/comms/features.py` (`feature` must be a safe folder name, else 400
  `invalid_feature`) and `blueprints/comms/runs.py` (an evaluator reply is not saved under an
  unsafe scope). The "Chief gate" section of `src/pathly_orchestrator/CLAUDE.md` is corrected.
  `tests/http_api/test_chief_gate.py` is split by concern into `test_chief_gate.py` (the Done-when
  cases, 97 tests) and ten `test_chief_gate_*.py` files, with the shared fixtures in
  `chief_gate_support.py` (651 tests in all; test-only commit `d3d52b1`, fix `53dc2fa`, split
  `45357e6`); `tests/INDEX.md` and `tests/http_api/INDEX.md` regenerated.
- Round 5 (see **Review fixes (round 4)**): `src/pathly_orchestrator/scope_names.py` (new, 43
  lines): `is_segment` (one plain folder name) and `is_project_root` (a normalised absolute root,
  POSIX or `C:/...`), the two predicates the gate and the sinks share. `board_mirror.py` (306
  lines) answers only those two shapes: `board_from_scope` returns None for anything else,
  `mark_board_dirty_by_scope` queues nothing for it, `write_board_mirror` and `board_mirror_path`
  refuse it. `supervisor/slug.py` (111 lines): `ensure_goal_slug` replaces a stored slug that is not
  one folder name. `chief_fields.py` (363 lines): `Fields.segments` (the `slug` of `/comms/post`),
  the `ScopeRead` docstring, the `/db/rollup` note. `chief_project.py` (204 lines): a scope that
  is a path is bound to the session's project on every board, any other scope off the project
  board is one folder name, and a `segments` field is one folder name. The "Chief gate" section of
  `src/pathly_orchestrator/CLAUDE.md` is corrected (findings 1, 3, 4 and the scope and folder-name
  bullets). New tests: `tests/comms_board/test_board_mirror_scope.py` (the sink) and
  `tests/http_api/test_chief_gate_mirror.py` (the gate: the post route, `/runs`, every scope read of
  `ROUTE_FIELDS`, the slug); small edits to `tests/http_api/test_chief_gate_tables.py`; the three
  `INDEX.md` files regenerated. Test-only commit `0ab8cdb`, then the fix.
- Round 6 (see **Review fixes (round 5)**): the owner chose "strict keys". Every `ROUTE_FIELDS`
  entry is now the **complete list of the keys a chief may send** to its route (body keys; query
  keys for a GET), and every listed key that can reach a path, a file or a folder has a declared
  kind with a rule at the gate and, where the key reaches a sink, at the sink. The table moved:
  `chief_fields.py` (28 lines) is only the merge of `chief_field_calls.py` (182, the 19 POST
  entries), `chief_field_reads.py` (181, the 65 GET entries) and `chief_field_types.py` (183:
  `Fields`, `ScopeRead`, `TextPath`, the kinds, `url_variables`); 84 entries, 221 listed keys, 9
  keys a view reads that no chief flow needs (`not_for_chief`). New `chief_keys.py` (55 lines):
  `key_refusal`, which `chief_gate.py` (144 lines) calls last (an unlisted key is 403 naming it; a
  `flow` that is not one name and a `skill` that is not `name` or `category/name` too).
  `chief_project.py` (205 lines) only changed its imports. `scope_names.py` (77 lines) gains
  `is_flow_name`, `is_skill_name` and `resolves_inside`. The sinks: `fsm_ops._load_flow` (353) and
  `skills/compose_resources._skill_file` (152) refuse a string that is not one name or that
  resolves outside the packaged folder; `supervisor/goal_executor.py`: `_flow_kind` raises
  `ValueError`, and `_run_team` checks the flow before it makes a folder (the file stays at 492
  lines, its baseline); `runner/hydrate.py` (388): `hydrate_section(contain_in=...)` answers 400
  `path_out_of_scope` for a stored path outside the root the call names (`inside_root` and
  `whole_file_result` live in `hydrate_helpers.py`, 143), and `blueprints/comms/artifacts.py` passes
  the root. `scripts/file_size_baseline.txt` loses the `runner/hydrate.py:403` line (the file is
  under 400 now and the ratchet fails until it goes). The "Chief gate" section of
  `src/pathly_orchestrator/CLAUDE.md` is rewritten sentence by sentence. New tests (test-only commit
  `acf32ae` first, then the rest with the fix): `test_chief_gate_flow_skill.py` (25),
  `test_chief_gate_artifact_section.py` (8), `test_chief_gate_strict_keys.py` (30),
  `test_chief_gate_keys.py` (88, with `chief_walk_support.py`), `test_chief_gate_audit.py` (6, with
  `chief_audit_support.py` and `chief_audit_world.py`), `tests/comms_board/test_board_mirror_
  relative_root.py` (12), `tests/storage_paths/test_scope_names_flow_skill.py` (58); edits to
  `test_chief_gate.py`, `test_chief_gate_tables.py`, `test_chief_gate_root_naming.py` and
  `chief_gate_support.py` (listed under Review fixes); the four `INDEX.md` files regenerated.

- Round 7 (see **Review fixes (round 6)**): `scope_names.py` (139 lines) gains `host_is_windows()`,
  `root_spelling()` and `lies_under()`, the one host-aware reading of a root and a file; `http_server/
  chief_project.py` (186) uses them in place of `normalise_project_root` and its own `_under`;
  `runner/code_context_cli.py` (201) escapes the target in its Cypher literal (`_cypher_literal`)
  and hashes a relative file under the project root (`_file_hash(path, project_root)`,
  `_file_section(..., project_root)`). No other source file changed. The "Chief gate" section of
  `src/pathly_orchestrator/CLAUDE.md` is corrected (host reading of a backslash, the drive prefix,
  "What was measured", the fourth reading test, `max_cost_usd`, ticket 17's texts), and so is the
  `code_context_cli.py` line of its package map. Tests (test-only commits `509e381` and `fc2b66e`
  first): new `test_chief_gate_separators.py` (122), `test_chief_gate_kinds.py` (7),
  `tests/storage_paths/test_scope_names_host.py` (62), `tests/code_intel/test_code_context_cypher.py`
  (8), and the audit's support files `chief_audit_sandbox.py`, `chief_audit_calls.py` and
  `chief_audit_reads.py` (`chief_audit_world.py` fell from 379 to 250 lines); edits to
  `test_chief_gate_audit.py`, `test_chief_gate_keys.py`, `chief_walk_support.py`,
  `test_chief_gate.py`, `test_chief_gate_project_scope.py` and `test_chief_gate_files.py` (listed
  under Review fixes (round 6)); the four `INDEX.md` files regenerated.

- Round 8 (see **Review fixes (round 7)**): `scope_names.py` (155 lines) gains `cache_root()` (the
  project part of a cache key) and `host_path()` (a path as this host's file system reads it);
  `runner/code_context_cli.py` (213): `_CLI_CACHE` is keyed `(project root, path, hash)` and
  `_cypher_literal` returns None for a text with a double quote (the file section makes no query
  then); `http_server/blueprints/code/query.py` (399): `_QUERY_CACHE` is keyed `(project root, op,
  target, hash, backend)` and nothing is read from it or stored in it for a target with no hash;
  `db/queries/run_history.py` (124): `_SLUG_MATCH` has an `ESCAPE` clause and the three readers
  bind `_like_literal(feature)`; `http_server/chief_project.py` (215): `_opens_inside` resolves a
  chief's `target` and `artifact_path` the way `open` does, after the text check. Docs: the "Chief
  gate" section of `src/pathly_orchestrator/CLAUDE.md` (the "A file" bullet, "Held at the gate
  only", "Not held", "What was measured", "Not here yet", and the package-map lines of
  `code_context_cli.py` and `code/query.py`). Tests (test-only commit `d5c0a86` first): new
  `tests/code_intel/test_code_cache_projects.py` (11), `tests/http_api/test_chief_gate_code_cache.py`
  (9), `tests/db/test_run_history_wildcards.py` (16),
  `tests/http_api/test_chief_gate_feature_names.py` (17) and
  `tests/http_api/test_chief_gate_symlinks.py` (65); edits to
  `tests/code_intel/test_code_context_cypher.py`, `tests/code_intel/test_code_context_lsp.py` and
  `tests/http_api/test_chief_gate_audit.py` (listed under Review fixes (round 7)); the four
  `INDEX.md` files regenerated.

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
- Round 6: `hydrate.py` went from 403 to 388 lines because the whole-file response that was
  written out twice is now `hydrate_helpers.whole_file_result` and the containment check is
  `hydrate_helpers.inside_root` (the file would have grown past its baseline otherwise). The file
  is under 400 now, so `check_file_size.py` made me remove its baseline line; I removed that one
  line by hand, because `--update` also rewrote two unrelated baseline lines (I put them back).
- Round 6: `goal_executor._flow_kind` raises `ValueError` for a flow that is neither a goal flow
  nor one name, and `_run_team` calls it and `_load_flow` before it makes any folder. It answers
  the same `{"ok": false, "reason": "unknown_flow"}` as before for a flow that does not exist; the
  only change a caller sees is that the folder is no longer made first. I moved lines instead of
  adding them, so `goal_executor.py` stays at 492, its baseline.
- Round 6: `flow` is not a key a chief may send to `POST /comms/goals/run` (`not_for_chief`): the
  goal's executor picks its flow, and a chief that wants another one starts it with `POST /runs`.
  The review asked for a folder-name field on that route; removing the key closes the same hole
  with less surface, and the sinks hold it for every other caller.
- Round 6: `cite` is listed on `/runner/agent-answer`, `/comms/answer` and `/comms/acknowledge`
  before any view reads it, so ticket 10 can read it without the gate refusing a chief that sends
  it. `test_a_listed_key_is_read_or_is_a_url_variable_or_waits_for_a_ticket` names the keys that
  wait for a ticket (`cite`) so a listed key that nothing reads is still caught.
- Round 6: the audit's zones are the chief's project, another project, the server's working
  directory and `Path.home()` of the test (which `tests/conftest.py` points at `tmp_path`). The
  user's real home is **not** a zone: the repository may lie inside it, and the test never sends a
  real home path.
- Round 6: a key the planner sends to a decompose route that does not read it is now a 403 for
  every tier (`prompt_override` to `features/decompose` or `project/decompose`: the planner is told
  `run` first, as before; an operator is told the key is not listed). Before, the route ignored it.

- Round 7: the host decides what a backslash is, in one function (`scope_names.host_is_windows`),
  and the gate follows the host rather than a fixed rule. Why not "always refuse a backslash": a
  Windows deployment is a supported host (Studio runs there, and `C:\Users\...` is the form its
  roots arrive in), and refusing it there would lock out every Windows chief. Why not "always read
  it as a separator": that is the bug. The cost is that the same request is refused on one host
  and not on the other; that is the truth about what the route opens, not an inconsistency.
- Round 7: "the same directory" is decided by a spelling that does little: trailing slashes only.
  A `.` segment, doubled slashes inside the path and a leading space may well name the same
  directory, and the gate refuses them, because a spelling it does not rewrite is one it cannot
  get wrong. Cost: a chief that spells its root with `./` is told it is not its project. The
  prompt (ticket 17) says to use the root as the session has it.
- Round 7: a string with a drive prefix (`C:`, so also `a:b`) is read as an absolute path on every
  host and refused unless it lies under the root, though a POSIX host would read `a:b` as a
  relative name. I kept the old reading rather than guess which a route means; a symbol target
  like `a:b` is refused. Ticket 17's texts say so.
- Round 7 (reversed in round 8, see below): the Cypher fix escaped (`\` and `"`) rather than
  refusing a target with a quote: a legitimate file name can have a quote, and `/code/query` is a
  read. The escape is the standard Cypher one, which was never checked against the real tool.
- Round 7: the early-stopping baselines were made to reach their sinks, not just listed as not
  covered, wherever a baseline could: a stop with a run held, a supersede of a decision of the
  same board, an answer with a question open, `/code/query` through a canned `cli` backend. That is
  what showed the extra sink in `CliProvider._file_hash`.
- Round 8: a cache entry is for one project and for a file that has a hash. The key's project part
  is `scope_names.cache_root` (`root_spelling`, else the string as given), not the gate's own
  comparison: a cache only has to keep two projects apart, and a string this host does not read as
  a root (a backslash on POSIX) must keep a key of its own rather than share one with the folder
  its slash form names. Not caching a target with no hash (a directory, a missing file, a symbol
  such as `parse_result`) costs one backend query per repeated symbol query; the old rule cached
  those under the hash `""`, which cannot tell a changed directory from an unchanged one. The
  owner chose it.
- Round 8: the realpath check at the gate takes the path as the route opens it (the text as
  written, joined under the root when relative), not the text after the `..` collapse, because
  `link/../x` is `x` beside the link's target, not beside the link. It reads the value through
  `scope_names.host_path` so the Windows-host tests (a POSIX machine patched to read `\` as a
  separator) still mean what they said; on a real Windows host the replacement is harmless.
- Round 8: a double quote in the last two segments of a `/code/query` target is refused (no query,
  no section) rather than dropped. Dropping it would match a different file (`we"ird.py` as
  `weird.py`) and hand the chief that file's block. A file name with a quote is rare and the
  chief falls back to Grep, as for every other backend miss.
- Round 8: `_like_literal` and the `ESCAPE` clause are in `run_history.py` only. `GET
  /db/features/<feature>/runs` in `ops/db_api_feature_detail.py` has its own `feature LIKE '%/' ||
  ?`; it was not changed because the ticket names `_SLUG_MATCH`, the route is a read, and a chief
  must name its `project_root` on it, which filters the rows.

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
- Round 3 (the symlink half is closed by round 8, see below): the project binding is textual
  (`normalise_project_root`, then `posixpath.normpath` for a file); a Windows drive letter is
  compared as written (`c:/p` is not `C:/p`). Round 8 added the real-path check for a file, so a
  `/code/query` `target` or an `artifact_path` through a symlink out of the project is refused;
  what is still only text is the project root and a path-like scope (a string is the chief's own
  only when it spells the session's root).
- Round 3: the calls that name their target by an id or a name are not bound (the `unbound` entries
  of `ROUTE_FIELDS`; the list is in the "Chief gate" section). The new ones this round makes
  visible are the id-addressed reads (`GET /runs/<run_id>`, `/runner/status`, `/status?topic=`,
  `/db/runs/<id>/cost`, `/comms/artifacts/<id>/section`, `/comms/goals/refs-coverage`) and the
  `goal_id` and task `message_id` of the run and stop routes; ticket 14 covers neither. Two reads
  have no project filter at all and cannot be bound: `GET /db/rollup`'s `global` block and `GET
  /telemetry/trends` with a feature, plus `GET /metrics` and `/metrics/json`. The owner's
  decision (reads are bound where the route allows it) is met for every other route; these are
  stated in the living doc, not hidden.
- Round 5: two joins of a stored string into a path are not guarded at the sink, only by the gate
  in front of them. `event_mirror.backfill_event_mirrors` joins the `feature` of a stored event
  (the basename `eventlog.append_event` keeps, or the topic `terminal_phase` passes behind
  `_safe_topic`), and `goal_decomposer` joins the `scope` of the goal row it decomposes. The first
  relies on the gate's hold on the `scope` of `/runs` and `/comms/run`; the second is checked for
  a goal a chief posted and for none that another writer posted (the same gap as `goal_id`, which
  no ticket owns). It stops working if a non-chief route stores a path-like value in either field;
  the upgrade is the `is_segment` check at each join, as `ensure_goal_slug` and the mirror now do.
- Round 5: the sink check and the gate check are two copies of the same rule (`scope_names`
  holds the predicates, the gate decides per board). A scope the gate passes as the chief's own
  root on a feature board (`board:"feature"`, `scope:<own root>`) is accepted, and the mirror then
  rewrites `<own root>/pathly/project/BOARD.json` from the project board's rows (the posted row is
  not in it). It is the mirror's existing reading of such a scope and writes inside the chief's own
  project; it stops being fine if the mirror's reading of a path scope changes.
- Round 6: the name-pattern tripwires of `test_chief_gate_tables.py` are gone, on purpose (the
  owner's choice, finding 3): `test_a_view_and_the_helpers_it_calls_read_no_project_ish_field_its_
  entry_does_not_name` (a regex for project-like names) and `test_a_request_field_a_view_or_helper_
  joins_into_a_path_is_declared_as_one` (a list of path calls). `test_chief_gate_keys.py` replaces the
  first with a stricter one (every key a view or helper reads, found by what a name is bound to,
  must be listed or in `not_for_chief`). **Nothing replaces the second one statically**: it saw a key
  whose view joined it into a path with `join`, `Path`, `makedirs`, `mkdir` or `open`; now a key
  of a plain kind (text, number, name, enum, id, flag) that a view starts to join into a path is
  found only by the audit (`test_chief_gate_audit.py`: twelve hostile values to every file-kind key
  of an operator chief, five of them to every other key and to every key of a status or planner
  chief). It stops working for a route the audit's baseline cannot get past its first check
  (below).
- Round 6: what the audit cannot see. `os.stat`, `os.path.exists` and `os.path.isfile` are not
  audit events, so a probe for a file in another project is invisible (a read of its content is
  seen); nor is the C layer of a library (sqlite is seen at `connect` only) or what a child process
  opens (only its working directory is seen); other writers' rows (a human's post may store any
  path, and the by-id section read of it is what `contain_in` is for) are outside the sandbox; and a
  route is only as deep as the requests it is sent: `chief_audit_world.py` gives one or more valid
  requests for the routes that need one, 13 of them asserted to be accepted
  (`test_the_requests_the_audit_starts_from_are_valid_ones`), and a route with no baseline is sent
  only the project root, so a hostile value in a key it needs is stopped by its first check. The
  audit's request set is 3,830 (operator) or 2,535 (planner, status) requests per tier, not a proof.
- Round 6: three things the audit's hostile values showed that I did not change, because they are
  not the gate's: a non-numeric value for a number key in a query string makes a few `GET` views
  raise `ValueError` from `int()`, a 500 (production behaviour; the audit fixture turns
  `PROPAGATE_EXCEPTIONS` off so the test sees the 500 the server gives instead of raising it);
  a folder name over the file system's limit (the 5,000-character value) raises `OSError` in the
  route that makes the folder, also a 500; and the by-id section read tells a chief whether an id
  exists (400 `path_out_of_scope` for a row in another project, 404 for no row), though not what
  is in it.
- Round 6: feature boards are keyed by feature name only, so a chief's post to a feature board
  makes the board mirror rewrite `BOARD.json` in whichever project `run_history` last mapped that
  name to (`resolve_project_root`; the startup backfill matches by an existing
  `pathly/features/<name>/` folder). The audit does not see it because every `demo` run of its
  sandbox lives in the chief's project. The gate cannot bind a feature name to a project; the
  living doc says so (finding 5). The upgrade is to key feature boards by project, which changes
  the board model, not the gate.
- Round 6: `PROPAGATE_EXCEPTIONS=False` in the audit fixture and a `settle()` plus a 0.3 s sleep
  after seeding (a post indexes its artifact on a background thread) are the two timing-dependent
  parts of `test_chief_gate_audit.py`; the sleep is what keeps a late seeding write from being
  counted against a chief. The file takes about 40 s.

- Round 7 (replaced by round 8): `_cypher_literal` escaped a quote with a backslash, which is
  standard Cypher but was never run against the real tool. Round 8 does not rely on it: see the
  round 8 line below.
- Round 7: the kinds test (`test_chief_gate_kinds.py`) reads one function at a time and a fixed
  list of path calls. It does not follow a key into another function (`start_run(flow=...)` ends in
  `_load_flow`), and a path call it does not list is invisible to it. A plain key that a later
  change joins through such a call is caught by the audit only if the audit's plain values reach
  the join. Upgrade: follow keys across calls with the call graph, or give every key whose value a
  function receives as an argument a declared kind. Three plain keys are joined today and held by
  the view (`HELD_BY_THE_VIEW`).
- Round 7: `reroute`, `retry` and the codeintel, lsp and both backends of `/code/query` are not
  covered by the audit (the doc says so). `retry` is the one that matters: it starts a run in the
  directory the body names, which the gate binds to the chief's own root, but the audit replaces
  the run's loop, so what the started run does with a hostile value is not measured. Upgrade: a
  spawn host that runs a real fake agent, or a second audit with the supervisor's loop left in.
- Round 7: a POSIX project directory whose name has a backslash cannot be a chief's project
  (`open_chief` stores `normalise_project_root`, which makes the backslash a slash on every host).
  Not changed: the ticket is the gate, and `chief_session` belongs to ticket 07.

- Round 8: `codebase-memory-mcp` is not installed in this environment, so no query with a quote
  in it was run through the real tool, and the way its lexer reads a backslash before a quote is
  still unverified. That is why a tail with a double quote is not queried at all (the section is
  empty) and the escape is kept only for a backslash. The target's tail has had its backslashes
  made slashes before it reaches the literal, so in practice no query carries one. It stops being
  enough if the tool is found to need a quote in a name matched exactly; the upgrade is one real
  query with a quoted name, then either the escape the tool honours or its parameter form.
- Round 8: the real-path check sees a symlink that exists when the gate looks. It does not see a
  link made between the check and the open (the gate checks, the route opens later), a hard link
  (a second name inside the project for a file that is also elsewhere) or a mount, and for
  `/code/query` it checks the `target` only: what the backend (graph tool, Serena) then opens by
  its own rules is not looked at. Upgrade: open the file from the gate's descriptor, or have the
  backend refuse a path outside the root it is given.
- Round 8: the feature-board lookup is exact in what it escapes, not in case: SQLite's `LIKE`
  ignores the case of ASCII letters, so a chief's feature `Demo` still maps to a legacy row whose
  path ends in `/demo`. The living doc says so. Upgrade: compare the last path segment with `=`
  (`substr` on the position of the last `/`) once the legacy rows are gone or rewritten.
- Round 8: the empty-hash rule drops the gateway cache for symbol-style targets (`parse_result`),
  so each repeated symbol query reaches the backend. Upgrade, if that costs: key a symbol query
  on the index version the backend reports instead of on a file hash.

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

**Review fixes (round 2)** (quality review; the round starts at `5631406`. Test-only commit first:
`f298248`, run red before any source change: with `chief_fields.py` absent, 143 of the 483 tests
failed and 340 passed. The structure is fixed, not only the cases the review named.)

The cause of findings 1 to 3 is one: which request fields name a project was code, in branches per
route (`board_values`, `root_values`), so a route's fallback (`scope or feature` on `/comms/search`)
or its source (body, not query string) was missed by hand. Now it is data next to `ROUTE_ACTIONS`.
I read the view of every route the gate lets a chief reach (19 POST routes and 65 GET rules, 84
table entries) and recorded the fields it uses, the source it reads them from and
the fallback it applies; a test then holds the table to `app.url_map`.

1. *major, a query-string `project_root` satisfied "names its project".* Reproduced as the finding
   says (the test the finding names asserted it). Fixed: the rule is `Fields.names_root` of the
   route's entry and is judged against the source the view reads, the body of a POST and the query
   string of a GET (verified in the source: no listed POST view reads `request.args`, no GET view
   reads a body; a tripwire test scans the views and fails if that changes). A root only in the
   query string of `POST /runs`, `/comms/goals/run`, `/comms/run`, `/comms/tasks/run` or the three
   decompose routes is 403 `a chief names its project_root on this route`; a foreign root in either
   place is still `that is not this chief's project`. `test_a_project_named_in_the_query_string_counts`
   is flipped to `test_a_project_named_only_in_the_query_string_does_not_count` (403). New: the seven
   routes with the root only in the query string, only in the body, and in both; for a planner too.
2. *major, `/comms/search` and the `board=project` reads.* Reproduced (B's seeded decision text came
   back to all three tiers). Fixed both ways the review gave, and the owner's decision is that reads
   are bound like writes: `/comms/search` reads `scope`, else `feature` (the first usable value:
   truthy and not a blank string, so `0`, `null`, `""` and `"  "` fall through, as the view's
   `scope or feature` does), on the board `board` names (an unknown or missing one is `feature`,
   as the view takes it); `GET /comms`, `/comms/tasks`, `/comms/goals` take the same from the query
   string, and `/comms/artifacts`, `/comms/run/status` their `scope`; `/comms/trash` has no board,
   so its `scope` is bound when it looks like a path. The scope must be the session's root when the
   board is `project`. Tests: the search with `feature` as the other project and `scope` absent, `0`,
   `null`, `""`, `false` or `[]`, and with the scope given, for the three tiers; `GET /comms`,
   `/comms/tasks` and `/comms/goals` of another project's board by `scope`, by `feature`, with a
   padded `board` and with both, for the three tiers; the same reads on the chief's own board pass
   and return its rows; a feature board stays unbound.
3. *minor, hard-coded routes.* `chief_fields.ROUTE_FIELDS` is the table and `project_refusal` the one
   function that applies it; `board_values`, `root_values` and the route branches are removed (a
   mutation that switches off any one rule fails a named test). three tests walk `app.url_map` the way the action walk does and fail for a reachable `(rule,
   method)` with no entry (`test_every_route_a_chief_can_reach_says_which_fields_it_reads_as_a_
   project`), for an entry whose rule no route has (`test_the_field_table_lists_no_route_that_does_
   not_exist`) and for an entry that names no field and gives no `note` (`test_an_entry_names_a_
   field_or_gives_a_reason`); a route with no entry is refused by the gate (`NO_ENTRY`), so the
   gate fails closed even if a test is not run.
4. *minor, an absolute `/code/query` `target`.* Fixed: `target` is anchored on the session's root (a
   relative one is the project's own) and must lie under it once its `..` segments are collapsed, in
   POSIX and Windows drive spelling (`C:\other`, `c:/other`), else 403 `a chief names only files
   inside its project`; `/code/query` also now has to name `project_root` (without it the backend
   resolves a relative target against the server's directory). 11 outside targets for the 3 tiers
   are refused, 8 inside ones pass, and the root is required. Same rule for the file `POST
   /comms/post` stores as `artifact_path` (it must be absolute; `GET /comms/artifacts/<id>/section`
   later reads whatever path the row keeps, whole) and the path an `artifact` post takes from its
   `text` when `artifact_path` is blank (always relative, so refused): 9 refused variants, an
   inside one and a note that merely mentions a path pass.
5. *minor, missing tests.* Added with 1 and 2: the query-string-only root on all seven run routes,
   the `board=project` reads, the search fallbacks, the target and artifact path cases, the
   completeness walk, a source-scan tripwire for the body/query rule, and a fail-closed test that
   empties the table and sees 403 on every reachable route.

Found by reading the routes, not named by the review, and bound the same way: `POST /comms/post`
with `context_refs` must name `project_root` (the refs resolve under the server's directory
otherwise); the `/db/features`, `/db/stats`, `/db/stats/trends`, `/db/recent`, `/db/rollup`,
`/db/features/<feature>/{agents,events,otel,runs}`, `/status` and `GET /comms/artifacts/section`
reads fall back to `PATHLY_PROJECT_ROOT` or to every project when `project_root` is absent, so they
must name it (a status chief that sends no root used to read the server's own project's runs and
costs); the board-less scope ids (`/comms/trash`, `/hq/context`, the two artifact-section routes)
are bound when they look like a path; `GET /runs`, `/api/*`, `/skills/*` and `/flows/stage-config`
filter by the `project_root` they are given, which is bound.

Stated plainly instead of bound, because the route cannot be (living doc, "Chief gate", bullet "Not
bound", and Shortcuts above): calls addressed by an id or a name (`goal_id`, a task's `message_id`,
`run_id`, `topic`, `artifact_id`, a feature name) and the fleet-wide reads (`/db/rollup`'s `global`
block, `/telemetry/trends` with a feature, `/metrics`). The wording that implied a binding that
did not exist ("Every value the call uses to name a project must be the session's") is replaced.
Tests I edited, not only added: the `/code/query` case of `test_a_status_chief_may_call_the_read_
routes` and the `_code_query` helper send `project_root` now (the route requires it); the query-
string test was flipped (item 1); `test_the_routes_that_must_name_a_project_are_the_listed_run_and_
decompose_routes` was replaced by the table-based tests (item 3); no assertion was loosened.

Proof after the fixes (each run fresh, after the last edit to code and tests; docs were edited
after the last full code run, and the Done-when commands were run again after that):

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `483 passed in
  132.14s`, exit 0. `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p
  no:cacheprovider` -> `33 passed in 7.33s`, exit 0.
- Mutation checks, each against the matching tests, each failing (17): naming rule off; the query
  string counting as naming; the `/comms/search` `feature` fallback off; the board name not
  stripped; `_under` always true; the text-recovered path off; a missing entry passing; the GET
  scope reads off; bare scope ids unbound; absolute paths off; relative targets not anchored; a
  Windows drive not absolute; the universal `project_root` check off; the `(marker)` skip off; the
  decompose override off; the `context_refs` naming off; the `/db/stats` naming off.
- Test command from `commands.md` -> `1856 passed, 2 skipped in 414.75s`, exit 0 (the 2 skips are
  not mine). `tests/consistency tests/local_operator tests/hq_copilot` -> `155 passed in 20.91s`.
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (588 files
  unchanged), `mypy` (`no issues found in 325 source files`), `check_file_size.py` (`none new, none
  grown`; `chief_fields.py` 298, `chief_project.py` 168, `chief_gate.py` 137, `chief_routes.py` 117
  lines), `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0
  broken`), `bandit -q -r src/ -ll -x src/pathly_data/` (no SQL added), `check_adapters.py`,
  `check_entry_points.py`. Smoke and `python -m build --wheel` exit 0. No `# noqa`, `# nosec` or
  `type: ignore` added.

**Review fixes (round 3)** (quality review; the round starts at `6d48b88`. Test-only commit first:
`d3d52b1`, run red before any source change: 129 of the 648 tests failed and 519 passed. Then the
fix, `53dc2fa`, and the test split, `45357e6`, as its own commit. The cause of findings 1, 2, 4 and
5 is again one: the table said less, or more, than the view does with a field. Each fix is a table
entry or a route guard, and each is held by a test that fails without it.)

1. *major, `retry` falls back to the server's directory.* Reproduced as the finding says: with a
   finished registry run, `POST /runs/run-own-1/retry` with `project_root` `""`, `null`, `0`, `false`,
   `[]` or `{}` passed the gate and `start_run` received the empty root (an absent key was refused
   by the route's own 400, not by the gate). Fixed by a naming rule that knows the verb:
   `Fields.names_root_verbs=("retry",)` on `/runs/<run_id>/<action>`, applied in
   `chief_project._unnamed_root` from `request.view_args["action"]`, so `retry` needs a truthy
   `project_root` in the body (403 `a chief names its project_root on this route`) and `pause`,
   `resume`, `advance`, `reroute`, `stop` and `abort` still need none
   (`test_the_other_run_verbs_need_no_root`). Tests: seven empty spellings refused, the own root
   starts the run there (`start_run` receives it), another project's root refused. The exclusion in
   `test_every_route_that_starts_an_agent_in_a_directory_names_its_root` is shrunk: the by-id rule is
   no longer left out, the test now requires `names_root_verbs == ("retry",)` there and that
   `RUN_VERB_ACTIONS` classes that verb `run`. The tripwire now reads the helpers a view calls too
   (see item 8). The run id of the route is still ticket 14's.
2. *major, `feature` of `/comms/features/decompose` is a folder name.* Reproduced (a planner and an
   operator chief with `feature="../../../proj-b/pathly/features/planted"` and every rigor made the
   folder inside project B). Fixed in both places, as the finding recommends: the route refuses a
   `feature` that `storage_paths._is_unsafe_topic` rejects (400 `invalid_feature`, before any
   `makedirs`), and the gate treats the field as a folder name (`ScopeRead(..., segment=True)`: a
   string without `/`, `\`, `:`, a NUL, and not `.` or `..`, else 403 `feature must be one folder name`).
   The gate is stricter than the route on purpose: the route allows a nested `a/b` (the existing
   `_is_unsafe_topic`), the gate refuses it, because a chief's feature is one folder. A route test
   plants nothing outside the project (8 spellings x 3 rigors: 400 `invalid_feature`, no run
   started, the other project's tree empty) and still makes the folder for a plain name; the gate
   tests cover the three rigors and both tiers, 12 path spellings (4 of them the route allows, such
   as `sub/dir`), non-string values, and plain names that must pass (`Q3 plan`, `.hidden`).
   **Found by the same check, not named by the review:** `POST /comms/run` of an `evaluator` on a
   `feature` or `global` board saves a reply that posted no `BOARD_EVAL` artifact to
   `<project_root>/pathly/features/<scope>/artifacts/`. The review's probe got a 500 there. With
   the spawn faked (the test's `evaluator_reply`) the request answers 200 and the run's `_on_done`
   writes the evaluation inside project B for `scope="../../../proj-b/planted"` on a `global`
   board (red run: `test_the_route_saves_no_evaluation_outside_the_project` failed). Fixed
   the same way: the `scope` of `/comms/run` is a `segment` when the board is not `project` (a
   project board's scope is the root and stays bound as a root), and `runs.py` saves no evaluation
   under an unsafe scope (it falls to the existing warning post). Tests: the route saves the
   evaluation inside the project for a plain scope and nothing outside it for three traversal
   scopes; the gate refuses them; a project-board run still names the root as its scope. A
   mutation of any of the four guards (route and table, each route) fails a named test.
3. *major, the "Chief gate" section overclaims.* Corrected after the code was fixed, against the
   code: "Naming it" now lists exactly what is refused when no root is named (including `retry` and
   `/telemetry/trends` without a feature) and names the exceptions that do not need a root and why
   (`GET /runs`, `/api/*`, `/skills/*`, `/flows/stage-config`, `/db/agents`, `/comms/permissions`,
   `/comms/scope`, `/hq/context`, `/chief/session`: they filter by the root when given one, or read
   no project); a new bullet says what a folder-name field is; "Not bound" gains the `/db/stats`
   global counts and the rule for `under_root`; "Reads are not all pure" now lists **four** writes,
   with `GET /skills/prompts` without `kind` (or `kind=preset`), which calls
   `migrate_db_presets_to_files`, writes prompt files and deletes the legacy DB rows. I verified the
   fourth by reading the view; I did not add a binding for it (the route reads no project at all),
   and it is stated rather than hidden.
4. *minor, `/telemetry/trends` and `/db/stats`.* `/telemetry/trends` with a blank or whitespace
   `feature` and no `project_root` is refused: `Fields.names_root_unless=("feature",)` (the root is
   required unless a usable feature is given). A named feature stays summed across every project, the
   same exposure class as the accepted `/db/rollup` global block, and the entry's note says so.
   `/db/stats` keeps its `project_root` filter for cost and tokens, and its note now says that its
   `features`, `events` and `invocations` counts are global. Tests: the three tiers with a blank
   feature (no root, another project's root, the own root), the fleet-wide note, the `/db/stats` note.
5. *minor, `unbound=("feature",)` was misleading.* Fixed with `Fields.under_root`: a name the view
   reads together with `project_root` and filters by it is bound by the root the gate already checks.
   `unbound` now lists only what the route really leaves to the caller. Moved to `under_root`:
   `feature` on `/db/rollup`, `/db/features/<feature>/{agents,events,otel,runs}`,
   `/api/features/<feature>/{artifacts,events,invocations,metrics}`, `/api/traces`,
   `/flows/stage-config` and `/comms/scope`, and `artifact` on the two artifact-section routes. I
   checked each against its query before moving it. Left in `unbound`: `run_id` (`/runs/<run_id>/...`,
   `/api/traces`), and the feature of `/telemetry/trends` (summed across every project). A test
   holds the twelve `feature` entries: `feature` is not in their `unbound` and `project_root` is in
   their `roots`.
6. *minor, ownership of id-addressed calls.* Not changed in ticket 14, as the brief says. The calls
   nothing owns are recorded under **For later tickets**, as an exact list.
7. *minor, legitimate flows.* No change needed. The 403 text names the missing field (`a chief
   names its project_root on this route`), so the chief can tell what to add; the same text is used
   for the new `retry` and `/telemetry/trends` refusals. Ticket 17's prompt must say what the
   finding lists (see **For later tickets**).
8. *minor, one 2165-line test file and a tripwire that misses helpers.* The tripwire now reads the
   view **and the helpers it calls** (`create_run`, `handle_retry`, `_dispatch_*`): functions called
   by name, as a module-level name or an import inside the body, that live under `blueprints/`, to
   three levels; `test_the_walk_reaches_the_helpers_the_views_call` fails if that walk stops
   reaching them. It replaces the view-only tripwire and is a superset of it (`data["x"]` is read
   too, not only `data.get("x")`). A second tripwire fails when a field the entry calls an id is
   used as an argument of a path call (`join`, `Path`, `makedirs`, `open`, ...) in a view or helper
   (`test_a_request_field_a_view_or_helper_joins_into_a_path_is_declared_as_one`); a mutation that
   puts `feature` back as an id fails it. Both are **heuristics**: they match by variable name, so a
   helper that renames the value, calls a method (`obj.f(x)`) or goes deeper than three levels is not
   seen. The split is its own commit, `45357e6`: `test_chief_gate.py` (the Done-when cases, 97 tests),
   `test_chief_gate_actions.py`, `_bodies.py`, `_requests.py`, `_project_scope.py`,
   `_root_naming.py`, `_board_reads.py`, `_files.py`, `_tables.py`, `_folders.py`,
   `_unbound_reads.py`, and `chief_gate_support.py` with the shared fixtures and helpers (the three
   autouse fixtures and `app` are imported into every file, so each file runs alone). No assertion
   changed or was weakened: every top-level definition has the same AST as before (176 names, 0
   differences), the 651 collected node ids are the same set, each file passes on its own, and the
   mutation run below was repeated against the split files.

Tests I edited, not only added: `test_run_control_verbs_are_run_or_stop` (the `retry` call now sends
`project_root`, because the gate now requires it), `test_a_route_that_names_its_root_reads_one`
(covers the two new naming fields), the exclusion in `test_every_route_that_starts_an_agent_in_a_
directory_names_its_root` (item 1), and the view-only tripwire (replaced by its superset, item 8).
No assertion was loosened.

Also worth knowing: `start_board_run` leaks the board lock when `_resolve_storage_path` raises (it
raised for the traversal scope before the guard). It is pre-existing and not touched here; the guard
means a chief can no longer reach it with a path-like feature or scope, but another caller still can.
A path-like feature scope also made the board mirror write `<scope>/pathly/project/BOARD.json` under
the working directory in the red runs; the guard stops that too.

Proof after the fixes (each run fresh, after the last edit to code, tests and docs):

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `97 passed in
  27.71s`, exit 0 (the Done-when cases; the whole chief set, `tests/http_api/test_chief_gate*.py`, is
  651 tests: `651 passed in 167.65s` before the doc-only edits that followed, and inside the Test
  command below after them). `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p
  no:cacheprovider` -> `33 passed in 8.18s`, exit 0.
- Test first: at `d3d52b1`, `129 failed, 519 passed` (the retry, feature-name, evaluator-scope,
  trends, `/db/stats`, `under_root` and tripwire cases); all 648 pass at `53dc2fa` plus the three
  tripwire tests that commit added (651).
- Mutation checks, each run against the matching tests of the split files, each failing (13): the
  `retry` rule off; `names_root_unless` off; the segment check off; `.` and `..` allowed as a
  segment; `:` allowed in a segment; the `features.py` guard off; the evaluation-save guard off;
  `/comms/run` scope not a segment; `/comms/features/decompose` feature not a segment; the
  `/db/stats` note gone; `/db/rollup` `feature` unbound again; `retry` dropped from the table;
  `/telemetry/trends` root rule dropped from the table. Before the split, one more: the helper walk
  cut to the view alone fails `test_the_walk_reaches_the_helpers_the_views_call`.
- Test command from `commands.md` -> `2024 passed, 2 skipped in 440.99s`, exit 0 (the 2 skips are
  not mine). `tests/consistency tests/local_operator tests/hq_copilot` -> `155 passed in 20.89s`.
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (599 files
  unchanged), `mypy` (`no issues found in 325 source files`), `check_file_size.py` (`none new, none
  grown`; `chief_fields.py` 342, `chief_project.py` 201, `chief_gate.py` 139, `chief_routes.py` 117
  lines), `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0
  broken`), `bandit -q -r src/ -ll -x src/pathly_data/` (no SQL added), `check_adapters.py`,
  `check_entry_points.py`. Smoke and `python -m build --wheel` exit 0. No `# noqa`, `# nosec` or
  `type: ignore` added.

**Review fixes (round 4)** (quality review; the round starts at `c88f85b`, work from `56ba48c`.
Test-only commit first: `0ab8cdb`, run red before any source change: `364 failed, 178 passed` over
its three files (the first run, before I amended the commit to exclude the global mirror from the
"nothing written" assertions, counted 371 failed; the count moves a few tests between runs with
the flusher thread's timing, and I did not chase that). The cause of finding 2 is one: the gate
bound a scope by the board the request **declared**, while the board mirror reads the **shape** of
the scope. I closed the class, not the one route: a request string that becomes a filesystem path
is now held where the gate sees it and again where the path is made.)

1. *major, "Reads are not all pure".* Verified in the code (`artifacts.py::comms_artifact_section`
   -> `hydrate_section` -> `ensure_indexed` -> `find_or_create_artifact_by_path`): for an existing
   file under a `pathly/features|plans|goals|project/` folder it inserts a sentinel
   `comms_messages` row (board `feature`, the given scope, from `system`, type `artifact`), a
   `comms_artifacts` row and a section index, with no `trail`. The "Chief gate" section now says
   **five** small writes and lists this one, saying it needs no `trail` and works at any feature
   scope the caller names (the scope is now held by the rule in item 2). I did not change the
   hydrate path, as the brief says.
2. *major, a path-like scope on a feature or global board plants files in another project.*
   Reproduced (red run: `test_a_chief_plants_no_file_in_another_project_through_the_scope_of_a_
   post`, 8 cases: the gate passed the post, where the review's probe saw the mirror write
   `<other project>/pathly/project/BOARD.json`). Closed in the three places the brief names:
   - **(a) the gate.** `chief_project._scope_refusal`: a scope that looks like a path (`/`, `\` or a
     drive prefix) must be the chief's own root on **every** board (403 `that is not this chief's
     project`), and a scope on a board other than `project` that is not a path must be one folder
     name (`scope_names.is_segment`: no `/`, `\`, `:`, NUL, not `.` or `..`). This is in the one
     function every `ScopeRead` goes through, so it applies to `/comms/post`, `/runs`, `/comms/run`,
     `/comms/run/stop`, `/comms/search`, `/comms/features/decompose`, `GET /comms`,
     `/comms/tasks`, `/comms/goals`, `/comms/artifacts`, `/comms/run/status`, `/comms/trash`,
     `/hq/context` and the two artifact-section reads: a test walks the 15 `ScopeRead`s of
     `ROUTE_FIELDS` that are not the project board's and sends nine path spellings (a foreign
     root, `OWN/../proj-b`, `../proj-b`, `sub/dir`, `C:/other/proj`, `C:\other\proj`, `a\b`,
     `..`, `.`) on `feature`, `global` and no board: all refused, and five plain names (a dot, a
     space, unicode) pass. The own root passes on a non-project board (it is bound, as the
     brief allows); a `segment` scope (`/comms/features/decompose`, the `/comms/run` evaluator)
     still refuses even the own root. A new `Fields.segments` names a stored field the server
     later joins into a folder: `/comms/post` declares `slug` (below).
   - **(b) the sink.** `board_mirror.py` now answers only a normalised absolute project root on the
     project board (`scope_names.is_project_root`: starts `/` or `X:/`, no `\`, no NUL, no
     trailing `/`, no `.` or `..` part) and one plain folder name on a feature board:
     `board_from_scope` returns None for any other scope, `mark_board_dirty_by_scope` queues
     nothing, `write_board_mirror` returns False before touching a path (also when the pair is
     queued directly with `mark_board_dirty`), and `board_mirror_path` is None for a non-segment
     feature scope. It covers the callers the gate does not see (a human, an agent with another
     token): `test_the_route_itself_plants_nothing_for_a_scope_that_is_a_path` posts with no token
     and the other project's tree stays empty. Legitimate scopes are unchanged: roots in POSIX and
     `C:/...` spelling with spaces and unicode, `//server/share/...`, and feature names with dots,
     spaces and unicode (`Q3 plan`, `café-ü`, `v1.2.3`, `.hidden`, `(interactive)`); the existing
     `test_board_mirror*.py` files (3, unchanged) pass, and `test_a_legitimate_project_root_still_
     gets_its_mirror` writes the mirror for a plain, a spaced and a unicode root.
   - **`POST /runs`, `kind=single`, board `global` or `feature`, traversal scope** (the "less
     certain" case). The gate passed it before (red: 81 cases of `test_a_run_cannot_name_a_path_
     as_the_scope_of_a_feature_or_global_board` failed, the faked run was started). It is refused
     now for `single`, `evaluator` and `flow` on `feature`, `global` and no board, and the run
     file-planting test passes with nothing created in either project. I did not trace the
     early-advance-off slow path through `terminal_phase.py`; the gate refuses the scope before it
     and `_resolve_storage_path` (`_safe_topic` or the root itself) stands behind it.
   - **Found by the same check, not named by the review:** a goal's `slug` is stored from
     `POST /comms/post` as given and the goal run and decompose later make
     `pathly/features/<scope>/goals/<slug>` (and `os.makedirs` it) from it, so a chief could post
     `slug: "../../../../proj-b/planted"` (red run: `test_a_goal_run_plants_nothing_for_a_stored_
     slug_that_is_a_path`, 7 cases: `resolve_goal_home` handed the stored path back as the goal's
     folder name and joined it under the project). Held
     twice: the gate (`Fields.segments=("slug",)` on `/comms/post`: 403 `slug must be one folder
     name`) and the sink (`supervisor/slug.py::ensure_goal_slug` ignores a stored slug that is not
     a plain folder name and generates and stores a new one, so a goal posted with no token is
     safe too).
   - **(c) every other place a chief-reachable route turns a request string into a path**, read in
     the code (a list, not a proof; also in the "Chief gate" section). **Guarded:** the board mirror
     (gate and sink); `features/decompose` and the evaluator save (gate `segment`, and the routes'
     `_is_unsafe_topic`); the goal `slug` (gate and sink); `fsm_ops._resolve_storage_path` for
     `start_run` and `start_board_run` (`_safe_topic`, or the project root itself); the
     `context_refs` of a post and `GET /comms/artifacts/<id>/section`
     (`hydrate_helpers.safe_artifact_path`, a realpath containment check); a post's
     `artifact_path`, the path recovered from an artifact post's text and `/code/query`'s `target`
     (gate text containment; symlinks are not followed, said above); the `topic` of `/status` (read
     against the database and the feature folder it names, behind `_safe_topic`); the `/db/*`
     reads (rows filtered by the bound `project_root`, no file opened from the request);
     `GET /skills/prompts` (a category filter; `_SEG_RE` on writes, which the gate does not
     reach); the flows, menu, summary-format, catalog and `/api/*` reads (the database or an
     allow-list); `/ops/export/skills` (configuration, not the request); static files (Flask's
     own); the phase-summary fallback of `terminal_phase` (`.exists()` and a database event only).
     **Not guarded at the sink:** `event_mirror.backfill_event_mirrors`, which joins the `feature`
     of a stored event (kept as a basename by `eventlog.append_event`, or a `_safe_topic` topic from
     `terminal_phase`; the gate holds the scope of `/runs` and `/comms/run` that feeds it); and
     `goal_decomposer`, which joins the `scope` of the goal row it decomposes (the gate checks it
     for a goal a chief posts, nothing checks it for a goal another writer posts: the same gap as
     the unowned `goal_id`). Both are listed under **Shortcuts taken** and in the living doc.
   - Tests: `tests/comms_board/test_board_mirror_scope.py` (new: the sink, 19 refused and 14
     accepted spellings through `board_from_scope`, the dirty queue, `flush_dirty`,
     `write_board_mirror` and `board_mirror_path`, the relative-traversal case end to end, and the
     legitimate root) and `tests/http_api/test_chief_gate_mirror.py` (new: the post route for two
     tiers x three boards x nine spellings, the fall-back-to-`feature` case, files planted in the
     other project and in the chief's own tree, the tokenless route, `/runs` for three kinds x
     three boards, the table walk, the own-root/foreign-root binding of every scope read, the
     slug). The "nothing written" assertions exclude `~/.pathly` (the fake home holds the global
     mirror in every test). The own-root/foreign-root test was added after the test-only commit,
     because the mutation run (below) showed that dropping the path rule left the other tests green
     (a path was still refused, as a bad folder name); it asserts the refusal text and that the
     chief's own root passes.
3. *minor, `/db/rollup`'s `by_project`.* "Not bound" item 2 now says the `global` block also lists
   every project's root path with its cost and tokens (`by_project`), so a status chief can read
   where the other projects are and what they spend. The entry's `note` in `chief_fields.py` says
   it too. I did not drop the rows for a chief: that is a change to a read route the brief puts
   outside this ticket.
4. *minor, the id-addressed reads and the folder-name bullet.* `GET /comms/artifacts?message_id=`
   is added to the id-addressed reads that no ticket owns (its entry has `unbound=("message_id",
   "goal_id")`, which was right). The "A project board's scope" bullet no longer says an unknown
   board is "not bound": a path is bound on every board and any other scope off the project board is
   one folder name. The "A folder name" bullet now lists the three ways a request string becomes a
   path (a decompose or evaluator folder, a stored `slug`, a scope that reaches the mirror), the
   sink guards, and the list from (c); its tripwire sentence says the two tripwires miss a scope
   that only reaches the mirror, and which rule holds it instead. `test_a_request_field_a_view_or_
   helper_joins_into_a_path_is_declared_as_one` now counts a `segments` field as declared safe, and
   the `segment`-scopes test says why only two routes are listed.
5. *minor, ticket 14's first sentence.* I did not edit ticket 14 (not mine to edit). It is stale,
   and `chief_bind` must stay consistent with `ROUTE_FIELDS`; both are under **For later tickets**.

Tests I edited, not only added: `_PROJECT_ISH` in `test_a_view_and_the_helpers_it_calls_read_no_
project_ish_field_its_entry_does_not_name` gains `slug` (the tripwire must see a field the table
now declares), `path_safe` in `test_a_request_field_a_view_or_helper_joins_into_a_path_is_declared_
as_one` gains `*fields.segments`, and a docstring on `test_the_segment_scopes_are_the_two_routes_
that_make_a_folder_of_them`. A new test, `test_a_post_that_stores_a_slug_declares_it_a_folder_name`,
holds the `slug` entry. No assertion was loosened.

Proof after the fixes (each run fresh, after the last edit to code, tests and docs):

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `97 passed in
  28.09s`, exit 0. `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p
  no:cacheprovider` -> `33 passed in 7.65s`, exit 0. The whole chief set and the mirror tests,
  `tests/http_api/test_chief_gate*.py tests/comms_board/test_board_mirror*.py` -> `1238 passed in
  274.22s`.
- Test first: at `0ab8cdb` (the source as it was at `56ba48c`), the three test files of that commit
  gave `364 failed, 178 passed`, re-run today. Of the failures, `test_a_scope_that_is_a_path_is_
  refused_on_every_board_but_the_project_board` 89, `test_a_run_cannot_name_a_path_as_the_scope_...`
  81, `test_a_post_cannot_name_a_path_as_the_scope_...` 54, the sink tests (`write_board_mirror`,
  `board_from_scope`, the dirty queue, `flush_dirty`, `board_mirror_path`, the end-to-end case) 93,
  the slug tests 21, the post that falls back to a path `feature` 8, the file-planting tests (post,
  run, and the tokenless route) 16, and two tripwire tests: 364. All pass with the fix.
- Mutation checks (nine, each failing the named tests; the script restored every file and
  `git status` is clean of them): the mirror reads any `/` as a project root; a feature scope
  need not be a segment in `board_from_scope`; `write_board_mirror` skips `_scope_fits`;
  `board_mirror_path` accepts a non-segment; `ensure_goal_slug` trusts a stored path slug; the gate
  does not bind a path scope off the project board (this one **survived** the first run: a path was
  still refused as a bad folder name, so I added `test_a_scope_that_is_a_path_is_bound_to_the_
  chiefs_project_on_every_board`, which asserts the refusal text and that the own root passes, and
  it now fails the mutation); a non-path scope off the project board need not be a segment; the
  `segments` field is not checked; `/comms/post` no longer declares `slug`.
- Test command from `commands.md` -> `2568 passed, 2 skipped in 533.94s (0:08:53)`, exit 0 (the 2
  skips are not mine). `tests/consistency tests/local_operator tests/hq_copilot tests/storage_paths
  tests/dag_goals` (the last two because `slug.py` and the mirror were touched) -> `451 passed in
  75.49s`.
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (602 files
  unchanged), `mypy` (`no issues found in 326 source files`), `check_file_size.py` (`none new, none
  grown`; `scope_names.py` 43, `board_mirror.py` 306, `slug.py` 111, `chief_fields.py` 363,
  `chief_project.py` 204 lines), `check_no_mirror_reads.py`, `gen_test_index.py --check`,
  `lint-imports` (`1 kept, 0 broken`), `bandit -q -r src/ -ll -x src/pathly_data/` (no SQL added),
  `check_adapters.py`, `check_entry_points.py`. Smoke and `python -m build --wheel` exit 0. No
  `# noqa`, `# nosec` or `type: ignore` added (grepped over the diff).

**Review fixes (round 5)** (quality review; the round starts at `12df38b`, work from `acf32ae`.
Test-only commit first: `acf32ae`, run red before any source change: `56 failed, 7 passed` over its
three files, re-run today in a worktree of that commit against the source as it was at `7521392`.
The project owner chose "strict keys" for it. The cause of findings 1, 2 and 4 is one: a request
key reached a join (a folder, a packaged file, a stored path) and the table did not list the key,
because the table listed only what looked like a project. So the table now lists everything, and
refuses the rest: an entry is the complete list of the keys a chief may send, a key that can reach a
path has a kind with a rule at the gate and at the sink, and two tests, one static and one that
watches the file system, check the lists against the code.)

1. *blocker, `flow` on `POST /comms/goals/run` made folders in another project.* Reproduced as the
   finding says (red: `test_the_goal_run_route_makes_no_folder_for_a_flow_that_is_not_a_flow`, 8
   cases posted with no token, and `test_a_chief_cannot_name_a_flow_on_a_goal_run`, 8 more): with `executor:
   "team"`, `_run_team` made `pathly/features/<scope>/<flow>/<slug>` of the flow (`_flow_kind`
   returned any unknown name) and `os.makedirs`'d it, and only then did `_load_flow` answer
   `unknown_flow`. Held three times:
   - **the gate:** `flow` is not a key of that route (`not_for_chief`), so any chief that sends it
     is 403 naming `flow`;
   - **the folder:** `goal_executor._flow_kind` raises `ValueError` for a flow that is neither a
     goal flow nor one name (`scope_names.is_flow_name`), and `_run_team` now runs `_flow_kind` and
     `_load_flow` first and answers `unknown_flow` before `board_run_topic` and `os.makedirs`; the
     route answers 400 `unknown_flow` as before, with no folder in either project (the test posts
     with no token, so the gate is not what stops it). A packaged flow still gets its folder
     (`test_the_goal_run_route_still_makes_the_folder_of_a_packaged_flow`);
   - **the reader:** `fsm_ops._load_flow` (below).
2. *major, `skill` on `POST /comms/run` and `flow` on `POST /runs` read files outside the packaged
   folders.* Reproduced (red: `test_a_chief_cannot_start_a_flow_named_by_a_path`, `test_a_chief_cannot_
   name_a_skill_that_is_a_path`, and `test_the_run_route_hands_an_agent_no_file_outside_the_skills`,
   which puts a marker line in `<other project>/planted.md`, names it as the skill with no token,
   and checks that what the faked spawn host was handed holds no marker). Fixed at the
   readers and at the gate, with one pair of predicates: `scope_names.is_flow_name` (one folder
   name) and `is_skill_name` (`name` or `category/name`, each part one name) and
   `resolves_inside(root, path)` (symlinks followed). `fsm_ops._load_flow` reads a packaged flow
   only when the name passes and the file resolves inside `core/flows` (else `FileNotFoundError`,
   which `start_run` already answers); a flow stored in the database is found by its name and never
   opened as a file. `compose_resources._skill_file` does the same for `core/skills`, and
   `_skill_exists` answers False for such a string. At the gate, `Fields` kinds `FLOW` (the `flow` of
   `POST /runs` and `/runs/<run_id>/<action>`) and `SKILL` (the `skill` of `POST /comms/run`) are
   checked by `chief_keys.key_refusal`; the 403 names the key. A packaged flow and a packaged
   skill still load (`test_a_packaged_flow_still_loads`, `test_a_packaged_skill_is_still_composed_
   into_the_prompt`, `test_a_chief_may_name_a_packaged_skill`). The 58 tests of `tests/storage_paths/
   test_scope_names_flow_skill.py` pin the predicates (names a packaged flow or skill can have,
   `..`, absolute, UNC, drive, NUL, empty, non-strings, a link out of the folder).
3. *major, the claim and the tripwire.* The "Chief gate" section no longer says the gate holds "each
   of three ways". It lists, in "What reaches a path, and what holds it", what is held at the gate
   and the sink, at the gate only, by the route's own design, and **not held** (feature boards
   keyed by name, the event-mirror backfill, `goal_decomposer`); and "What was measured" says what
   the audit did and what it cannot see. The review asked for a tripwire that lists every key a view
   reads, not only project-like names:
   - **the table is the list.** `chief_keys.key_refusal` (called last by `chief_gate._refusal`)
     refuses a body key (a query key for a GET) the entry does not list, with a 403 naming it, on
     every route; the entries were rewritten from the views and every helper they call: 84 entries,
     221 listed keys, each with a kind (text, number, flag, enum, name, id, root, scope, segment,
     path, ref, flow, skill) and 9 keys a view reads that no chief flow needs, in `not_for_chief`;
   - **a static test** reads the views and the helpers under `blueprints/` for the keys they read
     (`tests/http_api/test_chief_gate_keys.py`, 88 tests, with the AST walker in
     `chief_walk_support.py`: found by what a name is bound to, not by what the key is called; three
     levels of helper). It fails when a view reads a key the entry neither lists nor puts in
     `not_for_chief`, when `not_for_chief` or the list names a key nothing reads (a ticket's `cite`
     is the one exception, named in the test), and for each file kind it sends hostile values to the
     gate; `test_chief_gate_strict_keys.py` (30) sends an unlisted key to every route;
   - **a property test that watches the file system** (`test_chief_gate_audit.py`, 6 tests): it
     sends hostile values to every key of every route of the table, and to every variable of its
     URL, as a status, a planner and an operator chief, and records every file system call the
     process makes with `sys.addaudithook`; none may fall in the other project, the server's
     working directory or the home directory. The same file shows the audit sees each kind of call
     and a write a request makes (a post with no token that names another project's root as a
     board's scope makes the mirror write that project's `BOARD.json`; a chief's is refused).
   - I **removed** the two name-pattern tests the review called weak (see Shortcuts for what the
     second one saw that nothing static replaces). The "Chief gate" tripwire paragraph now says what
     the new tests read and what they do not.
4. *major, `GET /comms/artifacts/<id>/section` had no containment on the id branch.* Reproduced
   (red: `test_a_chief_does_not_read_a_file_of_another_project_through_an_artifact_id`, three tiers,
   and `test_the_section_route_reads_no_file_outside_the_root_it_is_given`: a row another writer
   posted with a path in another project was read, 200, with and without `project_root`). The
   document had said `safe_artifact_path` holds it, which is true of the by-path branch only. Fixed
   at both ends. The sink: `hydrate_section(..., contain_in=<root>)` answers 400
   `path_out_of_scope` (`outside the project`) when the row's stored path is not under that root
   (`hydrate_helpers.inside_root`: real paths on both sides, symlinks followed), before it reads,
   indexes or posts anything, and `comms_artifact_section` passes the root the request names. The
   gate: the route is in the set that must name its root (`NAMES_A_PROJECT_READS` of the tests,
   `names_root` of the entry), so a chief that sends no `project_root` is 403 and one that sends
   its own gets the check. A caller that names no root (Studio, a human) reads the stored path as
   before; that is stated in the section. The chief's own project's file still reads
   (`test_a_chief_still_reads_a_file_of_its_own_project_through_an_artifact_id`).
5. *minor, three imprecise sentences.* Each checked against the code and reworded: (a)
   `board_mirror_path` is None for an unfit scope on a **feature** board only; on the project board
   it joins whatever root it is given and `write_board_mirror`'s `_scope_fits` is what stops it.
   (b) the `/db/*` reads: `GET /db/features` and `/db/stats` glob and read `STATE.json` and
   `RUNNER_STATE.json` under the bound root, so what they open lies inside the chief's own project.
   (c) feature boards are keyed by name only, so the mirror writes a feature board's `BOARD.json`
   into whichever project `run_history` last mapped the name to (the startup backfill matches by an
   existing `pathly/features/<name>/` folder), which may not be the chief's. Listed as **not held**
   and under Shortcuts.
6. *minor, a relative project root is no longer mirrored.* A project board whose scope is `proj/x`
   was written under the server's working directory before the round-4 fix (`scope_names.
   is_project_root`); since then its rows are stored and served as before and the export is gone. Deliberate, now pinned: `tests/comms_board/test_board_mirror_
   relative_root.py` (12 tests: five relative spellings are no project board to the mirror, post
   and flush write nothing and the rows stay, the startup backfill exports nothing for them, the
   same root named absolutely is mirrored), and one bold sentence in the "A folder name" bullet of
   the living doc.

Tests I edited, not only added: `test_chief_gate.py::test_operator_passes_the_decompose_routes_with_
overrides` now sends `prompt_override` only to `/comms/goals/decompose` (the one decompose route
that reads it) and asserts the other two refuse it for an operator, naming the key; before, the
routes ignored the key and the gate let it through. `chief_gate_support.NAMES_A_PROJECT_READS`
gains `/comms/artifacts/<artifact_id>/section`, and `test_chief_gate_root_naming.py` fills the
`<artifact_id>` converter in its path (finding 4). `test_chief_gate_tables.py` lost the two
name-pattern tests (finding 3) and its walker helpers (`chief_walk_support.py` has them now). No
assertion was loosened and no test is skipped.

Proof after the fixes (each run fresh, after the last edit to code, tests and docs):

- `python -m pytest tests/http_api/test_chief_gate.py -q -p no:cacheprovider` -> `97 passed in
  36.91s`, exit 0. `python -m pytest tests/comms_board/test_comms_write_perm.py -q -p
  no:cacheprovider` -> `33 passed in 8.68s`, exit 0. The whole chief set, the mirror tests and the
  new predicate tests, `tests/http_api/test_chief_gate*.py tests/comms_board/test_board_mirror*.py
  tests/storage_paths/test_scope_names_flow_skill.py` -> `1464 passed in 372.97s`.
- Test first: at `acf32ae` (its three test files, `test_chief_gate_flow_skill.py`,
  `test_chief_gate_artifact_section.py` and `test_chief_gate_strict_keys.py`, 63 tests) against the
  source as it was at `7521392`, re-run today in a worktree: `56 failed, 7 passed`. The 7 that pass
  are the "still works" cases (a packaged flow loads, a packaged skill composes, a chief names a
  packaged skill, a chief reads its own project's file by id, a caller with no root still reads by
  id, the keys a chief flow sends pass the gate, and the goal run still makes the folder of a
  packaged flow). With the
  fix all 63 pass.
- The measurement, `test_chief_gate_audit.py` (6 tests, about 35 s): it sent the hostile values to
  every key of every route of the table (and every variable of its URL) and counted the answers
  with a temporary print that I removed: **3,830 requests as an operator chief** (1,938 refused by
  the gate, 1,424 answered 200, 190 answered 400, 235 answered 404, 23 answered 500, 15 answered
  308, 5 answered 403 by the route), **2,535 as a planner** (1,531 refused by the gate, 735 answered
  200, 20 answered 500) and **2,535 as a status chief** (2,107 refused by the gate, 248 answered 200,
  16 answered 500). The audit saw 10,250, 5,102 and 2,997 file system calls inside the chief's own
  project, and **none outside it** in any tier. The 500s are the hostile numeric values and the
  over-long folder name (Shortcuts); none touched a file outside the project.
- Mutation checks (each failing the named tests; the scripts restored every file, and the sha256 of
  every changed and new file under `src/`, `tests/` and `scripts/` is the same before and after):
  `_load_flow` reads any string (1 failed); `_skill_file` reads any string (2); `_run_team` makes
  the folder before it checks the flow and `_flow_kind` trusts any name (8); the gate lets a flow or
  a skill that is a path through (2); the gate lets any key through (29 of 30 in
  `test_chief_gate_strict_keys.py`); the by-id section reads any stored path (5); the section route
  does not pass the root it was given (5); a relative root is a project root to the mirror (5);
  `is_flow_name` accepts anything (21); `is_skill_name` accepts anything (18); `resolves_inside`
  is always true (2); a key left off its entry (`mode` of `/comms/search`) (1, in the static keys
  test); a `not_for_chief` key forgotten (`system_prompt`) (1). The audit itself, `-k operator`:
  project rules off -> **229 touches outside the project**; project rules and the unsafe-topic check
  off -> 245; key list and the `flow` and `skill` name checks off -> 16 (`open` of
  `<other project>.md` through `skill`); stored-path containment off -> 35 (`open` of another
  project's `PLAN.md` through the by-id section); **only the key list off -> passes**, which is the
  point of holding each path twice: the sinks hold alone.
- Test command from `commands.md` -> `2736 passed, 2 skipped in 690.45s (0:11:30)`, exit 0 (the 2
  skips are not mine). `tests/consistency tests/local_operator tests/hq_copilot tests/storage_paths
  tests/dag_goals tests/fsm_flows tests/install_skills` (the last three read the code I changed:
  `_load_flow`, `compose_resources`, `_run_team`) -> `1642 passed, 11 skipped in 298.61s`, exit 0
  (the skips are not in my files: `-rs` over the two small test files I edited after this run,
  `test_scope_names_flow_skill.py` and `test_board_mirror_relative_root.py`, shows none, and they
  were re-run after the last edit: `70 passed`).
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (616 files
  unchanged), `mypy` (`Success: no issues found in 330 source files`), `check_file_size.py` (`1026
  source files checked; 18 known over 400 lines, none new, none grown`: `hydrate.py` 388 and its
  baseline line is gone, `goal_executor.py` 492 = its baseline, `chief_field_calls.py` 182,
  `chief_field_reads.py` 181, `chief_field_types.py` 183, `chief_fields.py` 28, `chief_keys.py` 55,
  `chief_gate.py` 144, `chief_project.py` 205, `scope_names.py` 77, `chief_audit_world.py` 379
  lines), `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0
  broken`), `bandit -q -r src/ -ll -x src/pathly_data/` (no SQL added), `check_adapters.py`,
  `check_entry_points.py`. Smoke and `python -m build --wheel` exit 0. No `# noqa`, `# nosec`,
  `type: ignore` or skipped test added (grepped over the diff and the untracked files; I had
  written one `pytest.skip` as a guard for a platform without symlinks, which the floor scan counts
  as a skipped test, and removed it: the other symlink tests in the repo call `symlink_to` bare).


**Review fixes (round 6)** (quality review; the round starts at `dfead50`, work from `509e381`.
Test-only commit first: `509e381`, run red before any source change: `246 failed, 257 passed` over its nine files (`test_chief_gate_separators.py` 101 of 122, `test_scope_names_host.py` 62 of 62, `test_chief_gate_keys.py` 68 of 90, `test_code_context_cypher.py` 7 of 8, `test_chief_gate.py` 3, `test_chief_gate_project_scope.py` 1, `test_chief_gate_files.py` 1 (that one in the second test-only commit `fc2b66e`) and the audit 3), re-run today in a worktree of `fc2b66e` against the source as it was at `dfead50`. The tests that pass there are the "still works" cases, and the ones for findings 3, 4 and 6, which change what the tests send and what the lists say, not the source. The project owner
approved fixing all eight. The cause of findings 1 and 2 is one: the gate compared the chief's root
with the request's after turning `\` into `/` on every host, and the audit never sent it the
spellings the gate accepted, so the gate and the sinks could disagree about a directory and nothing
checked. So the gate now reads a spelling the way the host that opens it does, one place says how,
and the audit sends the accepted spellings everywhere a file can be reached.)

1. *major, the gate read a backslash as a separator on POSIX.* Reproduced as the finding says
   (red: `test_chief_gate_separators.py`, which sends the spellings through nine routes on this
   POSIX host and finds `proj-a\/pathly/...` and `server/\tmp\...` made by the decompose, goal-run
   and project-decompose routes, and `open proj-a\` and `open server/<padded path>` by
   `/code/query`; and the audit, 89 touches as an operator). The cause is the principle, not the
   spelling: `chief_project.is_own` and `_under` compared after `normalise_project_root` turned
   `\` into `/`, but the views use the request's string as it is (`os.path.join`, `os.makedirs`, a
   git working directory), and on a POSIX host `/work/proj\` is a sibling folder and `\work\proj` a
   path under the server's working directory. Fixed through one host-aware place, `scope_names.py`:
   - `host_is_windows()` (`os.name == "nt"`), the one switch; a test patches it;
   - `root_spelling(value)`: the one spelling of a root, trailing slashes dropped and nothing else
     changed; on Windows `\` reads as `/`; on any other host a value with a backslash (or a NUL, or
     empty, or not a string) has no spelling, so it is never the chief's own;
   - `lies_under(path, root, anchored)`: the file test, with the same host reading (a path with a
     backslash on a POSIX host is refused), `..` collapsed, a relative path read against the root
     only when `anchored` (`target`), and a drive-prefixed string absolute on every host.
   `chief_project` uses them (`own = root_spelling(session root)`, `is_own`, `_foreign_file`), and
   the `_normalise` and `_under` it had are gone. The property the gate relies on is tested, not
   argued: `tests/storage_paths/test_scope_names_host.py` makes the folder and asks `os.path.samefile`
   of every string the gate takes for its root (`test_two_spellings_with_one_key_name_one_folder`),
   and tables for both hosts. A trailing slash (any number) still passes and names the same
   directory; a `.` segment, doubled slashes inside the path and a leading space are refused (they
   may be the same directory, but the gate does not rely on it).
   **A test I changed, as the finding asked:** `test_the_chiefs_own_project_passes_however_it_is_
   spelled` (and its twin `test_a_project_board_post_to_its_own_scope_passes`) now run for both
   hosts: the "backslashes" spelling is refused (`_gated`) on a POSIX host, which is the point of
   the fix, and still passes under the patched Windows host; the other spellings pass on both.
   `test_chief_gate_keys.py` runs its roots under a patched POSIX host, so its backslash cases
   mean the same on any machine the suite runs on.
2. *major, the audit never sent the accepted spellings, and the doc said it did.* Reproduced (the
   audit, 89 touches as an operator, was red for the spellings of finding 1 and for one more sink
   below). The audit now sends the **whole** list at every tier to every key of a file kind (root,
   scope, segment, path, ref, flow, skill) and to every URL variable: the old hostile values, a
   relative climbing path, and the spellings of the chief's own root and file that a gate might take
   for the chief's own (trailing and doubled trailing slash, a dot segment at the end and in the
   middle, doubled slashes, a backslash at the end, backslashes for every slash, mixed separators, a
   climb with backslashes, padded). "What was measured" in the "Chief gate" section is rewritten
   to say that, and the sentence that nothing falls in the server's working directory is now true
   for every spelling in the list: the operator, planner and status runs all pass
   (7,097 requests at each tier; counts in the proof below). The new baselines would have taken `chief_audit_world.py` past
   400 lines; the POST baselines moved to `chief_audit_calls.py` and the GET ones to
   `chief_audit_reads.py`, the fixture to `chief_audit_sandbox.py`.
   **A sink the new baseline found, not named in the findings:** with the cli code backend canned
   (`codebase-memory-mcp` answers from a table, so `/code/query` no longer stops at "backend none"),
   `CliProvider._file_hash` opened a relative target against the server's working directory
   (`open <server>/src/x.py`) for any `/code/query` with a relative `target`. It now takes the
   project root the call names (`_file_section(..., project_root)`, passed by `build_block`) and
   reads a relative file under it. Pinned by `test_a_relative_target_is_hashed_under_the_project_not_
   the_working_directory`; the audit fails without it (mutation below).
3. *minor, plain keys had no `../..` and nothing checked that a key's kind fits its sink.* Added
   `relative climbing` (`../..`) to `PLAIN_VALUES`. The kind check is a static test,
   `tests/http_api/test_chief_gate_kinds.py` (with `keys_joined_into_paths` in `chief_walk_support.py`,
   a taint walk inside one function): a request key that a view or a `blueprints/` helper passes,
   directly or through the names it is assigned to, to a call that makes or opens a path must have a
   file kind or be listed in `HELD_BY_THE_VIEW` with what holds it. It found three plain keys that
   are joined into a path: `board` of `POST /comms/run`, `adapter` of `GET /ops/export/skills`,
   `topic` of `GET /status`; each is held by the view (a fixed list or `_safe_topic` and a
   containment check), and a second test fails when a held key stops being joined, so the list
   cannot go stale. 5 small tests pin the detector on source it must understand. **Its gap, stated
   in the test and the doc:** it does not follow a key into another function (`start_run(flow=...)`
   ends in `_load_flow`), does not know a path call that is not in its list, and cannot say a file
   kind is the *right* one; the audit is the only check of those.
4. *minor, `max_cost_usd` on `POST /runs`.* Added `("/runs", "max_cost_usd")` to
   `WAITS_FOR_A_TICKET` and to the "Not here yet" paragraph, with the reason: no view reads the key
   on `POST /runs` today (`handle_retry` and the `/runner/*` routes do), so the entry does not
   list it and a chief that sends it is told the key is not listed. Ticket 15 lists it with the
   code that reads it and deletes the line (a test fails until it does). I did not edit ticket 15.
5. *minor, feature boards keyed by name.* Nothing to change, as the review says.
6. *minor, early-stopping baselines.* Each now reaches its sink, asserted by `REACHES` in
   `test_chief_gate_audit.py` (`test_the_requests_the_audit_starts_from_are_valid_ones`): a stop with
   a run held (`stopped: true` on `/runs/<id>/stop`, `/comms/goals/stop`, `/comms/run/stop`,
   `/comms/tasks/stop`), a supersede of a decision of the same board (`ok: true`), an answer with a
   question open (`status: accepted`), and `/code/query` through the canned `cli` backend. Twenty
   baselines in all. **Listed as not covered**, because the audit's request stops before the sink:
   `reroute` and `retry` of `/runs/<run_id>/<action>` (reroute sets an attribute of a registered run;
   retry starts a run whose loop the audit replaces) and the codeintel, lsp and both backends of
   `/code/query` (they need an external tool). Said in "What was measured".
7. *minor, the Cypher literal.* Reproduced (red: `test_code_context_cypher.py`, all 5 quote cases:
   `a" OR 1=1 /x` ends the literal and adds a condition). `runner/code_context_cli.py::
   _cypher_literal` escapes a backslash and a quote, and `_file_section` puts the tail through it.
   (The tail has had its backslashes made slashes since before, so only the quote changes a query.)
   The test reads the literal as a Cypher reader does and checks that it closes at the real closing
   quote and that the rest of the query is the same text as before; an ordinary target gives the
   same query as before.
8. *minor, docs and ticket 17.* "For later tickets" (below) and the "Not here yet" paragraph of the
   "Chief gate" section now say what ticket 17's `pathly api` texts must teach: the `project_root`
   field, spelled as the session's (no backslash on a POSIX host), the per-route key lists, that a
   relative `artifact_path` post is refused, and that a symbol `target` like `a:b` is read as a
   drive path and refused. The "A file" bullet says the last two as well.

Tests I edited, not only added: the two backslash tests above; `test_chief_gate_audit.py` (the
value lists, `REACHES`, a grouped report, the fixture moved out); `chief_audit_world.py` (baselines
moved to two new files); `test_chief_gate_keys.py` (`_posix_host`, `WAITS_FOR_A_TICKET`, backslashed
roots in the hostile lists, two new tests). No assertion was loosened and no test is skipped.

Proof after the fixes (each run fresh, after the last edit to code, tests and docs):

- Test first: `509e381` and `fc2b66e` (two test-only commits; the second is `test_chief_gate_files.py`,
  where `test_a_code_query_target_inside_the_project_passes` listed a backslash path as the
  project's own: the Test command found it after the first commit, so it is host-aware now, in a
  test-only commit of its own before the fix). Against the source as it was at `dfead50`, in a
  worktree: `246 failed, 257 passed in 292.86s` over the nine files listed above.
- The two Done when commands: `python -m pytest tests/http_api/test_chief_gate.py -q -p
  no:cacheprovider` -> `106 passed in 31.12s`, exit 0; `python -m pytest
  tests/comms_board/test_comms_write_perm.py -q -p no:cacheprovider` -> `33 passed in 8.09s`,
  exit 0.
- The measurement, `test_chief_gate_audit.py` (6 tests, about 50 s), counted with a temporary
  print that I removed (the file is as committed): **7,097 requests at each tier.** Operator: 3,936
  refused by the gate, 2,235 answered 200, 431 answered 404, 333 answered 400, 90 answered 409,
  42 answered 308, 29 answered 500, 1 answered 405; 16,237 file system calls seen inside the
  chief's own project and **0 outside it**. Planner: 5,032 refused, 1,392 answered 200, 361 answered
  404, 243 answered 400, 42 answered 308, 26 answered 500, 1 answered 405; 11,874 seen, 0 outside.
  Status: 5,992 refused, 555 answered 200, 347 answered 404, 138 answered 400, 42 answered 308, 22
  answered 500, 1 answered 405; 8,364 seen, 0 outside. (Round 6 sent 3,830, 2,535 and 2,535.) The
  500s are the hostile numeric values and the over-long folder name (Shortcuts); none touched a
  file outside the project.
- Mutation checks (each failing the named tests; every file restored afterwards and compared with a
  copy): the host switch read as "a backslash always separates" (the old behaviour) -> the audit
  fails at all three tiers (**28 touches** as an operator, 24 as a planner, 6 as a status chief) and
  117 tests of the separators, gate, scope, files, keys and `scope_names_host` files fail; the code
  backend's file read left to the working directory -> the audit fails at all three tiers (**55
  touches** each) and `test_a_relative_target_is_hashed_under_the_project_not_the_working_
  directory` fails; the Cypher literal not escaped -> 5 of 8 in `test_code_context_cypher.py`; the
  file check turning a backslash into a slash before `lies_under` -> 6 failures in the files,
  separators and keys tests.
- Test command from `commands.md` -> `2880 passed, 2 skipped in 830.75s (0:13:50)`, exit 0 (the 2
  skips are skips that the existing tests of those four folders make when FTS5, sqlite-vec or a
  platform is missing; I added none). The domains that read what I changed besides it, `tests/consistency tests/local_operator
  tests/hq_copilot tests/storage_paths tests/dag_goals tests/fsm_flows tests/install_skills
  tests/code_intel` -> `1759 passed, 12 skipped in 305.46s`, exit 0 (`-rs` shows the skips: a flow
  that has no designer stage, a Windows-only test, two "files not found in this environment", and
  `test_windows_backslash_path_normalized`, which was skipped before).
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (623 files
  unchanged), `mypy` (`Success: no issues found in 330 source files`), `check_file_size.py` (`1026
  source files checked; 18 known over 400 lines, none new, none grown`: `scope_names.py` 139,
  `chief_project.py` 186, `code_context_cli.py` 201, `chief_audit_world.py` 250 and its new
  neighbours `chief_audit_calls.py` 167, `chief_audit_reads.py` 48, `chief_audit_sandbox.py` 115,
  `chief_walk_support.py` 312), `check_no_mirror_reads.py`, `gen_test_index.py --check`,
  `lint-imports` (`1 kept, 0 broken`), `bandit -q -r src/ -ll -x src/pathly_data/` (exit 0, no SQL
  added), `check_adapters.py`, `check_entry_points.py`. Smoke, `python -m build --wheel` and
  `check_version_sync.py` exit 0. No `# noqa`, `# nosec`, `type: ignore`, `pytest.skip`,
  `skipif` or `xfail` added (grepped over `git diff dfead50` of every file but the docs).

**Review fixes (round 7)** (quality review; the round starts at `df853ed`, work from `d5c0a86`.
Test-only commit first: `d5c0a86`, run red before any source change: `83 failed, 69 passed` over
its eight files (`test_code_cache_projects.py` 6 of 11, `test_code_context_cypher.py` 8 of 12,
`test_run_history_wildcards.py` 8 of 16, `test_chief_gate_code_cache.py` 8 of 9,
`test_chief_gate_feature_names.py` 15 of 17, `test_chief_gate_symlinks.py` 37 of 65,
`test_chief_gate_audit.py` 1 of 7, `test_code_context_lsp.py` none), re-run today in a worktree of
`d5c0a86` with `PYTHONPATH` on that worktree's `src`, which holds the source as it was at
`df853ed`. The tests that pass there are the "still works" cases (a second call on the same
project is a cache hit, an edited file is queried again, a symlink that stays inside the project,
a legitimate feature name with a `%`, `_` or backslash in it, the plain keys of the audit) and the
slow audit tests, which pass before and after. The project owner approved fixing all six. The
cause of findings 1 and 3 is one: a cache or a lookup keyed by a name or a relative path alone,
where the same string is a different thing in every project. Findings 4 and 5 are two checks that
trusted a string the file system, or the tool, reads differently from the gate.)

1. *major, the two `/code/query` caches had no project in their key.* Reproduced as the finding
   says (red: project A was served `sym_of_graph-b` with `cached: true` for `src/a.py`, a file
   with the same bytes in both projects, and for the directory `src`, at all three tiers; and
   with one cache cleared between the two calls the other still leaked). Fixed:
   `scope_names.cache_root(project_root)` (the `root_spelling` of the root, so `/p` and `/p/`
   share their entries, else the string as given, so two projects never share one) is the first
   element of both keys. `query._QUERY_CACHE` is `(project root, op, target, hash, backend)` and
   nothing is read from it or stored in it for an empty hash (a directory, a missing file, a
   symbol); `code_context_cli._CLI_CACHE` is `(project root, path, hash)` (it already skipped an
   empty hash). Tests: `test_code_cache_projects.py` (the route and the provider, each alone: same
   bytes and a directory, the empty-hash targets are never cached, a second call on the same
   project is a cache hit, an edit forces a new query, `/p/` shares `/p`) and
   `test_chief_gate_code_cache.py` (the whole path through the gate, the real `cli` provider and a
   graph that names the project it answered for: a human on project B, then a chief of each tier
   on A, for a file and for `src`; a chief that asks twice is cached; each cache alone, the other
   cleared). Two existing tests changed (below).
2. *major, URL variables were on the short list.* Reproduced: a new test asks `_routes` for the
   kind of every URL variable and found 13 (rule, variable) pairs on the short list, the `feature`
   of eight rules, the `artifact_id` of one and the `run_id` of four (the review counted 11). Fixed
   in `_routes`: a variable of the URL is kind `"variable"` whatever its entry says, and `_attack`
   gives every kind but `"plain"` the whole list, so only a key that is free text gets the short
   one. The audit then passed with the whole list on those variables (counts below), as the
   review had found. "What was measured" in the "Chief gate" section and the audit's docstring now
   say exactly which kind gets which list, and what the short list is: `..`, `../..`, a relative
   path that climbs into the other project, the other project's root and a file in it (both
   absolute), a NUL and a 5,000-character name. It has no absolute climbing path, as the review
   noted, and neither the server's or home directory, a UNC or drive spelling, nor an own-root
   spelling; the old sentence and the test's comment said "an absolute climbing path".
3. *minor, `%` and `_` were wildcards in `_SLUG_MATCH`.* Reproduced (red: with one legacy row for
   project B, a planner or operator chief on A posting `board: "feature", scope: "%"` made the
   mirror create `<B>/pathly/features/%/BOARD.json`; `resolve_project_root(conn, "feature", "%")`
   was B; the same for `d%`, `%o`, `d_mo`, `_emo`, `dem_` and `%%`). Fixed in `run_history.py`: the
   constant is one static literal with an `ESCAPE '\'` clause, and the three readers bind
   `_like_literal(feature)` (`%`, `_` and the backslash escaped in Python). A name with one of
   those characters still matches itself (`100%`, `my_feature`, a backslash) and no other row
   (`1000`, `myXfeature`): `test_run_history_wildcards.py` has all three directions; the route test
   is `test_chief_gate_feature_names.py`. The doc sentence in "Not held" no longer says "whichever
   project ran that name": it says how the lookup matches (the newest row whose `feature` is the
   name, or a legacy path ending in `/<name>`, SQLite `LIKE`, so ASCII case is ignored, and the
   three characters literal). `bandit` finds no new B608: the f-string is the one that was there,
   with its `# nosec`, and no `# nosec` was added.
4. *minor, a symlink in the project passed the text check.* Reproduced with real symlinks under
   `tmp_path` (red: a link to project B, to a folder of B, to a file of B and `link/../x`, each
   posted as an `artifact_path` by a planner and an operator and sent as a `target` at all three
   tiers, passed the gate). Fixed in `chief_project._opens_inside`, called after `lies_under` for
   `paths` (`target`) and `abs_paths` (`artifact_path`): the value as written (a relative one
   under the root, read through `scope_names.host_path`) is resolved with `hydrate_helpers.
   inside_root`, the check the by-id section read already makes, and must lie under the real root;
   the answer is the same 403 `a chief names only files inside its project`, and any error from the
   file system refuses. `link/../x` is judged where the file system puts it (beside the link's
   target), not where the collapsed text does. A link that stays inside the project, a path that
   does not exist yet, and a project root that is itself a symlink (both sides are resolved) still
   pass. The doc says, in "A file", what text containment alone cannot see and where it still
   decides alone (the project root and a path-like scope, accepted only when they spell the
   session's root), and what the real-path check cannot see (a link made after the check, a hard
   link, a mount, and what the code backend opens by its own rules).
5. *minor, the Cypher escape was never checked against the real tool.* `codebase-memory-mcp` is
   still not available here. `_cypher_literal` now returns None for a text with a double quote and
   `_file_section` makes no query for it (an empty section); the backslash is still doubled. The
   test that read the literal as a Cypher reader does is replaced by `test_a_target_with_a_quote_
   is_not_queried_at_all` (six targets, no query sent, an empty section) and a direct test of
   `_cypher_literal`: a stricter assertion than before. Shortcuts says the real tool was not
   available.
6. *minor, the stored root.* Docs only: "For later tickets" (below) and the "Not here yet"
   paragraph of the "Chief gate" section say that ticket 17 must hand the chief the stored
   `project_root` string, since a chief that reads its root with `pwd` can read another spelling
   of the same directory and would be refused on every call that names its project. I did not edit
   ticket 17.

Tests I edited, not only added: `test_code_context_cypher.py` (the quote test is the stricter one
above, its `_literal` reader and two constants are gone, and the key in
`test_a_relative_target_is_hashed_under_the_project_not_the_working_directory` is now `(project
root, path, hash)`), `test_code_context_lsp.py::test_null_result_not_cached` (its target `x.py`
did not exist and was cached under the hash `""`; it is a real file in `tmp_path` now, and its
assertions are the same: the first null is not cached, the second answer is, the third is served
from the cache) and `test_chief_gate_audit.py` (`_routes`, the docstrings, the comment on
`PLAIN_VALUES`, and the new URL-variable test). No assertion was loosened and no test is skipped.

Proof after the fixes (each run fresh, after the last edit to code and tests; the docs were edited
while the full run was going, and the Done when commands were run again after that):

- Test first: `d5c0a86`, `83 failed, 69 passed` (above).
- The two Done when commands: `python -m pytest tests/http_api/test_chief_gate.py -q -p
  no:cacheprovider` -> `106 passed in 28.38s`, exit 0; `python -m pytest
  tests/comms_board/test_comms_write_perm.py -q -p no:cacheprovider` -> `33 passed in 7.45s`,
  exit 0.
- The measurement, `test_chief_gate_audit.py` (7 tests, `7 passed in 52.49s`), counted with a
  scratch test that I removed afterwards: **7,477 requests at each tier** (7,097 in round 7).
  Operator: 3,936 refused by the gate, 2,303 answered 200, 724 answered 404, 333 answered 400, 90
  answered 409, 61 answered 308, 29 answered 500, 1 answered 405; 16,667 file system calls seen
  inside the chief's own project and **0 outside it**. Planner: 5,064 refused, 1,428 answered 200,
  654 answered 404, 243 answered 400, 61 answered 308, 26 answered 500, 1 answered 405; 12,314
  seen, 0 outside. Status: 6,024 refused, 591 answered 200, 640 answered 404, 138 answered 400, 61
  answered 308, 22 answered 500, 1 answered 405; 8,799 seen, 0 outside. (The extra 380 requests and
  the extra 404s and 308s are the whole list sent to the URL variables.)
- Mutation checks (each failing the named tests; the file restored afterwards and compared with a
  copy): the gateway key without the project -> 1 failure at the first (`-x`); both empty-hash
  guards of the gateway off -> 3 failed, 17 passed (each guard alone is covered by the other,
  so the two were switched off together); the provider key without the project -> `test_the_cli_
  cache_is_per_project`; a quote escaped instead of refused -> the quote tests of
  `test_code_context_cypher.py`; `_like_literal` an identity -> `test_run_history_wildcards.py`;
  the `ESCAPE` clause removed -> the same file; the real-path check always true -> the symlink
  tests; the text collapsed before the real path -> the `sublink/../x.md` cases; `host_path` not
  applied -> the Windows-host cases of the files and symlink tests; the URL variables back on the
  short list -> `test_every_url_variable_gets_the_whole_list`.
- Test command from `commands.md` -> `2988 passed, 2 skipped in 816.22s (0:13:36)`, exit 0 (the 2
  skips are skips that the existing tests of those four folders make; I added none). The domains
  that read what I changed besides it, `tests/consistency tests/local_operator tests/hq_copilot
  tests/storage_paths tests/dag_goals tests/fsm_flows tests/install_skills tests/code_intel` ->
  `1772 passed, 12 skipped in 269.96s`, exit 0 (`-rs`: eight flow cases without a designer stage
  or the routing, a Windows-only test, two "files not found in this environment", and
  `test_windows_backslash_path_normalized`, all as in round 7).
- Lint chain from `commands.md`, piece by piece, all exit 0: `black --check src/ tests/` (628 files
  unchanged), `mypy` (`Success: no issues found in 330 source files`), `check_file_size.py` (`1026
  source files checked; 18 known over 400 lines, none new, none grown`: `query.py` 399,
  `scope_names.py` 155, `code_context_cli.py` 213, `run_history.py` 124, `chief_project.py` 215),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (`1 kept, 0 broken`),
  `bandit -q -r src/ -ll -x src/pathly_data/` (exit 0), `check_adapters.py`,
  `check_entry_points.py`. Smoke, `python -m build --wheel` and `check_version_sync.py` exit 0. No
  `# noqa`, `# nosec`, `type: ignore`, `pytest.skip`, `skipif` or `xfail` added (grepped over
  `git diff df853ed` of every file but the docs).

**For later tickets**

- Ticket 09: no change to the table is needed for `/chief/human-messages`. Its hook posts with no
  run token, so the gate does not see it.
- Ticket 10: call the cite rule from `chief_gate._refusal()` after the action check (it runs once
  per reading of the body, so a cite rule that reads the body reads the one it is given). The `answer` action is
  already assigned to `/runner/agent-answer`, `/comms/answer` and to `/comms/acknowledge` on a
  human escalation (classed in `chief_routes._acknowledge_action` through the `is_human_escalation`
  predicate `chief_gate._human_escalation_check(conn)` builds), so the rule has one place to hook.
  `chief_gate.py` is 144 lines, so a new `chief_cite.py` fits as the ticket plans. Round 6: the
  `cite` key is already listed (kind `id`) on the entries of the three answer routes, so a chief
  may send it; `WAITS_FOR_A_TICKET` in `test_chief_gate_keys.py` names those three so a listed key
  that no view reads is still caught. When 10 starts to read it, delete those three tuples.
- Ticket 12: `/comms/directives` is already mapped to `decide`, `chief` is already a project
  writer, and `PLANNED` (now in `tests/http_api/chief_gate_support.py`) may drop its entry once the
  route exists. The living-doc
  "Chief gate" section says the route arrives with ticket 12; fix that sentence then. The route
  also needs an entry in `chief_fields.ROUTE_FIELDS` (the fields it reads as a project root, board
  scope or file; `Fields(roots=("project_root",), names_root=True, ...)` if it falls back to the
  server's directory): without one the gate answers 403 `the gate has no project entry for this
  route` and `test_every_route_a_chief_can_reach_says_which_fields_it_reads_as_a_project` (in
  `test_chief_gate_tables.py`) fails. **Round 6: the entry is also the complete list of the body
  keys a chief may send.** Put it in `chief_field_calls.py` (182 lines; `CALL_FIELDS`) with a
  `keys={name: kind}` for every key the route reads (kinds in `chief_field_types.py`: text,
  number, flag, enum, name, id, and the `scopes`, `paths`, `segments`, `flows` and `skills`
  attributes for a key that can reach a file or a folder), and the keys it reads that no chief flow needs in
  `not_for_chief`. A key the entry does not list is a 403 to the chief, and a key the route reads
  that the entry neither lists nor puts in `not_for_chief` fails `test_chief_gate_keys.py`. Also
  give the route a baseline request in `chief_audit_world.py` (`_POST`), or
  `test_chief_gate_audit.py` sends it only the project root and stops at the route's first check;
  that file is 379 lines, so a baseline that takes it past 400 means moving the GET ones to a new
  file. A new test for the chief gate goes in the
  `test_chief_gate_*.py` file of its concern; the shared fixtures are in `chief_gate_support.py`.
- Ticket 14: add `chief_bind.target_in_project(...)` after the action check in
  `chief_gate._refusal()` (`request.view_args` and the body are already in hand there);
  `chief_project` covers the project a request names (`project_root`, a project board's `scope`,
  a code query's scope, the decompose override), not a run or message id. The `unbound` entries of
  `chief_fields.ROUTE_FIELDS` are the list of what is left: take the ids ticket 14 binds off it
  as they land, and update the "Not here yet" and "Not bound" bullets of the "Chief gate" section.
  Ticket 14's first paragraph ("binds only when `project_root` is named") is stale: since round 2 a
  chief must name its root on every run, decompose, `/code/query` and `/db/*` call, and since round
  3 on `POST /runs/<run_id>/retry` (the only verb that starts an agent in a directory the body
  names), so ticket 14 binds the **run id** and needs no root rule.
  **Id-addressed calls that no ticket owns** (the exact list; ticket 14 as written covers none of
  them, and an operator chief on project A can start a goal or a task of project B in A's
  directory): `goal_id` on `/comms/goals/run`, `/comms/goals/stop` and `/comms/goals/decompose`, and
  on `/runs` with `kind` `goal`; the task `message_id` on `/comms/tasks/run` and
  `/comms/tasks/stop`. Add them to ticket 14 or give them a ticket. Also unowned and unbound, but
  reads: `GET /runs/<run_id>`, `/runner/status`, `/status?topic=`, `/db/runs/<id>/cost`,
  `/comms/artifacts/<id>/section`, `GET /comms/artifacts?message_id=` and
  `/comms/goals/refs-coverage`. The feature-board "context pull" row (Shortcuts) and the sentinel
  rows of the artifact-section read ("Reads are not all pure") are the other unbound writes.
  Round 6: the ids are listed as keys of kind `id`, so a chief may send them whatever 14 does;
  binding one is a check in `chief_bind`, plus taking it off `unbound`, not a change of kind. A
  new key 14 reads goes on the entry's list first (`test_chief_gate_keys.py` fails otherwise).
  Round 5: `chief_bind` and `ROUTE_FIELDS` must stay consistent. When ticket 14 binds an id, take
  it off that entry's `unbound` in the same change (and off the "Not bound" list in the living
  doc), and if the id also reaches a path (a `goal_id` whose row's `scope` `goal_decomposer` joins
  into a folder, see Shortcuts) check it with `scope_names.is_segment`, since nothing else guards
  that join. Ticket 14's **opening sentence** is stale as well as its first paragraph: it says
  ticket 08 binds the chief only when the body or query string names `project_root`, but 08 also
  binds board scopes (a path on every board, and a folder name off the project board), files and
  the `slug` of a goal post, all through `ROUTE_FIELDS`. A builder of 14 should read the "Chief
  gate" section, not that sentence. I did not edit ticket 14.
- Ticket 15: `POST /runs` is the `("/runs", "POST")` entry; ticket 15's ceiling can key on it. The
  `GET /chief/session` route is already a `read` for the chief, so its new fields reach it.
- Ticket 17: the chief's prompt must tell it to post with `"from": "chief"` and to name its
  project by the exact spelling it was opened with (`project_root` is compared textually, after
  `normalise_project_root`). It must also say: send `project_root` in the JSON body (a query string
  does not count on a POST) of every run, goal, decompose and `/code/query` call, and in the query
  string of the `/db/*`, `/status` and `/comms/artifacts/section` reads (a call without it is
  403), in the body of `POST /runs/<run_id>/retry`, and in the query string of
  `/telemetry/trends` unless it names a feature; name the `feature` of
  `/comms/features/decompose` and the `scope` of a `/comms/run` on a feature or global board as one
  plain folder name (no `/`, `\`, `:` or `..`); the same holds since round 5 for the `scope` or
  `feature` of every other call on a board that is not `project` (a path there must be exactly the
  chief's own root, and anything else is one folder name), and for the `slug` of a goal post
  (one folder name, or leave it out); give the project root as `scope` on a
  project-board post, search, read or run (a missing scope is read as `feature`, which is a
  feature board, and a feature name given for a project board is 403); use a parenthesized scope such as `(interactive)` on `/code/query` (a feature name
  is 403) and a `target` inside the project; give `artifact_path` as an absolute path inside the
  project. `pathly api` may fill `project_root` in from the session itself. **Round 6: send only
  listed keys.** A body key (a query key on a GET) that the route's `ROUTE_FIELDS` entry does not
  list is a 403 naming it, so the prompt must name the keys per route: they are the `keys`,
  `scopes`, `paths` and so on of the entries in `chief_field_calls.py` and `chief_field_reads.py`
  (`Fields.allowed(rule)` gives the list; 221 keys over 84 routes), not whatever the route's
  view happens to read. In particular: `prompt_override` goes only to `/comms/goals/decompose`
  (the other two decompose routes refuse it) and needs the operator tier; `flow` goes to
  `POST /runs` (and the run verbs) and is one flow name, never a path, and is not a key of
  `/comms/goals/run`; `skill` of `/comms/run` is `name` or `category/name`; `ability_ids`,
  `system_prompt` and `interactive` of `/comms/run` are not for a chief; `GET
  /comms/artifacts/<id>/section` needs the chief's own `project_root`. A project board must be
  named by its absolute root: a relative root such as `proj/x` is stored and served but no longer
  exported to disk.
- Ticket 12 (round 7): the baseline request for `/comms/directives` goes in `chief_audit_calls.py`
  (`POST_VARIANTS`, 167 lines) now, not `chief_audit_world.py`; the GET baselines are in
  `chief_audit_reads.py`. Add the route to `REACHES` in `test_chief_gate_audit.py` with the answer
  that says the work was done, so a baseline that stops early is caught.
- Ticket 15 (round 7): `max_cost_usd` on `POST /runs` is a key no view reads there today (only
  `POST /runs/<run_id>/retry` and the `/runner/*` routes do), and the `("/runs", "POST")` entry does
  not list it, so a chief that sends it is told the key is not listed. Ticket 15's text says it
  reads the key from `POST /runs`: list it in the entry (`chief_field_calls.py`, kind `NUMBER`) with
  the code that reads it, and delete `("/runs", "max_cost_usd")` from `WAITS_FOR_A_TICKET` in
  `test_chief_gate_keys.py`, which fails until you do. I did not edit ticket 15.
- Ticket 17 (round 7): this corrects the bullet above, which says `project_root` is compared
  after `normalise_project_root`: it is compared by `scope_names.root_spelling` (trailing slashes
  dropped, nothing else), and on a POSIX host a value with a backslash is refused whatever it
  spells. The `pathly api` texts must teach: name `project_root` exactly as the session has it, on
  the routes that need it; send only the keys the route's entry lists (`Fields.allowed(rule)`, the
  403 names a key that is not listed); post an artifact with an **absolute** `artifact_path` inside
  the project (a relative one is refused); and give `/code/query` a **file path** as `target`, since
  a symbol like `a:b` is read as a drive path and refused. The living doc says the same under "Not
  here yet".
- Ticket 17 (round 8): **hand the chief the STORED project root string**, as an environment
  variable or in the prompt text, and tell it to send exactly that. The gate compares `project_root`
  with the string `open_chief` stored (`chief_sessions.project_root`: forward slashes, no trailing
  slash) by `scope_names.root_spelling`, and refuses every other spelling of the same directory
  (that is the rule from round 7: a spelling it does not rewrite is one it cannot get wrong). A
  chief that finds its root with `pwd` can read another string: a symlinked parent (macOS `/var`
  for `/private/var`, a project under a linked home), a different letter case on Windows, a
  backslash form. It would then be refused (403 `that is not this chief's project`) on every call
  that names its project, which is nearly every call. `pathly api` may fill `project_root` in from
  that variable itself. The living doc says the same under "Not here yet". I did not edit ticket 17.
- Ticket 17 / any later ticket that reads code (round 8): `/code/query` answers are cached per
  project and per file with a content hash (a symbol or a directory target is never cached), and a
  `target` whose last two segments hold a double quote gets no block. A chief's `target` must be a
  path inside the project once symlinks are followed: a link that points out of the project is
  refused.
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

## Review findings (round 3, quality review)

QUALITY

Range reviewed: 570a6ee..ffe326b. ffe326b is the ticket's newest commit, so no later commits were left out. I read the ticket as it stood at 570a6ee plus the `## Review findings` sections of rounds 1 and 2 from the working copy, and the diff (ticket folder excluded). Both Done when commands pass: `tests/http_api/test_chief_gate.py` 483 passed, `tests/comms_board/test_comms_write_perm.py` 33 passed. black, mypy, lint-imports, check_file_size and gen_test_index --check are clean. The repo working tree is clean. My probes are in the scratchpad `rv3/` (test_p1.py, test_p2.py, test_p3.py, test_p4.py, test_p5.py, test_p6.py, list_routes.py, srcscan.py, conftest.py).

Disclosure: a grep I ran over the tasks folder for "code/query" printed snippets of the ticket's `## Answer` (ticket lines about the `/code/query` marker rule, and "Tests I edited"). Before that I had already found the `/runs/<id>/retry` hole and decided on FAIL. The Answer text did not change any finding.

How I checked the table: I enumerated every `(rule, method)` the chief can reach (84, all have an entry, none stale). For each one I read the view and the helpers it calls, and compared the fields it really reads, its fallbacks, and body versus query string. I also scanned every view's source: no listed GET view reads a body and no listed POST view reads `request.args`. Most entries are true. The ones below are not.

1. major src/pathly_orchestrator/http_server/chief_fields.py line 161 (`/runs/<run_id>/<action>`): `POST /runs/<id>/retry` falls back to the server's directory when `project_root` is empty, and the table does not mirror that.
   - `blueprints/control/_helpers.py::handle_retry` checks that the key `project_root` is present, not its value. It then calls `start_run(project_root=body["project_root"])`. `Path("")` and `project_root or None` resolve to the server's working directory.
   - The entry is `Fields(roots=_ROOT, unbound=("run_id",))`, so the gate only checks a foreign root. `_foreign_root` skips falsy values, and `names_root` is off for this rule.
   - Repro (test_p1.py): an operator chief on A, with a finished registry run, sends `POST /runs/run-own-1/retry` with `{"flow":"team","project_root":"","max_iterations":3,"max_cost_usd":1}`. The gate lets it through and `start_run` receives `""`. The same happens for null, 0, false, [] and {}. The control with project B's root gets the gate's 403.
   - So an operator chief can restart a run in the server's directory, which may be another project, with agents spawned there.
   - The test `test_every_route_that_starts_an_agent_in_a_directory_names_its_root` excludes this rule with the comment "names a run by id (ticket 14)". But `retry` starts an agent in a directory taken from its own body.
   - Fix: make the naming rule verb-aware, so `retry` requires a truthy `project_root` in the body. pause, resume, advance and reroute must stay callable without it. Add tests for ""/null/0 on retry, and shrink the exclusion in that test.
2. major src/pathly_orchestrator/http_server/chief_fields.py line 135 (`/comms/features/decompose`): `feature` is declared `unbound` as a board name, but the route joins it into a filesystem path, so a planner or operator chief can write into another project.
   - `blueprints/comms/features.py::_dispatch_board_run` does `os.makedirs(os.path.join(project_root, "pathly", "features", feature))`. It then passes that string as `storage_path` to `start_board_run`. `_dispatch_consultation` does the same `makedirs`. Neither calls the `_safe_topic` guard that `_resolve_storage_path` uses.
   - Repro (test_p3.py, test_p6.py): a chief on A (planner and operator tier) sends `feature="../../../proj-b/pathly/features/planted"` with `project_root=A` and rigor light, full or consultation. The gate lets it through. The directory is created inside project B. With the real `start_board_run` and the spawn faked, the run is accepted ("started") with `storage_path` pointing into B. The planner agent is told "Your working directory is: <that path>".
   - The table's own contract says a path the route stores or creates "must lie inside the chief's project" (`paths`/`abs_paths`). This route's `feature` is such a path but is listed only as an id.
   - The tripwire test cannot catch it, because `feature` is declared. I checked the other routes that take a topic or scope from the body: `/comms/run`, `/runs` and `/status` are protected by `_safe_topic` or a containment check. A `/comms/run` evaluator probe with a traversal scope got a 500 ValueError (test_p5.py), so that one is not a bypass.
   - Fix, preferably in the route: validate `feature` with the `_safe_topic`/`_is_unsafe_topic` guard before `makedirs` in both dispatchers. In the gate, treat `feature` of this route as a path-segment field that may not contain a separator or `..`. Add a test that plants nothing outside the project.
3. major src/pathly_orchestrator/CLAUDE.md, "Chief gate", bullet "Naming it": the section overclaims.
   - It says a route that falls back to the server's working directory, `PATHLY_PROJECT_ROOT` or every project is refused when it names no root, and it lists the routes. Finding 1 shows `retry` falls back and is not refused. Finding 4 shows `/telemetry/trends` falls back to every project and is not refused.
   - The "Reads are not all pure" bullet says a status chief can cause "three small writes". `GET /skills/prompts` without `kind` calls `migrate_db_presets_to_files`, which writes prompt files and deletes legacy DB rows. That is a fourth.
   - Fix: correct the lists after fixing 1 and 2, or state the exceptions.
4. minor src/pathly_orchestrator/http_server/chief_fields.py lines 260-264 (`/telemetry/trends`) and 203-205 (`/db/stats`): both fallbacks go unmirrored.
   - With a blank `feature` and no `project_root`, `/telemetry/trends` aggregates every project's daily cost (test_p2.py: a status chief on A got B's $12.50 bucket). The note only says "a named feature is summed across every project".
   - `/db/stats` with `project_root` filters cost and tokens, but its `features`, `events` and `invocations` counts are global. The table presents it as project-bound with no fleet-wide note.
   - This is the same exposure class as the accepted `/db/rollup` global block. Add `names_root` for the blank-feature case and say so in the notes, or list both as fleet-wide.
5. minor src/pathly_orchestrator/http_server/chief_fields.py: the `unbound=("feature",)` entries on `/db/features/<feature>/*` and `/api/features/<feature>/*` are misleading. Those queries also filter by the named `project_root`, so the feature is bound there. Only list what is genuinely unbound.
6. minor ownership of id-addressed calls. The task brief says ticket 14 covers ids. Ticket 14 as written covers only `/runs/<id>/stop|<action>`, `/comms/acknowledge|answer|supersede` and `/runner/agent-answer`.
   - Nothing owns `goal_id` on `/comms/goals/run|stop|decompose` and `/runs` kind=goal, or the task `message_id` on `/comms/tasks/run|stop`. An operator chief on A can start a goal or task from project B in A's directory.
   - CLAUDE.md says "no ticket yet", which is accurate. Add these routes to ticket 14 or open a ticket. Ticket 14's first line ("binds only when project_root is named") is also stale now.
7. minor legitimate flows: the new refusals do not break any flow the ticket lists.
   - The planner and operator Done when calls still pass once `project_root` is in the body. The builder edited those tests to add it.
   - Ticket 17's `pathly help` and the built-in style texts must now tell the chief to give `project_root` on run, decompose, `/code/query` and `/db/*` calls, and to use its own root or a `(marker)` as `scope`. The 403 text names the missing field.
   - An `artifact` post with a relative path in its text and no `artifact_path` is refused by design. That is the stricter behaviour.
8. minor tests/http_api/test_chief_gate.py is 2165 lines in one file, and `test_a_view_reads_no_project_ish_field_its_entry_does_not_name` reads only each view's own source, as its docstring admits. Splitting by concern would keep later tickets from growing it. The tripwire misses helper code such as `create_run`, `handle_retry` and `_dispatch_*`, which is exactly where findings 1 and 2 live.

Checked and found true: the `ScopeRead` fallbacks (`scope or feature` including blank, 0 and null) for `/comms/post`, `/comms/search`, `GET /comms`, `/comms/tasks` and `/comms/goals`. The board default and unknown-board handling, which is stricter than the routes. `/comms/artifacts` and `/comms/run/status` taking `scope` only. The `/code/query` scope, marker and target anchoring. The project-decompose `project` override. `artifact_path` and the text-recovered path. `names_root` for `/runs`, `/comms/run`, `/comms/goals/run`, `/comms/tasks/run`, the three decompose routes, `/code/query`, the `/db/*` family, `/status` and `/comms/artifacts/section`. Absent-root behaviour of `/api/*`, `/skills/*`, `/db/agents`, `/runs`, `/comms/permissions`, `/hq/context`, `/comms/scope`, `/chief/session` and `/flows/stage-config`. The "reads no project" entries. The repeated-query-key and whitespace handling, which fails closed.

REVIEW: FAIL

## Review findings (round 4, quality review)

QUALITY

Scope of this review: ticket 08 of chief-agent, round 4. The range is 570a6eef44c62cc658b338f90572d9ab871edb6f..c88f85b. c88f85b is also HEAD and the newest commit touching the ticket, so no later commits were excluded. It covers d3d52b1, 53dc2fa, 45357e6 (test-file split) and c88f85b. I read the ticket as of the base commit plus its Review findings sections, and the diff with the ticket folder excluded. I did not read `## Answer`.

Checks I ran:
- Done-when commands: `test_chief_gate.py` gave 97 passed; the glob gave 651 passed; `test_comms_write_perm.py` gave 33 passed.
- black, mypy, lint-imports, check_file_size and gen_test_index --check were clean.
- `git status` is clean. I changed nothing in the repo.
- Files left behind are outside the repo, in the scratchpad `rv4/`: routes.py, missing.py, split_check.py, old_gate.py, and probe/{conftest.py,test_p1.py..test_p5.py}.

Your items (a) to (d):
- (a) I compared `ROUTE_FIELDS` with the views and the helpers they call, route by route. Most entries are true: fallbacks (`scope or feature`), board defaults and strips, blank/0/null, query vs body, and the `_project_root_param` env fallback. The exceptions are findings 1 and 2 below.
- (b) I checked the "Chief gate" section sentence by sentence. Finding 1 is a doc claim the code does not back. Findings 3 and 4 are minor understatements.
- (c) The new guards do not reject legitimate names. `_is_unsafe_topic` in `blueprints/comms/features.py` and the 4-line guard in `blueprints/comms/runs.py` let nested names, dots, unicode and spaces through. They reject only reserved bare names, `:`, `\`, absolute paths and `..` segments.
- (d) The test split is lossless. An AST comparison of old and new shows the same test names and bodies. Fixtures are shared through `chief_gate_support.py`, and basenames are unique.

1. major src/pathly_orchestrator/CLAUDE.md ("Reads are not all pure"): The section says a status chief "can cause four small writes" and that the context-pull `status` row happens on `GET /comms/artifacts/section?scope=<feature>&trail=x`. The code does more. `GET /comms/artifacts/section` goes through `runner/hydrate.py` and `db/queries/comms_artifacts.py::find_or_create_artifact_by_path`. For a status chief it inserts a sentinel `comms_messages` row (board feature, `scope` as given, from `system`, type `artifact`, text "[legacy artifact] <title>"), a `comms_artifacts` row and a section index. This happens without `trail`, at any feature `scope` the caller names. I confirmed it with probe test_p1.py: the message count went from 0 to 1 for a status-tier chief. The closing claim "none of them can change a decision, a task or a run" stays true, but "four" and the trail-only wording do not. Fix: list it as a fifth write and say it needs no `trail`. Alternatively, make the hydrate path write no sentinel rows when the caller is a read-tier chief.
2. major src/pathly_orchestrator/http_server/chief_fields.py (`("/comms/post","POST")` with `_BOARD_SCOPE`, and `("/runs","POST")` with `_BOARD_SCOPE_ONLY`): A planner or operator chief can post to `board:"feature"` with a path-like or traversal `scope`, for example `/abs/proj-b`, `../../proj-b` or `C:/x`. The table does not bind a feature-board scope and sets no `segment` on this route. The post then reaches `_broadcast_comms` -> `board_mirror.mark_board_dirty_by_scope` -> `board_from_scope` -> `write_board_mirror`. `board_from_scope` treats any scope containing `/` as the project board, so `<scope>/pathly/project/BOARD.json` and its directories are created inside another project, or relative to the server cwd. Probe test_p3.py reproduced this: files and directories appeared in project B from a chief on project A. The cause is that the gate applies project binding by the declared `board`, while the mirror applies it by the shape of the scope. The "A folder name" bullet in CLAUDE.md, and the tripwire test that backs it, say that only `features/decompose` and the `/comms/run` evaluator make a folder from a name. This path is a third. Under your rubric this is arguable, because the table documents `board:"feature"` as unbound, so I rate it major. It is a write to another project's tree through a scope field. Fix, either of these:
   - In `chief_project._bound_scope`, treat a path-like scope (`_path_like`) as a project root on every board and bind it. Or give the `/comms/post` scope `segment=True` on non-project boards, as `/comms/run` already has.
   - Make `board_mirror` refuse or ignore a scope that is not a normalised absolute project root for the project board and not a single segment for the other boards. This also covers the human and agent callers, which the gate does not reach.
   Then correct the CLAUDE.md folder-name bullet and add a test for the post route.
   Related, less certain: `POST /runs` with `kind=single`, `board=global` and a traversal `scope` passes the gate, because `/runs` has no `segment` on its `ScopeRead`. With early advance on (the default), `_run_stage_via_terminal` raises ValueError at `terminal.py:133` (`_resolve_storage_path`), and nothing was written (probes test_p4.py and test_p5.py). I did not trace the early-advance-off slow path; `terminal_phase.py`'s fallback joins the topic under the project root. The same `segment` fix would close it.
3. minor src/pathly_orchestrator/CLAUDE.md ("Not bound", item 2): The text says `GET /db/rollup`'s `global` block "sums every project". It also lists every project's root path and cost (`by_project`). That helps a chief learn other projects' roots. Say so, or drop the per-project rows from `global` when the caller is a chief.
4. minor src/pathly_orchestrator/CLAUDE.md ("Not bound", item 1): The id-addressed reads list names `/comms/artifacts/<id>/section` but not `GET /comms/artifacts?message_id=`. That route is also unbound by an id, and its `ROUTE_FIELDS` entry is correct. Add it to the list.
5. minor pathly/features/chief-agent/tasks/14-bind-id-addressed-chief-calls-to-its-project.md: Its opening sentence says ticket 08 binds the chief only when the body or query string names `project_root`. That is stale, since 08 now also binds board scopes, files and folder names. A builder reading ticket 14 will misjudge what is already bound. Reword that sentence. The same ticket should also say that `chief_bind` and `ROUTE_FIELDS` must stay consistent.

REVIEW: FAIL

## Review findings (round 5, quality review)

QUALITY
1. blocker src/pathly_orchestrator/supervisor/goal_executor.py: An operator chief can create directories in another project's tree, or anywhere writable, through the undeclared `flow` field of `POST /comms/goals/run`. The entry in src/pathly_orchestrator/http_server/chief_fields.py declares only roots, `names_root` and `unbound=("goal_id",)`. With `executor:"team"`, `flow` goes straight to `_run_team(flow=...)`. There `_flow_kind(flow)` returns any unknown name unchanged, and `board_run_topic` and `os.makedirs(os.path.join(project_root, "pathly", *topic.split("/")))` run before `_load_flow` rejects it (400 `unknown_flow`). My probe sent `flow:"../../../../B/planted"` from a chief on project A and got `B/planted/ship-export-<id>` created in project B. The directory was left behind although the response was 400. Only empty directories are made. This is the sink class the "Chief gate" section says "the gate holds" in all three ways. - Declare `flow` on that route (and on `/runs` and `/comms/run`) as a folder-name field, or refuse it unless it is a packaged or DB flow name. Validate it in `_flow_kind` / `_run_team` and move the `makedirs` after `_load_flow` succeeds. Add a test that posts a traversing `flow` from a chief and checks that no directory appears outside the project.
2. major src/pathly_orchestrator/skills/compose_resources.py: Two more request strings reach path joins that no `ROUTE_FIELDS` entry declares or bounds. (a) `skill` on `POST /comms/run` goes through `start_board_run` and `_compose_skill_body` to `_read_skill_body`, which does `_skills_root().joinpath(f"{skill}.md").read_text()`. My probe passed an absolute and a `../..` value, and the server read `B/planted.md`, another project's file, into the agent prompt (200). (b) `flow` on `POST /runs` with `kind=flow` reaches `fsm_ops._load_flow` and opened `B/planted.flow.yaml` (200). A flow file can carry a literal `command` for `command_gate`, so this is more than a read. - Constrain `skill` and `flow` in the sinks (no `..`, not absolute, resolved path inside the skills or flows root) and declare them in `chief_fields.py`.
3. major src/pathly_orchestrator/CLAUDE.md: The "Chief gate" claim "A request string becomes part of a path in three ways, and the gate holds each" is not backed by the code (see 1 and 2). The "Other places" list says everything not held is `event_mirror.backfill_event_mirrors` and `goal_decomposer`, and that list is incomplete. The tripwire paragraph is also stronger than the tests. It says the tripwires read "the helpers it calls", but the walk covers only helpers under `blueprints/`, and `_PROJECT_ISH` is a name-pattern filter, so `flow` and `skill` (read in the view, joined in `supervisor/` and `skills/`) are never seen. - After fixing 1 and 2, rewrite the claim as "the three ways found", and state what the tripwires cannot see. Better, make the tripwire list every key a view reads, not only project-like names.
4. major src/pathly_orchestrator/CLAUDE.md: The doc says `GET /comms/artifacts/<id>/section` is held by "`hydrate_helpers.safe_artifact_path`, a realpath containment check". `runner/hydrate.py::hydrate_section` calls `safe_artifact_path` only in the scope-plus-artifact branch. The id branch does `path = row["path"]` with no containment. In my probe a status chief read `B/secret.md` (200, `"text":"# secret\n"`) from a row another writer had posted, both with and without `project_root`. The "Not bound" paragraph lists the same route as an unbound id read, so the document contradicts itself. - Either add the containment check to the id branch (the row's path must lie under the bound `project_root`), or delete this route from the "Held" list and say that the row's stored path is read as is.
5. minor src/pathly_orchestrator/CLAUDE.md: Three doc sentences are imprecise.
   - It says `board_mirror_path` is None for an unfit scope. That holds for a feature board only. For `board="project"` the function ignores `scope` and returns the project path. `write_board_mirror`'s `_scope_fits` is what stops it.
   - It says the `/db/*` reads "open no file". `/db/features` (`db_api_explorer.py`) globs and reads `STATE.json` and `RUNNER_STATE.json` under the bound root, which is harmless because the root is the chief's own.
   - It says feature boards are keyed by name only. The mirror therefore writes `BOARD.json` into whichever project `run_history` maps that name to, which may be another project's `pathly/features/<name>/BOARD.json`. - Reword each to match.
6. minor src/pathly_orchestrator/board_mirror.py: A relative project-root scope (for example `proj/x`) is now not mirrored, because `is_project_root` requires a leading `/` or a drive. Before, `board_from_scope` treated any scope with `/` as a project. It is a rare legitimate shape, and no test covers it. - Add a pinned test or one doc line so the change is deliberate.

Notes above the verdict.
- Range reviewed: 570a6eef44c62cc658b338f90572d9ab871edb6f..12df38bcc16cd9dc200ac2af8669868b21a2b53f. END equals HEAD, so no later commits were left out. I did not read the ticket's `## Answer`, so no verdict was formed before seeing it. I read the two "NOT guarded at the sink" lists in CLAUDE.md, as permitted.
- Done-when: I re-ran both commands and both passed (97, 33, 128 and 1132 tests passed). In addition, `black --check` on the 12 changed non-test files, `scripts/check_file_size.py`, `scripts/gen_test_index.py --check`, `lint-imports` and `mypy` on the five new or changed modules all pass.
- (a) How I checked the closing claim. I ran an audit-hook harness (`sys.addaudithook`) that records which of project A, project B, the server working directory or a fake home each filesystem event hits. It ran in-process with a faked spawn host. I drove 31 POST routes as status, planner and operator chiefs with hostile values: `..`, absolute, UNC, drive and NUL values, in every declared and undeclared body field. The gate refused every declared field correctly (mirror, `features/decompose`, evaluator save, goal `slug`, storage-path resolution, `context_refs`, `/code/query` target). The only hits were `flow` on `/comms/goals/run` and `/runs`, `skill` on `/comms/run`, and the id form of the artifact section (items 1, 2, 4). `event_mirror.backfill_event_mirrors` and `goal_decomposer` were not reachable through any field the gate lets a chief set. They are reachable only for rows another writer posted, which matches the documented gap. I checked the GET routes by reading code only (flows, skills, menu, hq, db), not by fuzzing, and found no further sink.
- (b) I checked every sentence of "Chief gate" against the code. The overclaims are items 3 to 5. The rest holds.
- (c) I found no regression for legitimate callers, apart from item 6. Roots checked: POSIX, `C:/`, spaces and unicode. Names checked: feature names with dots, spaces and unicode, plus `(interactive)`, `(project)` and `global`.
- (d) I checked the sampled `ROUTE_FIELDS` entries against the route code: `/comms/artifacts/<id>/section`, `/flows/*`, `/skills/*`, `/menu/<name>`, `/hq/context`, `/db/*`, `/telemetry/trends`, `/runner/status`, `/comms/trash`, `/static`. The only entry that does not match its route is the id section (item 4).
- Files left behind: `git status` is clean. All probes and logs are under the scratchpad `rv5/` and `venv`. The first finding's probe created `planted/` directories only inside throwaway test project directories under `/tmp/pathly-tests`.

REVIEW: FAIL

## Review findings (round 6, quality review)

QUALITY (chief-agent 08, round 6: acf32ae and 45d1854 on top of 7521392, range 570a6eef44c62cc658b338f90572d9ab871edb6f..45d1854)

Scope notes. I did not read the ticket's `## Answer`. I read the base-commit ticket, the earlier review findings and the diff. No repo file was changed, staged or committed (`git status` is clean). My probes are only under the scratchpad `rv6/`. I re-ran both Done when commands and they pass (97 and 33 tests). 1529 gate, mirror and storage tests pass, and the lints are clean. A background full-suite run (`pytest tests/ -q -x --deselect tests/http_api`) had not finished when I stopped. It was at about 34% with no failure, so I count it as incomplete.

1. major src/pathly_orchestrator/http_server/chief_project.py (`is_own` and `_under`, with `supervisor/chief_session.py::normalise_project_root`): The gate treats backslash as a path separator on POSIX. `is_own` compares after `\` becomes `/` and a trailing `/` is stripped, so a backslash spelling of the chief's own `project_root` passes. Examples are `/work/proj\`, `\work\proj`, and `/work/proj/sub\..\..\other`. On POSIX the routes use the raw string and read it as a relative path under the server's cwd, or as a sibling directory. I reproduced this as planner on `/comms/features/decompose`. As operator I reproduced it on `/comms/goals/run`, `/comms/run`, the decompose routes and `/code/query`. The audit hook recorded 27 file touches in the server cwd. This is a chief reaching files outside its own project through a declared key. Fix: on non-Windows, refuse any `project_root` or path value that contains a backslash. Alternatively compare the raw string after `rstrip("/")` only. Then change `test_the_chiefs_own_project_passes_however_it_is_spelled` in tests/http_api/test_chief_gate.py, whose "backslashes" case currently asserts `_passed`. Add these spellings to the audit.
2. major src/pathly_orchestrator/CLAUDE.md ("Chief gate", "What was measured") and tests/http_api/test_chief_gate_audit.py: The doc says every key gets the full hostile list at every tier. The test does not do that. `_attack` sends only `FEWER = ("dotdot","other project","other file","nul","very long")` to plain keys and to the status and planner tiers. The audit never sends the own-root spellings that the gate accepts, which is why finding 1 got through. The sentence that nothing falls in the server cwd is false on POSIX. Fix: add the accepted-spelling variants (backslash, trailing slash, `.` segments, doubled slashes) to the hostile list for the root and path kinds. Either run the full list at every tier or reword the doc to say what is actually sent.
3. minor tests/http_api/test_chief_gate_audit.py: Plain keys get no relative climbing value (`../..`). The two removed tripwire tests also did not check that each key has the right kind. A key declared plain that is really a path sink would not be caught. Fix: add a relative climbing value for plain keys, and a check that a key's declared kind matches what the sink does with it.
4. minor src/pathly_orchestrator/http_server/chief_routes.py, chief_fields.py and CLAUDE.md "Not here yet": Ticket 15 plans `max_cost_usd` on `POST /runs`. That key is not in the complete allowlist, so a chief would get a 403 when it uses it. Fix: list it in the audit's `WAITS_FOR_A_TICKET` entries and in the "Not here yet" paragraph, so ticket 15 knows to extend the entry.
5. minor chief_gate and the feature-board routes: Feature boards are keyed by feature name only. A chief can name another feature on its own project but not another project. This is already documented, so I only list it. Nothing to change beyond ticket 14's id-addressed work.
6. minor tests/http_api/chief_audit_world.py: Several audit baselines stop early. `/comms/supersede` returns a route 403, `/runner/agent-answer` returns 404, and the stop routes, `/code/query` (backend none) and `reroute`/`retry` (loop patched) also end before the sink. The hostile values may not reach the sink on those routes. Fix: give each a baseline that reaches the sink (a real superseded message, an open question, and so on), or list them as not covered.
7. minor src/pathly_orchestrator/runner/code_context_cli.py (`_file_section`): The tail of `target` goes unescaped into a Cypher string, so a quote in `target` could change the query. I did not test it. It stays inside the chief's own project graph, so this is not a tier breach. Fix: escape or parameterise `target`.
8. minor, docs and ticket 17: A relative `artifact_path` post is refused. A symbol target like `a:b` is read as a drive path. The planned `pathly api` texts for ticket 17 must teach the `project_root` field and the per-route key lists, or chiefs will hit 403s on legitimate calls. Fix: note this in ticket 17 and the doc.

Checked and found sound (no finding):
- Allowlists are wide enough for the Done when, the spec's chief flows and ticket 17's planned calls, apart from finding 4. The 13 `MUST_BE_ACCEPTED` routes pass.
- The sink guards hold with the gate's name checks switched off: `board_mirror`, `_load_flow`, `_skill_file`, `_run_team`, `ensure_goal_slug`, `hydrate_section(contain_in=)` and `_is_unsafe_topic`.
- The GET routes and URL path variables were attacked and hold.
- The sink edits cause no legitimate-caller regressions.
- Every sentence of the "Chief gate" section matches the code except the "What was measured" claim in finding 2.

REVIEW: FAIL

## Review findings (round 7, quality review)

QUALITY (chief-agent 08, round 7, quality pass)

Scope notes
- Base 570a6eef44c62cc658b338f90572d9ab871edb6f. END = 92fa929 = HEAD, so no later commits were left out. Round 7 is 509e381, fc2b66e and 92fa929.
- I read the ticket as of the base commit plus the `## Review findings` sections of rounds 1 to 6, and the diff. I did not read `## Answer`. The "Chief gate" section of src/pathly_orchestrator/CLAUDE.md I did read, as permitted.
- Done when, re-run by me:
  - `tests/http_api/test_chief_gate.py` gave 106 passed.
  - `tests/comms_board/test_comms_write_perm.py` gave 33 passed.
- Wider runs, no failures:
  - All `test_chief_gate*.py`, `tests/storage_paths` and `tests/code_intel`. The one skip is the old Windows-only one in `test_code_context_pathresolve.py`.
  - The rest of `tests/http_api` (220 passed).
  - `tests/` minus `http_api`. This ran at -q -q with no summary line; the log has no F or E mark.
- black, mypy on the changed modules, lint-imports, check_file_size, `gen_test_index --check`, check_no_mirror_reads and check_version_sync are clean. `git status` is clean; I changed nothing in the repo.
- My probes are only under the scratchpad directory `rv7r/`. They created folders only inside throwaway test projects under /tmp/pathly-tests.

1. major src/pathly_orchestrator/runner/code_context_cli.py (`_CLI_CACHE`) and src/pathly_orchestrator/http_server/blueprints/code/query.py (`_QUERY_CACHE`): `/code/query` hands one project's code-graph block to a chief on another project, on a call the gate passes as bound. This is the `_CLI_CACHE` side effect you asked about, and it is wider than that.
   - `_CLI_CACHE` is keyed `(path, content-hash)` with no project. Round 7 made `_file_hash` read a relative target under the project root, so relative paths now hash and cache across projects. Before, they hashed against the server cwd, mostly to "", and were never cached. Probe `test_cache.py`: after project B built the block for `src/a.py`, project A with identical bytes was served `sym_of_pb` and the graph was not queried again.
   - `_QUERY_CACHE` in `query.py` is keyed `(op, target, content-hash, backend)`, also with no project. The hash is "" for a directory or a missing file, so the key is then only the string. Probe `test_codecache_dir.py`: a human asked `{"op":"symbol","target":"src","project_root":B}`. A status chief on A then sent `{"op":"symbol","target":"src","project_root":A}`. The gate passed it, and the answer was `cached: true` with `symbols_of_project_B (callers:7, callees:9)`, although A's `src` has different files. The same happened with identical-bytes files (`test_codecache_e2e.py`). Clearing either cache alone still left the other leaking.
   - `query.py` is unchanged in this ticket, so `_QUERY_CACHE` is old. But the section says a code query of another project is refused, and this is a read of another project's graph data through an accepted call. For legitimate callers (worktrees and forks share relative paths and bytes), agents can now get another project's caller counts. The doc does not mention it.
   - Fix: put the normalised project root in both keys. For `_CLI_CACHE`, use `(project, path, hash)` or the joined absolute path. For `_QUERY_CACHE`, add `project_root`, or do not cache when the hash is "". Add a test with two projects and the same relative target.
2. major src/pathly_orchestrator/CLAUDE.md ("Chief gate", "What was measured") and tests/http_api/test_chief_gate_audit.py (`_routes`): the doc says "a key of a file kind ... or a URL variable gets the whole list". The code does not do that.
   - `_routes` gives the shorter `PLAIN_VALUES` list to any URL variable that the entry lists as a name or id. I ran `_routes`: 11 of the 19 URL variables get the short list. They are `feature` (4 `/api/features/<feature>/*` rules, 4 `/db/features/<feature>/*` rules), `artifact_id`, and `run_id` (`/db/runs/<run_id>/cost`, `/runs/<run_id>`, `/runs/<run_id>/<action>`, `/runs/<run_id>/stop`).
   - They never receive the server-directory, home-directory, UNC, drive, trailing-slash or own-root spellings, so the claim is false for them.
   - I sent the whole list to those 11 at the status and operator tiers (`test_urlvars.py`, 520 requests each): no violation. So the fix is cheap and safe.
   - Fix: in `_routes`, give the whole list to every key in `url_variables(rule)`. Or reword the doc.
   - Smaller nit in the same paragraph: the short list has no absolute climbing path (its absolute values are the other project and a file in it). Say what it sends.
3. minor src/pathly_orchestrator/db/queries/run_history.py (`_SLUG_MATCH`, via `latest_project_root_for_feature`) and src/pathly_orchestrator/CLAUDE.md ("Not held"): the documented feature-board mapping is wider than the doc says. `feature LIKE '%/' || ?` treats `%` as a wildcard, and `%` passes `is_segment`.
   - Probe `test_wild.py`: with one legacy run_history row (a full-path `feature`) for project B, a planner chief on A posted `board:"feature", scope:"%"`. The mirror created `B/pathly/features/%/BOARD.json`. The chief did not need to know any feature name of B.
   - Needs old-format rows. It is the same class the section already discloses ("whichever project run_history last mapped that name to"), but "that name" is not true for a wildcard.
   - Fix: add an `ESCAPE` clause or escape `%`, `_` and `\` before the LIKE in `_SLUG_MATCH`, or refuse them in a feature-board scope. At least reword the doc.
4. minor src/pathly_orchestrator/CLAUDE.md ("Held at the gate only") and src/pathly_orchestrator/http_server/chief_project.py (`lies_under`): the symlink limit is stated, but its effect is not.
   - Probe `test_symlink.py`: with a symlink inside project A pointing at project B, a chief posted `artifact_path=<A>/link/pathly/features/demo/PLAN.md`. The gate passed it (text containment), and the server then opened B's PLAN.md.
   - `GET /comms/artifacts` returned `indexed_structure_key: "hidden-heading|secret-plan"`, so B's heading names reach the chief. The by-id `/section` read correctly answered 400.
   - The chief's own tools cannot create the link, so this needs a link that already exists. Fix: apply `hydrate_helpers.inside_root` (realpath) to a chief's `artifact_path` and `/code/query` `target` at the gate, as the by-id read already does. Or state this effect in the doc.
5. minor src/pathly_orchestrator/runner/code_context_cli.py (`_cypher_literal`): the escape is right for standard Cypher, but the real `codebase-memory-mcp` is not in the repo or the environment, and `test_code_context_cypher.py` reads the literal with its own standard-escape model. If the tool's lexer does not take `\"` as an escape, a quote still ends the literal. The tail never holds a backslash, since `\` is turned into `/` first. Fix: also drop or refuse `"` in the tail, or note that the escape is unverified against the tool.
6. minor pathly/features/chief-agent/tasks/17-pathly-api-command-and-built-in-styles.md (note for ticket 17): the gate compares `project_root` as an exact string, but nothing tells the chief the stored string. A chief that reads its root with `pwd` can differ from the stored root (a symlinked parent such as macOS `/var`, letter case on Windows). That chief is then refused on every call that names its project. Ticket 17 should pass the stored root to the chief (an environment variable or the prompt), not only say "spell it as the session's".

Checked, no finding
- (a) I tried to reach another project's tree, board or files, or the server's directory or home, by independent routes:
  - Marker taint (`test_taint.py`): 1,336 requests, with a marker in every plain-kind key and URL variable of every route, and four value shapes. No file-system or subprocess event carried the marker, and the SQL traces show bound parameters only.
  - Spelling fuzz (`fuzz_spell.py`): 92,582 candidates compared with the real file system. The gate takes a root as the chief's own only when it is the root plus trailing slashes, and `samefile` agrees. No path accepted by `lies_under` leaves the project except through the in-project symlink of finding 4.
  - Covered in the probes above: trailing and doubled slashes, `.` and `..` segments, case, NFC and NFD forms, percent-encoded text, padding, NUL, long values, a root equal to a parent or a prefix sibling (`/work/proj` vs `/work/proj-b`), and a project directory that is a symlink. All were refused or equal to the chief's own folder.
  - The Windows reading (`host_is_windows` patched true): backslash and UNC roots are accepted only for the chief's own root, and case and `\\?\` spellings are refused.
- (c) Every sentence of "Chief gate" matches the code except finding 2 (and the wording gaps in findings 3 and 4). Specific checks:
  - Nine routes in the separators test, 20 `REACHES` baselines, and the three `HELD_BY_THE_VIEW` keys all match.
  - I re-ran the "breaking the guards" claims on the operator audit. With the Windows reading forced, with the project rules off, and with the code backend's hash left to the server cwd, the audit fails each time. With only the key list off it passes. All as the doc says.
  - The "not covered" list is accurate (reroute, retry, and the codeintel, lsp and both backends).
- (d) The key allowlists admit every flow the spec's walkthrough and ticket 17 name. They include `cite` on the answer routes and `project_root` on `GET /chief/session`. `max_cost_usd` on `POST /runs` and `/comms/directives` wait for tickets 15 and 12, and are documented.
- No weakened checks. The edited existing tests were flipped on purpose (a backslash root is refused on a POSIX host), and no skip, xfail or noqa was added. The new tests assume POSIX paths, but CI is Linux-only.

Rated against your rubric: findings 1 and 2 are major (data of another project handed to a gated chief, and a doc claim the code does not back). Findings 3 to 6 are minor.

REVIEW: FAIL
