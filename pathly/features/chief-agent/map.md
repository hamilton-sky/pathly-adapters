# Map: chief-agent

## Destination

Round one (this plan) leaves the chief's server core in place and proven. `POST /chief/open`
resolves a tier from the chosen preset, mints a `chief` run token, writes the session's claude
settings (a UserPromptSubmit hook and permission rules), registers the session and sends an
interactive `TERMINAL_SPAWN` that asks the host to paste the prompt without sending it; closing
the tab or restarting the server revokes the token. A `before_request` chief gate refuses every
call the session's tier does not allow, every unlisted write, any other project, and any revoked
chief token. Human messages typed in a claude chief tab are recorded, and a chief-token answer to
an agent must cite one. Binding directives keep reaching the prompts of the roles they target
after an acknowledgement, and only a chief token may post one until the UI token exists. The three
run-token holes are closed. The rest of the brief is outlined below as round two: the `pathly`
command set, the overview and inbox calls, the built-in preset texts, Studio pasting without
Enter, the Chief button replacing HQ, the inbox badge, the stale-directive re-queue and billing the
chief's own session. The split follows the user's decision for rounds; § Brief coverage
maps every In-scope line of the brief to where it is built.

**The bar.** `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider`
passes with a fake spawn host: opening the chief mints a `chief` token for the chosen style and
spawns an interactive tab with the style's prompt pasted and not sent; with the Operator style the
chief's API calls create a goal and start a run that Pathly spawns through its normal spawn path;
a Status-style token is refused on a write; an agent question is pending until it is answered with
a cited human message, and an uncited one is refused; a binding decision reaches the next builder,
reviewer and tester prompts after an acknowledgement; the raw run token no longer appears on
`/events/runner` or `/events/runs`. And `python -m pytest tests/ -q -p no:cacheprovider` passes in
full. Ticket 13 runs both.

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
- Design is in `spec.md`. The previous chief plan (git `72292b35:pathly/features/chief-agent/`) is
  superseded; its directive, answer-relay and project-writer parts are reused here.
- Hard rules from `CLAUDE.md`: 400-line ratchet (`scripts/check_file_size.py`), layer rule
  `db -> runner -> supervisor -> http_server` with lazy imports inside routes, new endpoints in a
  matching or new blueprint domain, living docs in the same change, unique test basenames and
  `python scripts/gen_test_index.py` after adding tests. CI also runs `bandit -r src/ -ll -x
  src/pathly_data/`: no f-string or `+` SQL building in new code (use `IN (SELECT value FROM
  json_each(?))`), never `# nosec`. The full suite runs on Python 3.11, 3.12 and 3.13.

## Decisions so far

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

## Open questions

Settled by the user on 2026-10-13 (the brief's Decided lines). Each line keeps the rejected option
and what would change under it.

- **Rounds.** A) This plan is round one: the 13 tickets here build the server core and prove the
  brief's bar. Round two (§ Round two) is planned as `pathly/features/chief-agent-round-two/` once
  round one is built, with its own map linking back, because its tickets build on round-one code
  that does not exist yet (the chief gate, the session tables, `_agent_question`, the `binding`
  column). Until then the user opens a chief with `POST /chief/open`, with no Chief button,
  `pathly` CLI, overview, inbox badge or re-queue. B) Plan round two now, in this folder, as
  tickets 14 to 22, written against round-one interfaces that so far exist only on paper.
  Decided: A (also planning guide rule 11: past about 12 tickets, plan in rounds). Round one's
  tickets are the same under both.
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
  chief unbilled with no ticket. Decided: A. No round-one ticket depends on it.
- **Planner style.** A) The Planner may post goals and tasks and call the three decompose routes,
  which start plan-only planner or consultation agents, but a body with `prompt_override` or
  `stage_overrides` also needs `run`; it never starts build runs or run control. B) The Planner
  posts goals and tasks only and starts no agent. Decided: A (ticket 08). Under B, ticket 08 maps
  the three decompose routes to `run` instead of `plan`.
- **Cited answers.** A) The cited human message must have been typed in the same chief session
  after the agent asked the question. B) Any human message of the same session, so the user can
  answer ahead of time for the chief to relay. Decided: A (ticket 10). Under B, ticket 10 drops
  its two timestamp comparisons.

Not known yet (later tickets or round two settle them):

- Codex human-message capture: codex has a UserPromptSubmit hook, but only through user or
  project config files with trust review. Until round two decides, a codex chief can open, read
  and act, but every relayed answer is refused.
- A codex chief runs with `--sandbox read-only`, so each `pathly` command asks for approval; the
  docs do not say whether an approved command can reach `127.0.0.1`. Round two's CLI ticket checks
  it on a real codex before the launcher offers codex.
- UserPromptSubmit also fires on scheduled tasks, background subagents reporting back and messages
  another session sends. Denying `Agent`, `CronCreate` and `Workflow` removes the first two; a
  cross-session message from another claude session (for example a worker) would still be
  recorded as human. Round two should check whether the hook input marks the source or whether
  cross-session messaging can be turned off for the chief session.
- The UI token (RRP-2b) is still missing: a chief that drops its token is unrestricted on
  loopback, `/events/spawn` still carries every spawn's token, and Studio cannot post a binding
  directive until it lands.
