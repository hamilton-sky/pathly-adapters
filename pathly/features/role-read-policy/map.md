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

## Open questions

- SPEC § F Q1: ship the `reviewer`/`tester` walls as built-in defaults, or as an opt-in preset?
  Planned default: built-in (ticket 01). Only takes effect once a later plan wires the predicate.
- Should a revoked or unknown token be refused on write (`401`), or stored as `author_source=none`?
  Planned default: stored as `none` and logged, so a run that outlives its token does not lose a
  post. Ticket 09.
- 01 — `runner/read_policy.py` holds policy shape, built-in walls, `policy_predicate` and pure `row_allowed`; stdlib only, tested to agree.
- 01 — read-policy core in runner/read_policy.py: row_allowed and policy_predicate agree; no own-post exemption without a caller run id; anonymous = discovery/status/nudge/warning by builder.
- 02 — resolve_read_policy(conn, role, feature, project_root=''): first stored row wins (no exclude_* = allow-all), else BUILTIN_DEFAULTS, None = anonymous; get_board_scope untouched.
