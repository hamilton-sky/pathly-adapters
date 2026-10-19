# Map: chief-agent

## Destination

Round one (this plan) leaves the chief's server core in place and proven. `POST /chief/open`
resolves a tier from the chosen preset, mints a `chief` run token, writes the session's claude
settings (a UserPromptSubmit hook and permission rules), registers the session and sends an
interactive `TERMINAL_SPAWN` that asks the host to paste the prompt without sending it; closing the
tab or restarting the server revokes the token. A `before_request` chief gate refuses every call
the session's tier does not allow, every unlisted write, any other project, and any revoked chief
token. Human messages typed in a claude chief tab are recorded, and a chief-token answer to an
agent must cite one, once; Pathly relays that message's own text, so the chief never words an
answer. The chief's claude starts in restricted mode with its own session id, so none of the user's
or project's settings reach it, and every chief prompt ends with the un-editable `chief-connect`
fragment. Binding directives keep reaching the prompts of the roles they target after an
acknowledgement, in their own standing-orders block, and only a chief token may post or retire one
until the UI token exists. A chief stays inside its project even on id-addressed calls and inside a
per-session cost and run ceiling. The three run-token holes are closed. A `pathly api` command,
three built-in style texts and the `chief-connect` fragment make the chief usable from a tab opened
with `POST /chief/open`. The rest of the brief is outlined below as round two: the friendly
`pathly` commands, the overview and inbox calls, Studio pasting without Enter, the Chief button
next to HQ, the inbox badge, the stale-directive re-queue and billing the chief's own session. The
split follows the user's decision for rounds; § Brief coverage maps every In-scope line of the
brief to where it is built.

**The bar.** `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider`
passes with a fake spawn host: opening the chief mints a `chief` token for the chosen style and
spawns an interactive tab with the style's prompt pasted and not sent; with the Operator style the
chief's API calls create a goal and start a run that Pathly spawns through its normal spawn path; a
Status-style token is refused on a write; an agent question is pending until the chief cites a
human message and Pathly relays that message's text, and an uncited answer, or one with the chief's
own words, is refused; a binding decision reaches the next builder, reviewer and tester prompts
after an acknowledgement and no caller but the chief retires it; a run above the ceiling and a call
on another project's run are refused; `pathly api` works from the chief's tab; the raw run token no
longer appears on `/events/runner` or `/events/runs`. And `python -m pytest tests/ -q -p
no:cacheprovider` passes in full. Ticket 13 runs both.

## How to work this

- Plans live in `pathly/features/` (root `CLAUDE.md`, "Feature plans"), so run the scripts with
  `FLOW_DIR=pathly/features FLOW_TICKETS=tasks`.
- See what is ready: `python3 scripts/flow-status.py chief-agent`. Take the lowest numbered READY
  ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py chief-agent --mermaid` (coloured by status, drawn
  on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- `round-two-drafts/` holds work drafted for round two (§ Round two). The flow scripts read only
  `tasks/`, so nothing there is claimed or built in round one.
- Design is in `spec.md`. The previous chief plan (git `72292b35:pathly/features/chief-agent/`) is
  superseded; its directive, answer-relay and project-writer parts are reused here.
- Hard rules from `CLAUDE.md`: 400-line ratchet (`scripts/check_file_size.py`), layer rule
  `db -> runner -> supervisor -> http_server` with lazy imports inside routes, new endpoints in a
  matching or new blueprint domain, living docs in the same change, unique test basenames and
  `python scripts/gen_test_index.py` after adding tests. CI also runs `bandit -r src/ -ll -x
  src/pathly_data/`: no f-string or `+` SQL building in new code (use `IN (SELECT value FROM
  json_each(?))`), never `# nosec`. The full suite runs on Python 3.11, 3.12 and 3.13.
- Do not touch HQ, in either round (the user's decision, 2026-10-14): not
  `studio/src/renderer/src/components/HQ/`, not HQ's top-bar toggle (`topbar-chat-toggle`), not
  `chatStore`, not `src/pathly_orchestrator/chat_agent.py`. The Chief is added beside HQ. A
  ticket that seems to need an HQ change stops and asks the user.

## Decisions so far

- Plan revised 2026-10-13 after an independent review of the merged plan
  (`/mnt/project-files/chief-agent/independent-review-2026-10-13.md` in the project's shared
  folder; the external assessment in this folder is a separate, earlier record). #63 (`b141dde`:
  supersession, the human escalation gate, tier-then-recency governance) landed after the plan,
  so: tickets 03, 11 and 12 re-measured (`messages_crud.py` 395 lines, `messages_write.py` 400,
  `comms_context.py` 370) and 11 renders directives through `render_governance_lines` in their own
  block; 08 classes a human-escalation acknowledgement as `answer` and refuses delete, hydrate,
  task status and `force_past_gate`; 10 requires the cited words verbatim, single-use citations,
  and a cite to close a human escalation; 06 adds `--strict-mcp-config` and curl/wget denies; new
  tickets 14 (project binding by id), 15 (cost and run ceiling), 16 (only the chief retires a
  directive; hydration cannot forge one) and 17 (`pathly api` and built-in texts). Round two
  item 1 now builds on `pathly api`, and item 4 only adds paste-without-Enter, because Studio
  already exports `PATHLY_RUN_TOKEN` for runner tabs
  (`studio/src/renderer/src/components/TerminalSpawnListener.tsx`, `main/ipc/terminal/spawnEnv.ts`).

