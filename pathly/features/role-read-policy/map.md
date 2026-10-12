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
