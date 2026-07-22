# SPEC — run-identity

_Seeded 2026-07-22 from the state-one-authority assessment. Goal: retire the
`<feature>` vs `<fsm_feature>` two-identity bug class at its root._

## Problem

Every `fsm_events` row is keyed by ONE `feature` column that must serve two different
identities:

- **board scope** (`<feature>`) — the parent feature/project a run belongs to (board writes,
  artifact attribution)
- **run slug** (`<fsm_feature>`) — the storage-dir basename (telemetry, event-log keying,
  billing reconciliation)

For a plain feature run they coincide; for goal/debug/nested runs they diverge, and every
consumer must GUESS which identity the column holds. This has produced a recurring bug class:
goal panels showing $0, artifacts orphaned onto slug boards, runs mis-bucketed in the
Monitor, `last_summary` keying subtleties. Root cause: **identity is derived from storage
location** (`feature_dir.name`, `storage_path.parent.parent.parent`) instead of **issued at
spawn**, where both values are known (`fsm_compose` already substitutes both placeholders;
`<run_id>` is already substituted too).

## Design step 1 - stamp at spawn

Stamp BOTH identities, once, where truth is known — then consumers stop guessing.

- `fsm_events` gains a nullable `board_scope` column (idempotent ALTER TABLE migration).
  `db.queries.fsm_events.append_event` extracts `board_scope` from the event dict into the
  column, exactly as it extracts `type`/`ts` today. Legacy rows stay NULL; no backfill
  required (fallback heuristics remain for NULL).
- The `completion-report` fragment and `utilities/log-agent-done` add
  `"board_scope": "<feature>"` to the AGENT_DONE body (the `<feature>` placeholder IS the
  board scope; the event's feature key stays `<fsm_feature>`). Adapter regen + compose
  snapshots per the core→adapter sync rule.
- Server-side guarantee: the supervisor paths that synthesize or patch events
  (`_synthesize_agent_done_if_missing`, `_patch_last_agent_done` / BILLING_UPDATE, the
  terminal-result path) stamp `run_id` + `board_scope` when the agent omitted them — the
  spawner knows both. An agent that reports nothing still yields a fully-identified row.

## Design step 2 - run id primary

Promote `run_id` to the issued primary identity of telemetry; location becomes a storage
detail.

- `run_history` becomes the identity map: every runner/board/goal spawn writes a row carrying
  `{run_id, project_root, feature (slug), board_scope}`; fix the residual keying-by-full-topic-path
  so `feature` is the slug, and add `board_scope` (nullable, migration).
- `invocation_projection` stamps `board_scope` onto `agent_invocations` (new column) from the
  event stream; `run_id` is already stamped — prefer it, and treat a NULL-run_id row as
  legacy.
- Consumers pivot: the DB-explorer rollup / goal detail / Monitor RECENT bucketing prefer the
  `run_id → run_history` join (or the `board_scope` column) over feature-key heuristics,
  keeping the heuristic only as the fallback for legacy NULL rows. A goal-run's cost is then
  visible under BOTH its slug and its board scope without guessing.

## Non-goals

- No change to storage layout or nesting (board-scoped storage stays).
- No rewrite of `<feature>`/`<fsm_feature>` prompt placeholders — they remain; this feature
  makes their VALUES land as first-class columns instead of being re-derived downstream.
- OTel span keying (residual full-path keying) may ride along in step 2 but is not a gate.

## Risks

1. **Fragment edits fan into all 4 adapters** — regen + snapshot discipline (the
   state-one-authority G1 learning): `pathly-setup claude --apply --repair` +
   `python -m build`, then regenerate golden compose snapshots after eyeballing the diff.
2. **Schema migrations must be idempotent** on live DBs (follow the existing ALTER TABLE
   ADD COLUMN try/except pattern in `db/migrations.py`).
3. **Legacy rows (NULL board_scope / NULL run_id)** must keep working — every consumer keeps
   its current heuristic as the NULL fallback; behavior-neutral for old data.
4. **Two writers race the same AGENT_DONE** (agent self-report vs supervisor synthesis) —
   the stamp must be COALESCE-style (fill only when absent), never overwrite an
   agent-provided value.