- The stale-directive re-queue (round two) matches directives to roles by `_spawn_role`, which
  returns `build` for quick-fix/debug FIXING spawns while directives say `builder`
  (role-read-policy ticket 10 open item).
- When the Chief button replaces HQ, where do HQ's `AgentQuestionCard` and `FlowControlBar` live?
  Round two keeps HQ reachable as the no-engine fallback; whether they also move elsewhere is a
  round-two decision.

## Brief coverage

Every In-scope line of the brief, and where it is built. `R2-n` is item n of § Round two (round
two numbers its own tickets from 01).

| Brief, In scope | Round one (tickets) | Round two (items) |
|---|---|---|
| Chief button and tab replacing HQ; engine choice; style choice; prompt pasted, not sent | 06 interactive `TERMINAL_SPAWN` with `submit: false`, engines `claude` and `codex`; 07 `POST /chief/open` | R2-4 Studio pastes without Enter; R2-5 Chief button on `PromptActionConfig` replacing HQ, `chat_agent.py` fallback |
| Chief styles: a preset plus the actions it may use, enforced through the token; Status, Planner, Operator | 04 tiers and preset-to-tier; 06 tier bound to the session; 08 the gate | R2-3 built-in preset texts; R2-5 `chief` Library category, saving `tier:` |
| The chief's identity: `chief` token for the style, `PATHLY_RUN_TOKEN` only, revoked on close | 05 tables; 06 mint and close; 07 routes and restart cleanup | R2-4 Studio exports `PATHLY_RUN_TOKEN` in the chief tab |
| Read side: `pathly` command set, one overview call through the role-read-policy for `chief` | 08 the chief may read every GET except `/events/*` and `/db/settings` | R2-1 `pathly`; R2-2 `GET /chief/overview` |
| Write side: only existing routes, refused outside the style's list, never opens agent CLIs | 06 no spawn tools in the chief's settings; 08 deny by default; 13 scenario 2 | R2-1 the write commands |
| Agent questions and decisions: badge, inbox on open or when asked, no LLM turns while away | 10 the pending question kept on the run state | R2-2 `GET /chief/inbox`; R2-3 presets read the inbox on open; R2-6 badge |
| Verifiable relayed answers | 09 human messages recorded; 10 the cite rule | none |
| Standing directives: binding by role, survive acknowledgement, chief token (or the UI), re-queue | 11 injection by role; 12 `POST /comms/directives`, no edits | R2-7 re-queue; the UI path waits for RRP-2b (user's decision, § Open questions) |
| The three run-token holes | 01 SSE; 02 `/db/query`; 03 `/comms/edit` | none |
| The bar | 13 | R2-9 round-two acceptance |

## Round two (outlined; planned once round one is built)

Planned as `pathly/features/chief-agent-round-two/` with its own map linking back here (the
user's decision for rounds). Its items, in order:

1. `pathly` command set: `pathly_orchestrator/chief_cli.py` and a `pathly` entry in
   `[project.scripts]`, stdlib HTTP, sending `X-Pathly-Run-Token` from `PATHLY_RUN_TOKEN` and
   refusing to run without it. Commands: `overview`, `inbox`, `goals`, `runs`, `board`, `search`,
   `agents`, `goal create`, `decompose`, `start`, `stop`, `control`, `answer --cite`,
   `decide [--binding --to]`, `post`, `help`.
2. `GET /chief/inbox` (pending agent questions from `RunnerState._agent_question`, pending
   decisions, open escalations, a count) and `GET /chief/overview` (agents and model policy,
   goals, running agents, features and tasks, inbox), board rows filtered through
   `read_policy.policy_predicate` for role `chief`.
3. Built-in preset texts for Status, Planner and Operator, written against the `pathly` commands,
   each telling the chief to read `pathly inbox` when it starts.
4. Studio paste-without-Enter: `TerminalSpawnListener` reads `submit === false` and passes a
   `pasteOnly` spawn meta through preload, `global.d.ts` and `terminal.ts` to
   `promptInjector.attachStartupHandling`, which pastes and sends no `\r`; a vitest with a fake
   `IPty`, and one that `buildSpawnEnv` exports `PATHLY_RUN_TOKEN` for the interactive chief tab.
5. Chief button and launcher replacing HQ: a `PromptActionConfig` host (pattern:
   `CommentConfigButton`), engines `claude` and `codex`, open / show tab on 409 / close, the tab
   label carrying the tier, "Save current as prompt" adding `tier:` front matter, `'chief'` in the
   Library `FIXED_CATEGORIES` and its Python mirror `skills/prompt_files.CATEGORIES` (the server
   already reads and writes any `<category>/<name>`), and HQ (`chat_agent.py`) as the fallback when
   `terminal:preflight` finds no engine.
6. Inbox badge on the Chief button (polls `/chief/inbox`; no LLM turns).
7. Stale-directive re-queue: `supervisor/directive_requeue.py`, called from the single-spawn branch
   of `fan_out.run_stage`, re-runs a stage once per binding directive newer than its spawn
   (at most twice) instead of advancing.
8. Bill the chief's own session: the result handler (`blueprints/runner/api_lifecycle.py`) parses
   the chief tab's output for `chief:<run_id>` and writes its cost, since the stop hook skips runner
   tabs (the user's decision for cost).
9. Round-two acceptance, `studio/CLAUDE.md`, `README.md` and `docs/WHAT_IS_PATHLY.md`.
