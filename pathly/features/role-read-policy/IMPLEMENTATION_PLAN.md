# Implementation Plan — Role Read Policy

Each ticket maps to one board task. Design: [SPEC.md](SPEC.md); acceptance:
[USER_STORIES.md](USER_STORIES.md).

Layering: `db/ → (none)`, `runner/ → db`, `supervisor/ → db, runner`, `http_server/ → all`
(lazy imports inside handlers). **400-line ratchet:** several files this touches are close to the
limit (`runner/comms_context.py` 394, `blueprints/comms/messages_write.py` 386,
`blueprints/comms/messages_crud.py` 382, `studio/src/main/ipc/terminal.ts` 391) and
`db/migrations.py` (438) is frozen and may only shrink. So every ticket below adds **new files**
and leaves only a one- or two-line call site in those files.

## Ticket map

```
RRP-1 policy core ──┬─► RRP-4 push path (warn) ──┐
RRP-2 run token ────┼─► RRP-3 author stamping ───┼─► RRP-5 pull paths ─► RRP-6 pair binding ─► RRP-8 enforce
                    └─► RRP-2b UI token ─────────┘                       RRP-7 visibility ──┘
```

Minimum the chief-agent work depends on: **RRP-1, RRP-2, RRP-3** (SPEC D, "Sequencing").
Build order: RRP-1..3 (feature-flow `tasks/01..10`) → chief-agent (its `tasks/01..13`, started as
soon as this plan reaches DONE) → RRP-2b, RRP-4..8 as a later plan.

---

## RRP-1 — Policy core (P1) · P0 · Low

**Goal:** one policy, compiled to SQL, with built-in defaults.

New files
- `src/pathly_orchestrator/runner/read_policy.py`
  - `ReadPolicy` (typed dict: tiers, `exclude_types`, `exclude_authors`)
  - `BUILTIN_DEFAULTS` for `reviewer`, `tester`, `chief`, `anonymous` (union of walls), SPEC C2
  - `NEVER_WITHHELD_TYPES = {"decision", "constraint", "goal", "task"}` + governance rule
  - `policy_predicate(policy, caller_run_id) -> (where_sql, params)`
  - `row_allowed(row, policy, caller_run_id) -> bool` (test/counter twin)
  - `resolve_read_policy(role, feature, conn)`: per-role row → per-feature row → built-in → all

Changed files
- `db/queries/app_settings.py` — `get_board_scope` keeps its contract; `resolve_read_policy`
  wraps it (no new logic in this file beyond accepting the two new keys).

Tests (`tests/<comms domain>/test_read_policy.py`)
- Every rule in SPEC C1/C2; governance and own-run rows never withheld; unverified author of an
  excluded type withheld; `policy_predicate` and `row_allowed` agree on a generated case matrix.

Done when: tests green; nothing calls the module yet (no behaviour change).

---

## RRP-2 — Run token (P3, token half) · P0 · Med

**Goal:** every spawned agent carries an unforgeable identity.

New files
- `src/pathly_orchestrator/db/queries/run_tokens.py` — table `run_tokens(token PK, run_id, role,
  feature, project_root, board, scope, created_at, revoked_at)`; `mint`, `resolve`, `revoke`.
- `src/pathly_orchestrator/db/migrations_provenance.py` — creates `run_tokens`; called from
  `migrations_incremental._add_additive_migrations` (one line).
- `src/pathly_orchestrator/http_server/run_identity.py` — `caller_identity(request)` →
  `{kind: run|ui|anonymous, run_id, role, feature, pairs}` from `X-Pathly-Run-Token`.

Changed files
- `supervisor/task_prompt.py`, `supervisor/board_run.py` — mint at prompt compose (role + scope
  known there, SPEC C4 open item); revoke on run end (`supervisor/terminal.py`).
- Spawn env: Studio `terminal.ts` next to `PATHLY_GATE_BILLED` (`:179`) and
  `pty_host/host.py:228` — add `PATHLY_RUN_TOKEN`. In `terminal.ts` put the env assembly in a new
  `studio/src/main/ipc/terminal/spawnEnv.ts` and call it, so the file does not grow.
- Fragments `board-search.md`, `board-init.md`, `comms-post.md` — send
  `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"`; then `pathly-setup claude --apply --repair`
  check + adapter rebuild (`python -m build`).

Tests: token minted per spawn and present in both spawn hosts' env; revoked token resolves to
anonymous; fragment snapshot tests updated.

---

## RRP-2b — UI token (P3, UI half) · P0 · Med

New files
- `src/pathly_orchestrator/http_server/ui_token.py` — mint at server start, write
  `~/.pathly/ui_token` (0600), `is_ui_request(request)`.