- Plan revised 2026-10-14 after a third review (`review-2026-10-14.md` in this folder; it verified
  the plan's code references against `0c3aba1c` and the installed claude 2.1.292). Ticket 06 starts
  claude with `--restricted` (or `--setting-sources` with no sources) and `--tools
  Bash,Read,Glob,Grep`, because allow rules from the user's and project's settings files would
  otherwise merge into the chief's and let it call the server without its token; it also passes a
  server-chosen `--session-id`, stored as `chief_sessions.cli_session_id` (ticket 05). Ticket 09
  refuses hook posts from any other session id and measures whether a message another session sends
  into the chief can be labelled `relayed`. That session id binds the process, not the typist, so
  it does not by itself settle the cross-session open question. Ticket 10 drops the word-for-word
  rule: the chief sends only `cite`, and Pathly relays the cited text (the chief retyping the
  user's words in shell-quoted JSON would refuse honest answers); it also keeps every question of a
  multi-question ask. Ticket 08 tests the default refusal of unlisted routes as a property of
  `app.url_map`. Ticket 15 gives a run slot back when the route answers 4xx. Ticket 17 moves the
  fixed rules into a `chief-connect` fragment appended to every style. Round two's billing item now
  reads the claude transcript, because an interactive tab prints no cost summary. Draft ticket 18
  (daycap spend) moved to `round-two-drafts/daycap-spend-report.md`, ticket 19 (daycap guard spike)
  stays, and round two is outlined as two parts, 2a and 2b.

- Plan — the Chief button goes in the top bar next to the HQ toggle, and HQ stays as it is (the
  user's decision, 2026-10-14; § Open questions, "Chief and HQ"; spec.md § UI). The brief had the
  Chief replace HQ; round one is the same either way.

- Plan — styles are three editable presets (Status, Planner, Operator) chosen in the existing
  shared picker (`PromptActionConfig` with `CliSelect`, `useMergedPresets`, library category
  `chief`); no new picker. Each preset names its base tier in front matter (`tier:`); a missing or
  unknown tier means Status. The action list per tier is a server constant bound to the session.
  (The brief's `Decided:` line.)
- Plan — the role-read-policy pieces are on `origin/master` (`72292b35`) and used as they are:
  `mint_run_token` / `resolve_run_token` / `revoke_run_tokens`, `caller_identity`,
  `provenance.stamp`, `read_policy.BUILTIN_DEFAULTS["chief"]`.
- Plan — the chief does not use `_run_stage_via_terminal`; it uses `create_run(run_id)` so the
  existing `/runner/terminal/started|result` callbacks reach it (the result handler skips billing
  when no `RunnerState` matches the topic `chief:<run_id>`), and a watcher thread closes it.
- Plan — `pathly-pty-host` refuses interactive spawns, so a chief needs Studio; with only the pty
  host the failed result closes the session.
- Plan — a revoked or unknown token resolves to `anonymous` in `caller_identity`, and anonymous
  loopback callers are unrestricted, so the chief gate must answer a revoked chief token itself.
- docs: https://code.claude.com/docs/en/hooks — UserPromptSubmit receives the common fields
  (`session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`) plus `prompt`;
  plain stdout on exit 0 is added as context Claude sees; exit 2 or `decision: "block"` blocks the
  prompt; it also fires on a scheduled task, a background subagent reporting back, and a message
  another session sends; pasted text arrives expanded in `prompt`; the default timeout is 30 s;
  hooks inherit the parent environment.
- measured: `claude --help` on claude 2.1.292 (2026-10-14) — `--restricted` "ignores user,
  project and local settings files (managed settings and --settings still apply; add
  --strict-mcp-config to skip MCP servers too)", removes the tools that run commands and
  `WebFetch` unless `--tools` names them, confines the file tools to the working directories and
  refuses `bypassPermissions`; `--tools` sets the list of built-in tools (`""` for none);
  `--setting-sources` takes a comma-separated list of `user`, `project`, `local`;
  `--session-id <uuid>` sets the conversation's session id. Not yet measured: whether the
  `--settings` hook fires under `--restricted` (ticket 06).
- docs: https://code.claude.com/docs/en/cli-reference — `--settings` takes a settings file or JSON
  string; `--model`, `--allowedTools` and `--disallowedTools` exist; `claude` alone starts an
  interactive session.
- docs: https://code.claude.com/docs/en/permissions — rules are evaluated deny, then ask, then
  allow; `Bash(pathly *)` matches the command text; `Read(~/path/**)` is a home-relative deny
  rule; a bare tool name such as `Write` denies the tool everywhere; Bash outside a read-only set
  asks before running.
- docs: https://code.claude.com/docs/en/tools-reference — built-in tool names used in the deny
  list: `Agent`, `Edit`, `Write`, `NotebookEdit`, `CronCreate`, `Workflow`.
- docs: https://learn.chatgpt.com/docs/config-file/config-basic — codex
  `shell_environment_policy.ignore_default_excludes` defaults to `true`, so names containing
  `KEY`, `SECRET` or `TOKEN` are not filtered by default.
- docs: https://learn.chatgpt.com/docs/config-file/config-advanced — with that set to `false` the
  default exclusions run first and only `set` restores a variable, so a filtered
  `PATHLY_RUN_TOKEN` could only come back through argv or config.
- docs: https://learn.chatgpt.com/docs/sandboxing — codex `read-only` sandbox: "the agent can
  inspect files, but it can't edit files or run commands without approval"; the documented
  local preset uses `--sandbox workspace-write --ask-for-approval on-request`, so both flags exist.
  The page does not state the default network rules.
- docs: https://learn.chatgpt.com/docs/hooks — codex has a UserPromptSubmit hook (stdin `prompt`,
  `turn_id`) configured in `hooks.json` or `config.toml`; project hooks need trust review and the
  page does not say a hook can be passed per session with `-c`.
- docs: https://www.sqlite.org/pragma.html#pragma_query_only — "When this pragma is enabled, any
  attempt to CREATE, DELETE, DROP, INSERT, or UPDATE will result in an SQLITE_READONLY error",
  and `PRAGMA query_only = boolean` sets it. Python raises this as `sqlite3.OperationalError`
  ("attempt to write a readonly database"). Measured with `query_only` on, for
  `WITH x AS (SELECT 1) INSERT ...`, `... UPDATE ...` and `... DELETE ...`: all three refused,
  nothing written. This held on Python 3.11.17, 3.12.3 and 3.13.16 with SQLite 3.45.1 (ticket 02).
- docs: https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Cursor.execute and
  https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Cursor.execute — `execute` "Raises:
  ProgrammingError – If sql contains more than one SQL statement", and `executescript()` is the
  multi-statement call. `ProgrammingError` and `OperationalError` both subclass `DatabaseError`,
  which subclasses `sqlite3.Error`, so `/db/query`'s existing `except sqlite3.Error` answers 400.
  Measured: `SELECT 1; PRAGMA query_only = OFF` raises `ProgrammingError` and leaves `query_only`
  on, on 3.11.17, 3.12.3 and 3.13.16 (ticket 02).
- docs: https://werkzeug.palletsprojects.com/en/stable/wrappers/#werkzeug.wrappers.Request.get_data
  (Werkzeug 3.1.x; `requirements.lock` pins Flask 3.1.3 and Werkzeug 3.1.8) — `get_data(cache=True,
  ...)`: "By default this is cached but that behavior can be changed by setting `cache` to
  `False`". In the source at https://github.com/pallets/werkzeug/blob/3.1.8/src/werkzeug/wrappers/request.py,
  `get_data` returns `_cached_data` when it is set, and `get_json` reads the body with
  `self.get_data(cache=cache)`. Measured: a `before_request` hook that calls `get_data()` leaves
  the body intact for a view that calls `get_json()` and `get_data()`, on Python 3.11, 3.12 and
  3.13 with the pinned Flask and Werkzeug (ticket 08).
- docs: https://flask.palletsprojects.com/en/stable/api/#flask.Flask.before_request (Flask 3.1.x) —
  "If it returns a non-`None` value, the value is handled as if it was the return value from the
  view, and further request handling is stopped"; `preprocess_request` "calls
  `before_request_funcs` registered with the app". The source at
  https://github.com/pallets/flask/blob/3.1.3/src/flask/app.py walks each list in registration
  order. Measured: a hook registered second runs second and can stop the view (ticket 08).
- docs: https://github.com/pallets/flask/blob/3.1.3/src/flask/wrappers.py — `Request.url_rule` is
  "The internal URL rule that matched the request. This can be useful to inspect which methods are
  allowed for the URL from a before/after handler". In
  https://github.com/pallets/flask/blob/3.1.3/src/flask/ctx.py, `RequestContext.match_request`
  sets it when the context is pushed. When no rule matches, it sets `routing_exception` and leaves
  `url_rule` None. Measured: inside a `before_request` hook, `POST /runs/abc/pause` gives
  `url_rule.rule == "/runs/<run_id>/<action>"`, and an unknown path gives None; the hook still runs
  and Flask then answers 404 (ticket 08).
- docs: https://www.sqlite.org/json1.html — "The JSON functions and operators are built into SQLite
  by default, as of SQLite version 3.38.0"; `json_each`'s `value` column is the element's SQL
  value. Measured: `x IN (SELECT value FROM json_each(?))` with a JSON list works on Python 3.11,
  3.12 and 3.13 with SQLite 3.45.1 (ticket 11).
- 01 — `sse._broadcast_runner` sends `run_token` only on `/events/spawn`: the `/events/runner` and
  `/events/runs` copies are built without the key and the caller's dict is untouched;
  `/events/spawn` itself stays credential-free until the UI token (RRP-2b).
- 02 — `/db/query` runs its statement under `PRAGMA query_only = ON` (reset to OFF in a `finally`) on
  the request thread's connection, so a `WITH ... INSERT|UPDATE|DELETE` is a 400 "attempt to write a
  readonly database" and writes nothing; the keyword check stays as the first filter.
- 03 — `POST /comms/edit` re-stamps the row to the editor: `update_message_text` (now in `db/queries/comms_edit.py`, re-exported from `comms_messages`) sets text and the three `author_*` columns in one `UPDATE`, from `_helpers.edit_stamp(request)` = `stamp(caller_identity(request))`; no token stores `author_source="none"`, and a call with no stamp does too.
- 04 — `supervisor/chief_tiers.py` holds the tiers as code (`TIERS` read-only: status=read, planner=read/post/plan, operator=all seven); `resolve_preset_tier(preset, project_root)` lets a `chief/<preset>` prompt file decide by its leading front matter `tier:` (no file-level `tier:` = status), else the built-in names map to themselves (exact match), anything else is status; `strip_front_matter` reuses `compose_base._strip_leading_frontmatter`.
- 05 — `db/migrations_chief.py::add_chief_tables` (called last in `_add_additive_migrations`) makes `chief_sessions`, `chief_human_messages` and `chief_citations` (`message_id` UNIQUE); `db/queries/chief.py` holds the session/message/citation queries (`close_session` revokes the run's tokens first, then marks it closed, and is once-only; the first message of a session is always `style_prompt`, later ones `human` or `relayed`; `record_citation` is False on a repeat); `run_tokens.lookup_run_token` returns a row revoked or not (None only for empty/unknown), `resolve_run_token` unchanged.
- 06 — `runner/chief_argv.py` (pure) builds the chief's argv (claude `--restricted --tools Bash,Read,Glob,Grep --settings --mcp-config <empty> --strict-mcp-config --session-id`, codex read-only) and the claude settings; `supervisor/chief_session.py::open_chief` writes the session folder (`~/.pathly/chief/<run_id>/`, 0600 files), registers the session, mints a `chief` token on the project board, `create_run`, sends one interactive `TERMINAL_SPAWN` (`submit: false`) and starts a watcher that closes it as `never started` or `tab closed`; `close_chief` revokes, removes the folder, drops the run and lets the watcher go. `--restricted` kept: on claude 2.1.302 the `--settings` hook still fires under it (checked with `-p`).
- 07 — `blueprints/chief/session.py` holds `POST /chief/open` (403 for any live run token, 400 for a bad field or `open_chief`'s `ValueError`, 409 `{error, run_id, tab_id}`, else 201 with `open_chief`'s result, given `sse._broadcast_runner`), `POST /chief/close` (closes with reason `closed from Studio`, then sends `TERMINAL_KILL` for the tab; 403 for a run token) and `GET /chief/session`; `chief_session.normalise_project_root` keys a project's chief on all three and inside `open_chief` (so `/p` and `/p/` are one project, and the stored root is the normalised one); `chief_startup_cleanup()` closes the sessions left open (reason `server restart`) and removes their folders, called by `app.main()` in a `try` that logs and goes on.
- 08 — `http_server/chief_gate.py::chief_gate` (registered after `_log_request`) acts only on a token row with role `chief`: revoked or closed session = 401 `chief session closed`, no URL rule = pass; else `chief_routes.action_for` classes the call from the data table `ROUTE_ACTIONS` ((rule, method) to action; GET = read except `/events/*` and `/db/settings`; posts by `type`, `/runs/<run_id>/<action>` by verb, an acknowledgement of a `to_agent: human` escalation = `answer`) and any unlisted non-GET route, or an action outside `actions_for(tier)`, is 403 `{error, action, tier, allowed}`; a non-empty `prompt_override`/`stage_overrides` also needs `run`, a named `project_root` must resolve to the session's project, a `/comms/post` must be `from: chief`; `chief` joins `_PROJECT_WRITERS` and the default project write list (`test_comms_write_perm`'s pinned set got `"chief"`).
- 08 (round 2) — the gate reads the body as the route will: `chief_gate._bodies` parses with `read_json_body` and with `get_json(silent=True, force=True, cache=False)` and every check runs over each non-empty result, so a BOM, UTF-16 or UTF-32 body no longer hides `project_root` from it; `http_server/chief_project.py` binds every value a route uses as a project (`project_root`, a project board's `scope`, a `/code/query` scope that is not a `(marker)`, the project-decompose `project`) after `normalise_project_root`, and `chief_routes.NAMES_PROJECT_ROOT` (`/runs`, the three run routes, the three decompose routes) refuses a call that names no `project_root`; `/comms/artifacts/section` and `/code/query` stay `read`, and the "Chief gate" section states the residual writes of a read.
- 08 (round 3) — which request fields name a project is data, not branches: `http_server/chief_fields.py::ROUTE_FIELDS` ((rule, method) to `Fields`: `roots`, `names_root`, `scopes` as `ScopeRead(keys, board_key, board, skip_*)`, `paths`/`abs_paths`/`text_paths`, `unbound`, `note`) has an entry for every route a chief can reach (19 POSTs, 65 GET rules), and `chief_project.project_refusal` applies it with one function, reading the query string for a GET and the JSON body for every other route; a route with no entry is 403, and `test_chief_gate.py` walks `app.url_map` for a missing or stale one. Naming `project_root` counts only where the view reads it (a query-string root on a POST does not), a project board's scope is the first truthy non-blank of `scope`/`feature` as the view's `scope or feature` (so `/comms/search` and `GET /comms`, `/comms/tasks`, `/comms/goals` are bound), `/code/query` `target` and a post's `artifact_path` must lie under the session's root (text check, symlinks not followed), and the `/db/*`, `/status` and `/comms/artifacts/section` reads that fall back to another project must name the root; id- or name-addressed calls and the fleet-wide reads (`/db/rollup` `global`, `/telemetry/trends` with a feature, `/metrics`) stay unbound and are listed in the "Chief gate" section.
- 08 (round 4) — the table now says what a view does with a field, verb by verb and name by name: `Fields.names_root_verbs` (`POST /runs/<run_id>/retry` needs a truthy body `project_root`, the other verbs none), `names_root_unless` (`/telemetry/trends` needs the root unless it names a feature), `under_root` (a `feature`/`artifact` the query filters by `project_root` as well is bound by the root, not `unbound`) and `ScopeRead.segment` (the `feature` of `/comms/features/decompose` and the `scope` of a `/comms/run` on a feature or global board is one folder name: no `/`, `\`, `:` or `..`); the two routes refuse it too (`features.py` 400 `invalid_feature`, `runs.py` saves no evaluation under an unsafe scope), the gate being stricter (it refuses `a/b`, the route allows it). The tripwire in `test_chief_gate_tables.py` follows the helpers a view calls (3 levels, by name, heuristic) and a second one fails on a field the table calls an id that a view or helper joins into a path. `/db/stats` and `/telemetry/trends` with a feature are stated fleet-wide in the "Chief gate" section, which also lists the four writes of a read. The chief gate tests are split by concern into `tests/http_api/test_chief_gate*.py` (the Done-when cases stay in `test_chief_gate.py`) with shared fixtures in `chief_gate_support.py`; the walk for a missing or stale `ROUTE_FIELDS` entry is in `test_chief_gate_tables.py`.
- 08 (round 5) — a request string that becomes a filesystem path is held twice, where the gate sees it and where the path is made, with one rule in `scope_names.py` (`is_segment`, `is_project_root`). The gate (`chief_project._scope_refusal`) binds a scope that looks like a path to the session's root on every board (the board mirror reads any `/` scope as a project root, so the declared board is no guard) and makes any other scope off the project board one folder name; `Fields.segments` (the `slug` of `/comms/post`) is a stored field that later becomes a folder. The sinks: `board_mirror.board_from_scope` returns None for a scope that is neither a normalised absolute root nor one plain name (so nothing is queued or written, `write_board_mirror` and `board_mirror_path` refuse it too), and `supervisor/slug.py::ensure_goal_slug` replaces a stored slug that is not a folder name. Not guarded at a sink: `event_mirror.backfill_event_mirrors` (the `feature` of a stored event) and `goal_decomposer` (the `scope` of the goal row), so ticket 14 should check any id that reaches them. Ticket 14's opening sentence is stale (08 binds scopes, files and folder names, not only `project_root`) and `chief_bind` must stay consistent with `ROUTE_FIELDS`.

## Open questions

Settled by the user on 2026-10-13 (the brief's Decided lines). Each line keeps the rejected option
and what would change under it.

- **Rounds.** A) This plan is round one: the tickets here build the server core and prove the
  brief's bar. Round two (§ Round two) is planned as `pathly/features/chief-agent-round-two/` once
  round one is built, with its own map linking back, because its tickets build on round-one code
  that does not exist yet (the chief gate, the session tables, `_agent_question`, the `binding`
  column). Until then the user opens a chief with `POST /chief/open`, with no Chief button,
  `pathly` CLI, overview, inbox badge or re-queue. B) Plan round two now, in this folder, as
  tickets numbered after round one's, written against round-one interfaces that so far exist
  only on paper.
  Decided: A (also planning guide rule 11: past about 12 tickets, plan in rounds). Round one's
  tickets are the same under both. (Round one grew to 17 tickets in the 2026-10-13 revision; the
  four new ones close gaps in round one's own promises.)
- **Directives from the UI.** A) Only a live chief token whose tier has `decide` may post a
  binding directive until the UI token (RRP-2b) exists. B) Also accept a caller that sends no run
  token and the matching `X-Pathly-Secret` (what Studio sends today), posted as `human` with
  `author_source = "none"`, at the cost that any local process that reads
  `~/.pathly/server_secret.txt` and leaves out its run token can post a standing order to every
  role. Decided: A (ticket 12). Under B, ticket 12 adds that path: compare the header with
  `middleware._api_secret` through `hmac.compare_digest`, refuse when no secret is configured.
- **Chief session billing.** The chief tab is a runner tab (`PATHLY_GATE_BILLED` set), so the stop
  hook skips it, and the result callback finds no `RunnerState` for `chief:<run_id>`. A) Round one
  leaves it unbilled and round two gets a ticket that bills it (§ Round two, item 8). B) Leave the
  chief unbilled with no ticket. Decided: A. No round-one ticket depends on it. (2026-10-14: round
  two bills it from the claude transcript that `cli_session_id` locates, not from the tab's output,
  which carries no cost summary for an interactive session.)
- **Planner style.** A) The Planner may post goals and tasks and call the three decompose routes,
  which start plan-only planner or consultation agents, but a body with `prompt_override` or
  `stage_overrides` also needs `run`; it never starts build runs or run control. B) The Planner
  posts goals and tasks only and starts no agent. Decided: A (ticket 08). Under B, ticket 08 maps
  the three decompose routes to `run` instead of `plan`.
- **Cited answers.** A) The cited human message must have been typed in the same chief session
  after the agent asked the question. B) Any human message of the same session, so the user can
  answer ahead of time for the chief to relay. Decided: A (ticket 10). Under B, ticket 10 drops
  its two timestamp comparisons.
- **Chief and HQ.** A) The Chief button sits in the top bar next to the HQ toggle, and HQ stays
  as it is. B) The Chief replaces HQ, which survives only as the no-engine fallback (the brief's
  line). Decided: A (2026-10-14). Round one is the same under both. Under B, round two would also
  route the HQ toggle to the Chief and decide where HQ's `AgentQuestionCard` goes.

Not known yet (later tickets or round two settle them):

- Codex human-message capture: codex has a UserPromptSubmit hook, but only through user or
  project config files with trust review. Until round two decides, a codex chief can open, read
  and act, but every relayed answer and every human-escalation acknowledgement is refused, and it
  has no permission file like claude's (only its read-only sandbox). The launcher must say so when
  it offers codex.
- Whether `--strict-mcp-config` with an empty `--mcp-config` behaves as the docs suggest on the
  installed claude: ticket 06 checks it and records the result in `learnings.md`.
- A codex chief runs with `--sandbox read-only`, so each `pathly` command asks for approval; the
  docs do not say whether an approved command can reach `127.0.0.1`. Round two's CLI ticket checks
  it on a real codex before the launcher offers codex.
- UserPromptSubmit also fires on scheduled tasks, background subagents reporting back and
  messages another session sends. The chief's `--tools` list leaves out `Agent`, `CronCreate`
  and `Workflow`, which removes the first two, and the session id check (ticket 09) keeps any
  other process from recording. A message another claude session (for example a worker) sends
  into the chief still arrives in the chief's own process with the chief's session id. Ticket 09
  measures whether the hook input tells it apart; if it does, it is stored as `relayed` and can
  never be cited; if not, it is recorded as human and this question stays open (can
  cross-session messaging be turned off for the chief?).
- The UI token (RRP-2b) is still missing: a chief that drops its token is unrestricted on
  loopback, `/events/spawn` still carries every spawn's token and needs no secret, and Studio
  cannot post or retire a binding directive until it lands.
- Still outside this plan from role-read-policy: agent curls to `/code/query` and
  `/record_phase` send no token, and `provenance.stamp()` stores the role as given.
- The stale-directive re-queue (round two) matches directives to roles by `_spawn_role`, which
  returns `build` for quick-fix/debug FIXING spawns while directives say `builder`
  (role-read-policy ticket 10 open item).


## Brief coverage

Every In-scope line of the brief, and where it is built. `R2-n` is item n of § Round two (round
two numbers its own tickets from 01).

| Brief, In scope | Round one (tickets) | Round two (items) |
|---|---|---|
| Chief button and tab replacing HQ; engine choice; style choice; prompt pasted, not sent | 06 interactive `TERMINAL_SPAWN` with `submit: false`, engines `claude` and `codex`; 07 `POST /chief/open` | R2-4 Studio pastes without Enter; R2-5 Chief button next to the HQ toggle, hosting `PromptActionConfig` (HQ stays: § Open questions, "Chief and HQ") |
| Chief styles: a preset plus the actions it may use, enforced through the token; Status, Planner, Operator | 04 tiers and preset-to-tier; 06 tier bound to the session; 08 the gate; 17 built-in texts and the un-editable `chief-connect` fragment | R2-3 richer preset texts; R2-5 `chief` Library category, saving `tier:` |
| The chief's identity: `chief` token for the style, `PATHLY_RUN_TOKEN` only, revoked on close | 05 tables; 06 mint and close; 07 routes and restart cleanup | R2-4 a vitest that the chief tab gets `PATHLY_RUN_TOKEN` (Studio already exports it for runner tabs) |
| Read side: `pathly` command set, one overview call through the role-read-policy for `chief` | 08 the chief may read every GET except `/events/*` and `/db/settings`; 17 `pathly api` | R2-1 friendly `pathly` commands; R2-2 `GET /chief/overview` |
| Write side: only existing routes, refused outside the style's list, never opens agent CLIs | 06 restricted start: no user or project settings, tools limited to Bash, Read, Glob and Grep, no MCP servers; 08 deny by default, tested over every route; 14 project binding by id; 15 ceilings; 13 scenario 2 | R2-1 the write commands |
| Agent questions and decisions: badge, inbox on open or when asked, no LLM turns while away | 10 the pending question kept on the run state | R2-2 `GET /chief/inbox`; R2-3 presets read the inbox on open; R2-6 badge |
| Verifiable relayed answers | 09 human messages recorded from the chief's own session; 10 the cite rule (Pathly relays the cited text, once; human escalations) | none |
| Standing directives: binding by role, survive acknowledgement, chief token (or the UI), re-queue | 11 injection by role in a standing-orders block; 12 `POST /comms/directives`, no edits; 16 only the chief retires one, hydration cannot forge one | R2-7 re-queue; the UI path waits for RRP-2b (user's decision, § Open questions) |
| The three run-token holes | 01 SSE; 02 `/db/query`; 03 `/comms/edit` | none |
| The bar | 13 | R2-9 round-two acceptance |

## Round two (outlined; planned once round one is built)

Planned as `pathly/features/chief-agent-round-two/` with its own map linking back here (the
user's decision for rounds), in two parts, each with its own acceptance, so neither grows past
about 12 tickets (planning guide rule 11):

- **2a, the chief's hands and signal (server and CLI):** items 1, 2, 3, 8 and 10. At the end of
  2a the chief is fully usable from a tab opened with `POST /chief/open`, sees its inbox, is
  billed, and can report spend.
- **2b, Studio (the launcher and the button):** items 4, 5, 6 and 7. At the end of 2b the user
  opens the chief from the Chief button and never needs `POST /chief/open`.
- Item 9 splits: 2a's acceptance and docs close 2a; 2b's close 2b.

Items, numbered as § Brief coverage cites them:

1. Friendly `pathly` commands on top of round one's `pathly api` (ticket 17, which already sends
   the token and refuses to run without it). Commands: `overview`, `inbox`, `goals`, `runs`, `board`, `search`,
   `agents`, `goal create`, `decompose`, `start`, `stop`, `control`, `answer --cite`,
   `decide [--binding --to]`, `post`, `help`.
2. `GET /chief/inbox` (pending agent questions from `RunnerState._agent_question`, pending
   decisions, open escalations, a count) and `GET /chief/overview` (agents and model policy,
   goals, running agents, features and tasks, inbox), board rows filtered through
   `read_policy.policy_predicate` for role `chief`.
3. Richer preset texts for Status, Planner and Operator (round one's ticket 17 has short ones
   using `pathly api`), rewritten against the friendly commands, each telling the chief to read
   `pathly inbox` when it starts. The fixed rules stay in the `chief-connect` fragment, which is
   rewritten against the friendly commands too; the style texts carry only the style.
4. Studio paste-without-Enter: `TerminalSpawnListener` reads `submit === false` and passes a
   `pasteOnly` spawn meta through preload, `global.d.ts` and `terminal.ts` to
   `promptInjector.attachStartupHandling`, which pastes and sends no `\r`; a vitest with a fake
   `IPty`, and one that `buildSpawnEnv` exports `PATHLY_RUN_TOKEN` for the interactive chief tab
   (it already does for runner tabs; the test pins it). Also decide whether the chief tab counts
   against the interactive cap of 5.
5. Chief button and launcher, next to HQ, which stays as it is (§ Open questions, "Chief and HQ").
   The button goes in `studio/src/renderer/src/components/topbar/index.tsx`'s right group, between
   the CLI Engines button (`cliMonitorWrap`) and the HQ toggle (`topbar-chat-toggle`). It shows
   "Chief" and the inbox count (item 6). Below `TOPBAR_COMPACT_BREAKPOINT` (1060 px; the same
   `compact` flag `ProjectSelector` gets) it shows only its icon and the count. The count badge
   follows the CLI Engines dot (`cliMonitorWrap`/`cliDot` in `TopBar.module.css`). The button hosts
   the launcher: a `PromptActionConfig` (pattern: `CommentConfigButton`), engines `claude` and
   `codex`, open / show tab on 409 / close, the tab label carrying the tier, "Save current as
   prompt" adding `tier:` front matter, `'chief'` in the Library `FIXED_CATEGORIES` and its Python
   mirror `skills/prompt_files.CATEGORIES` (the server already reads and writes any
   `<category>/<name>`). When `terminal:preflight` finds no engine, the launcher says so and points
   to HQ. HQ, its toggle and `chat_agent.py` do not change. Before opening, the launcher shows what
   the chief will be: the tier as a badge, the style text, and the `chief-connect` fragment folded
   under one line (the 2026-10-14 external assessment, § 3).
6. Inbox badge on the Chief button (polls `/chief/inbox`; no LLM turns).
7. Stale-directive re-queue: `supervisor/directive_requeue.py`, called from the single-spawn branch
   of `fan_out.run_stage`, re-runs a stage once per binding directive newer than its spawn
   (at most twice) instead of advancing.
8. Bill the chief's own session (the user's decision for cost). Not from the tab's output: an
   interactive claude tab prints no JSON cost summary, only screen output. And not from the
   user's stop hook, which skips runner tabs (`PATHLY_GATE_BILLED`) and which restricted mode
   does not load. Read the claude transcript instead: ticket 06 stored `cli_session_id`, so the
   file is `~/.claude/projects/<cwd slug>/<cli_session_id>.jsonl`. Sum `usage` over assistant
   messages, counting each message id once (one message can span several lines), price it with
   `db/pricing.py`, and write an `AGENT_DONE` plus `BILLING_UPDATE` keyed by the chief's `run_id`
   at close. For a running total while the chief is open, add a Stop hook to the chief's own
   settings file that posts the same sum. Check the transcript's field names on the installed
   claude first; they are not a documented contract. A codex chief needs its own source.
9. Round-two acceptance, `studio/CLAUDE.md`, `README.md` and `docs/WHAT_IS_PATHLY.md` (one
   acceptance for 2a, one for 2b).
10. Report daycap's machine-wide daily spend (`pathly spend` over a read-only route): the draft
    in `round-two-drafts/daycap-spend-report.md` (round-one ticket 18 until 2026-10-14), with the
    corrections at its top. Round one's ticket 19 settles what daycap can enforce first.
