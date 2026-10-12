# Map: role-read-policy

## Destination

Every board read an agent makes goes through one read policy compiled to SQL, and every board
write is stamped by the server with who really wrote it. This plan covers SPEC.md phases P1–P3
(implementation tickets RRP-1, RRP-2, RRP-3 in IMPLEMENTATION_PLAN.md): the policy core with its
built-in defaults, a per-run token minted at spawn and carried by both spawn hosts and the
fragments, the server resolving the caller from that token, and `author_role` / `author_run_id` /
`author_source` on every `comms_messages` row (existing rows backfilled as `legacy`). Wiring the
policy into the read paths (RRP-4, RRP-5), the UI token (RRP-2b), pair binding (RRP-6) and
visibility (RRP-7) are later plans. Nothing is withheld from any agent by this plan: reads are
unchanged, so it ships with no behaviour change for agents.

**What comes next.** When this plan reaches `DONE`, the chief-agent plan
(`pathly/features/chief-agent/`) starts: `/feature-flow chief-agent auto`, on the same branch, so
its Smoke finds the modules built here. RRP-2b and RRP-4..8 come after chief-agent, as a later
plan.

**The bar.** `python -m pytest tests/ -q -p no:cacheprovider` passes in full, and
`python -m pytest tests/comms_board/test_rrp_acceptance.py -q` passes: a spawned stage's
`TERMINAL_SPAWN` payload carries a token that resolves to its run and role; a post made with that
token and `from: "explorer"` is stored as `author_role=builder, author_source=token`; a post with
no token is `author_source=none`; and `policy_predicate` for `reviewer` excludes that builder row
while `row_allowed` agrees. Ticket 10 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py role-read-policy` (with `FLOW_DIR=pathly/features`). Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py role-read-policy --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Design is in `SPEC.md` (§ C1–C4, C8). `USER_STORIES.md` and `IMPLEMENTATION_PLAN.md` are the
  human-facing plan; the tickets here are what gets built.

## Decisions so far

- Plan — the token is minted in `_record_spawn_identity` (the one chokepoint every runner, board
  and goal spawn passes), carried as `run_token` in the `TERMINAL_SPAWN` payload, and put in the
  child env as `PATHLY_RUN_TOKEN` by both spawn hosts. Minting in `task_prompt.py` / `board_run.py`
  would miss FSM stages.
- Plan — the token is stored hashed (sha256) in `run_tokens`; the raw value exists only in the
  payload and the child env. The `/events/spawn` SSE stream carries it, which SPEC C0 accepts
  (default paths walled, bypass visible).
- Plan — this plan stamps and resolves identity but withholds nothing. `read_policy.mode` is not
  read by any query yet; RRP-4 starts that in `warn`.
- Plan — the UI token (RRP-2b) is not in this plan; until it lands the Studio UI posts with no run
  token and its rows are `author_source=none`, which only matters once `enforce` exists.

- 01 — `runner/read_policy.py`: `ReadPolicy`, `BUILTIN_DEFAULTS` (reviewer/tester/chief/anonymous), `row_allowed` and `policy_predicate` agree on a generated matrix; never-withheld types are dropped from the predicate.
- 02 — `resolve_read_policy(conn, role, feature, project_root='')`: stored per-role/per-feature row wins (no exclude_* keys = allow-all content, no fall to built-in), else built-in copy, `None` -> anonymous, unknown role -> allow-all.

## Open questions

- SPEC § F Q1: ship the `reviewer`/`tester` walls as built-in defaults, or as an opt-in preset?
  Planned default: built-in (ticket 01). Only takes effect once a later plan wires the predicate.
- Should a revoked or unknown token be refused on write (`401`), or stored as `author_source=none`?
  Planned default: stored as `none` and logged, so a run that outlives its token does not lose a
  post. Ticket 09.
- 03 — `db/queries/run_tokens.py`: `mint_run_token` (token_urlsafe(32), only sha256 stored), `resolve_run_token` (dict or None if unknown/empty/revoked), `revoke_run_tokens(run_id)`; table created by `db/migrations_provenance.py::add_run_tokens`, called from `_add_additive_migrations`.
- 04 — token minted by `terminal_identity._issue_spawn_token` as the first statement inside `_run_stage_via_terminal`'s try, sent as `run_token` in TERMINAL_SPAWN, revoked in `_settle_spawn_identity`; role = agent_map role (FSM), `builder` (sched- loop task), current_state (board run); feedback spawns carry the stage role.
- 05 — both spawn hosts put `PATHLY_RUN_TOKEN` in the child env from the payload's `run_token` (set only when a non-empty string; an inherited value is stripped); Studio via `terminal/spawnEnv.ts::buildSpawnEnv` and a 6th `runToken` arg on `terminal:register-runner`.
- 06 — `http_server/run_identity.py::caller_identity(request)` returns `CallerIdentity` (`run` from a live `X-Pathly-Run-Token`, else `anonymous`; unknown/revoked logged at info with remote addr; body role/run_id/from never read); the header is in both CORS allow lists.
- 07 — every `curl` to `8765/comms` under `core/` sends `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` (56 curls, 21 files); `tests/consistency/test_fragments_run_token.py` fails on a missing one; 9 composed snapshots updated by exactly the header lines; `GET`/`POST http://` pseudo-requests in `development/build.md` and `fragments/consult.md` are not curl and untouched; no tracked generated adapter copies exist.
- 07 (review round 1) — bare `VERB [http://127.0.0.1:8765]/comms/...` pseudo-requests in 10 `.md` files (drain-dag, team/build, team/review, development/build, development/review, consult, custom/testing, plan, goalize, consolidate) each got one `Send -H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN" ...` instruction line; the test now fails on a `.md` file with such a line and no instruction line outside a curl; 6 snapshots gained only those lines. For ticket 09: `supervisor/board_run.py:416` builds the board-run prompt in Python and tells the agent to `POST http://127.0.0.1:8765/comms/post` with a JSON body and no token header (outside `core/`, so ticket 07's test cannot see it); every board-run agent that follows it posts as anonymous until a header line is added there.
- 08 — `db/migrations_provenance.py::add_comms_provenance(conn)` (called last in `_add_additive_migrations`) adds `author_role`/`author_run_id`/`author_source` to `comms_messages` and backfills every NULL-source row as `legacy` (supervisor/system -> `system`; else the role of the `agent_invocations` row its `run_id` joins, ignoring NULL roles; else `from_agent`); `author_run_id` stays NULL; a second run touches no row. Until ticket 09 stamps writes, new rows have NULL source and are relabelled `legacy` on the next start.
- 08 (review round 1) — `add_comms_provenance` now creates `idx_agent_invocations_run_id` first (the backfill's join scanned `agent_invocations` once per message; 20k x 20k went from ~19 s to 0.05 s) and tolerates a concurrent "duplicate column name" on its ALTERs (any other OperationalError still raises). For ticket 09: the backfill relabels every row left with a NULL `author_source` as `legacy` on each start, so 09 must stamp EVERY `comms_messages` writer (token / system / none); a writer it misses will be recorded as `legacy`, not `none`, and the gap will not show.
- 09 — `runner/provenance.py` (existing git-provenance module) gained `stamp(identity)` (run token -> role/run_id/`token`, anything else -> `none`) and `system_stamp()`; `post_message` takes the three author kwargs and stores a missing source as `none`, never NULL; `/comms/post` passes `stamp(caller_identity(request))`, every server-internal `post_message` caller passes `**system_stamp()` except 7 calls in the size-frozen `comms/goals.py`/`project.py`/`settings.py` plus `answer_question`/`promote_message` (left on the `none` default, on the test's allow-list); the sentinel INSERT in `comms_artifacts.py` is `system`; `board_run.py` and `comms_catalog.py` instruction strings now carry the `X-Pathly-Run-Token` header.
- 09 (review round 1) — `stamp()` returns `none` (and logs a warning naming the run) for a run token with no role; `runner/provenance.post_system` (post_message + system stamp) is imported `as _post_message` by the size-frozen `comms/goals.py`/`project.py`/`settings.py`, so their 7 status posts are `system` with no added line; the `/code/query` log row, the `/record_phase` row and the context-pull trail are stamped from the caller's token (their content is the caller's); `hydrate_board` runs `add_comms_provenance` after importing a snapshot; `promote_message` copies the source's `author_*`; `db/provenance_values.py` holds `AUTHOR_SOURCES` and the `system` constants once and `post_message` raises `ValueError` on an unknown source; the scans now catch aliased/indirect `post_message`, any-case/quoted/qualified `INSERT`/`REPLACE`, and body-derived stamp values; the test allow-list is down to `answer_question` and `promote_message`.
- 10 — `tests/comms_board/test_rrp_acceptance.py` (7 tests) drives the bar through the real pieces: a `team` flow BUILDING and then REVIEWING stage spawned through `supervisor/terminal.py` (only the spawn host is a fake broadcaster), the Flask app, the real policy. The payload token resolves to the stage's run and role; a builder-token post labelled `explorer`, with the reviewer's run id in its body, is stored `builder/<run>/token`; a header-less post is `none`; for the reviewer's own identity `policy_predicate` withholds exactly those two rows and `row_allowed` agrees on every row, while a builder `decision` stays; the token is `None` after settle and a late post is `none`; a restart's backfill leaves the stamps alone; `GET /comms` still returns every row. Living docs: `src/pathly_orchestrator/CLAUDE.md` (new "Who wrote a board row, and who may read it" section, `run_tokens.py` / `read_policy.py` / `TERMINAL_SPAWN.run_token` entries, the "keeps the caller's role" claim reworded to what the code does) and a `CHANGELOG.md` entry; root `CLAUDE.md` unchanged because its comms-board paragraph names no read rule.
- 10 (open item for the next plan, RRP-4) — `supervisor/terminal_identity.py::_spawn_role` mints a role from the `agent_map` entry (via `_SKILL_AGENT_ROLE`, else its last path segment), not from the flow's `role_map`. Run over the 10 packaged flows the two disagree at 13 (flow, state) pairs, among them quick-fix and debug FIXING (`build`, where `role_map` says `builder`), debug VERIFYING (`verify`, `reviewer`), the consultation PLANNING states (`plan` / `feature-decompose` / `project-decompose`, `planner`), RESEARCHING (`research`, `web-researcher`) and team RETRO (`planner`, `retro`). A row stamped `build` is not matched by the built-in `exclude_authors: ["builder"]`, so the reviewer and tester walls would let those builders' posts through. Decide which table is the role vocabulary before the predicate is wired; only `team` BUILDING / REVIEWING (builder / reviewer) is proved so far.
- 10 (open item, RRP-4) — `POST /db/query` checks only the first word of the SQL and `with` is an allowed first word, so `WITH t AS (SELECT 1) INSERT INTO ...` runs on the shared connection. Probed on a scratch DB (never the real one): it created a `run_tokens` row and a `comms_messages` row stamped `explorer/run-x/token`, so provenance can be forged and tokens minted from one HTTP call. It needs `PRAGMA query_only` on the connection that serves the route, or an authorizer, before any wall relies on `author_source`.
- 10 (open item, RRP-4) — `POST /comms/edit` rewrites a row's `text` (`update_message_text` touches only `text`, and the handler reads no caller identity), so anyone can change what a builder wrote and the row keeps the builder's `token` stamp. Decide whether an edit by another caller must re-stamp the row or be refused.
- 10 (open item, RRP-4) — `stamp()` stores the role exactly as it was minted (only a blank role is refused), and `row_allowed` / `policy_predicate` compare exact strings, so a role minted `Builder` or `builder ` would not match `exclude_authors: ["builder"]`. Normalise case and whitespace once, where the role is minted or stamped, and in the setting keys.
- 10 (open item, RRP-4) — the agent-facing `curl`s to `/code/query` (`fragments/code-query.md`) and `/record_phase` (`utilities/log-phase.md`, `development/design.md`, `planning/storm.md`) send no `X-Pathly-Run-Token`, so those rows are stored `none` today (the `/code/query` row is a `discovery`, which the reviewer wall would withhold as unverified). Ticket 10 only corrected the living doc; the skill files and ticket 07's scan (which looks at `8765/comms` only) need the header added.
- 10 (review round 1, open item for RRP-4) — the raw run token rides in the `TERMINAL_SPAWN` payload, and `sse._broadcast_runner` sends that whole payload to three places: the topic's `/events/runner` clients, every `/events/spawn` client and (the payload has a `run_id`) the `/events/runs` clients of that run. None of the three needs credentials (`middleware._log_request` skips the secret check for every `/events/` path), so any client that can subscribe to those streams can read a live token until the spawn settles (`_settle_spawn_identity` revokes it); the Plan line above names only `/events/spawn`. Checked: a probe with a queue on each registry saw the marker token on exactly those three and not on `/events/comms`, `/events/menu` or `/events/stream`. The only code that reads the payload's `run_token` field is the two hosts' (`pty_host/host.py`, and Studio's `TerminalSpawnListener`, which hands it on to `buildSpawnEnv`), both on `/events/spawn`, so strip it from every channel but `/events/spawn`, or hand it to the host another way, before any wall relies on `author_source="token"`; stripping alone leaves `/events/spawn` readable by any client.
- 10 (review round 1, own sweep) — corrects the first `10 —` line above, which says only the spawn host is a fake broadcaster: that broadcaster also plays the agent (it posts with the payload's token), so the hosts' `PATHLY_RUN_TOKEN` export and the fragments' header are not links the acceptance test drives; `tests/runner_supervisor/test_pty_host.py`, `studio/src/main/ipc/terminal/spawnEnv.test.ts` and `tests/consistency/test_fragments_run_token.py` pin those. One more open item for RRP-4, checked with a probe: `POST /comms/hydrate` (`board_mirror_hydrate.hydrate_board`) inserts the rows of a project's `BOARD.json` as-is into an empty board, so a snapshot row carrying `author_source="token"` is stored as written and only a row with no stamp becomes `legacy`. Decide whether hydration keeps the stamps in the file or resets them before a wall relies on `token`.