Changed files
- `studio/src/main/apiConfig.ts` — read the UI token but **do not** put it in `process.env`.
- Preload bridge — expose it next to `apiConfig()`.
- `studio/src/renderer/src/lib/config.ts` (`apiFetch`) — send `X-Pathly-UI-Token`.
- `http_server/middleware.py` — add the header to both CORS allow-lists (`:162`, `:213`).

Tests: renderer board reads carry the header; a spawned agent's env has no UI token; preflight
allows the header. `npm run typecheck` + `tsc -p tsconfig.node.json`.

---

## RRP-3 — Server-stamped provenance (P2) · P0 · Med · needs RRP-2

New files
- `db/migrations_provenance.py` (same module as RRP-2) — add `author_role`, `author_run_id`,
  `author_source` to `comms_messages`; backfill `legacy` (SPEC C1 rules: `supervisor/system` →
  `system`; `run_id` joins `agent_invocations` → that role; else `from_agent`).
- `src/pathly_orchestrator/runner/provenance.py` — `stamp(identity) -> dict` used by every writer.

Changed files
- `blueprints/comms/messages_write.py` — one call to `stamp(caller_identity(request))` passed into
  `post_message`; body `from`/`run_id` ignored for provenance.
- `db/queries/comms_messages.py::post_message` — accept the three columns.
- Server-internal writers (`supervisor/goal_verify.py`, `supervisor/task_retry.py`, …) — pass
  `author_source="system"`.

Tests: US-2 cases; migrated DB backfill cases (SPEC E "Legacy backfill").

---

## RRP-4 — Push path in `warn` (P2b) · P0 · Low · needs RRP-1, RRP-3

New files
- `runner/comms_context_policy.py` — wraps the semantic and recency queries with
  `policy_predicate`, fetch-until-`k` for the vector arm, and returns withheld counts.

Changed files
- `runner/comms_context.py` — swap the two query calls for the wrapper (net ≤ 0 lines).
- `runner/context_record.py` — record `withheld` per reason (US-5 data).

Tests: SPEC E "Push path" and "Truncation" on the push path; `warn` leaves the prompt unchanged.

---

## RRP-5 — Pull paths (P3, routes) · P0 · Med · needs RRP-1..3, RRP-2b

Changed files
- `db/queries/comms_embeddings.py` — `search_by_keyword` / `search_by_embedding` /
  `search_by_hybrid` take an optional `(where_sql, params)` and AND it before ranking/`LIMIT`.
- `db/queries/comms_messages.py::get_messages` — same.
- `blueprints/comms/messages_crud.py` (`GET /comms` `:15`, `POST /comms/search` `:62`) — resolve
  `caller_identity`, pick the policy (run → role; ui → unrestricted; none → `anonymous`), pass the
  predicate. Put the resolution in a new `blueprints/comms/_read_gate.py`; the routes gain ~2
  lines each.

Tests: US-3 cases; anonymous call counted in `warn`.

---

## RRP-6 — `(board, scope)` pair binding (P4) · P1 · Med · needs RRP-5

New files
- `db/queries/comms_pairs.py` — query helper that **requires** board and scope.

Changed files
- `blueprints/comms/_read_gate.py` — refuse foreign pairs with `403 {reason}` in `enforce`, count
  in `warn`; allow `type ∈ {goal, task}` on any feature board (SPEC C6).
- `board-init.md` — treat `403` as "refused", not "empty".

Tests: US-4 cases; invariant test over all comms read queries (also covers US-6, SPEC C8).

---

## RRP-7 — Visibility (P5) · P1 · Low · needs RRP-4

Changed files
- `blueprints/comms/context.py` (`POST /comms/agent-context/preview`) — return withheld rows with
  the rule that hid them.
- Studio preview component — grey rows + reason (new component folder, CSS module).

Tests: preview for `role=reviewer` lists hidden rows and reasons.

---

## RRP-8 — Flip to `enforce` (P6) · P1 · Med · needs RRP-1..7

- Soak in `warn` on real runs; review withheld counts and any review/test stage that failed for
  missing context.
- Change the `read_policy.mode` default; CHANGELOG entry; update
  `src/pathly_orchestrator/CLAUDE.md` (comms board section) and root `CLAUDE.md` if the read
  contract is described there.

Done when: soak data reviewed and recorded in this folder; default is `enforce`.

---

## Cross-cutting DoD (every ticket)
- `python -m pytest tests/ -q` (full suite: basenames must be unique)
- `python3 scripts/check_file_size.py` (no growth of near-limit files)
- `python3 scripts/check_no_mirror_reads.py`
- `python scripts/gen_test_index.py --check`
- Living docs updated in the same commit (root `CLAUDE.md` "Documentation sync").
