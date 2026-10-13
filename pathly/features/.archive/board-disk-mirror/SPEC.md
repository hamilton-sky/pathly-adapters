# SPEC — Board disk mirror

**Status:** DESIGN · **Created:** 2026-07-12

Make the comms board portable and git-trackable by mirroring board content to disk
inside each project's `pathly/` tree, without changing the runtime board engine.

## Goal & motivation

Today every board's messages/goals/tasks live **only** in the central DB
(`~/.pathly/pathly.db`, tables `comms_messages` + `comms_artifacts`), keyed by
`(board, scope)`. Consequences the user hit while dogfooding:

- Copy a project to another machine → the board is empty (cards stayed behind in the
  central DB).
- Board content is **not** version-controlled with the repo and never appears in the
  file tree — only the *artifacts* (files) land under `pathly/`, not the cards.

We want the board (feature + project) to **travel with the repo** and diff in git, while
the global board (cross-project) travels with the machine.

## Locked decisions

1. **Source of truth = DB; disk = mirror.** The DB stays the runtime system of record so
   every `/comms/*` route, the SSE streams, and hybrid search keep working unchanged. Disk
   files are synchronized, git-trackable copies — the exact pattern `STATE.json` uses for
   `fsm_state` (`eventlog.write_state`: DB first, then the file; reads fall back to the file
   when the DB has no row).
2. **Global board → `~/.pathly/global/`.** It is cross-project and must never be committed
   into a repo, so its mirror lives in the global home, not under any `pathly/`.

## What mirrors where

| Board scope | DB key (`scope`) | Disk mirror |
|---|---|---|
| feature | `<feature-id>` | `<project>/pathly/features/<feature-id>/BOARD.json` |
| project | `<project-root>` | `<project>/pathly/project/BOARD.json` |
| global  | `"global"` | `~/.pathly/global/BOARD.json` |

Artifacts already live on disk (`pathly/features/<f>/artifacts/`, `pathly/project/artifacts/`).
This feature mirrors the **message/goal/task/artifact-metadata rows** — the cards — not the
artifact files (which are handled and now canonical after `40c7aadc`).

## Design

### File format — `BOARD.json` snapshot
A single JSON object per board, **rewritten atomically** on each change (like `STATE.json`),
not append-only — board rows are mutable (edit, delete, supersede, ack, answer, `task_status`,
`goal_id`). Snapshot form keeps git diffs readable and hydration trivial.

```jsonc
{
  "board": "feature",
  "scope": "board-disk-mirror",
  "version": 1,
  "messages": [ /* comms_messages rows, non-deleted, stable-sorted by ts,id */ ],
  "artifacts": [ /* comms_artifacts metadata rows for these messages */ ]
}
```
Soft-deleted rows are **excluded** from the mirror (the mirror reflects the live board).
Embeddings are **not** mirrored (they're a derived search index; rebuilt on hydration).

### Write path (mirror hook)
Add one choke-point hook, mirroring the existing `append_event → on_event_appended`
invocation-projection hook. After any committed `comms_messages`/`comms_artifacts` mutation
for a `(board, scope)`, enqueue a **debounced** rewrite of that board's `BOARD.json`
(coalesce a burst of task updates into one write). Debounce + atomic temp-file rename keep it
cheap and crash-safe. Failure to write the mirror **never** fails the board write (best-effort,
like the stop-hook telemetry).

### Hydration (fresh clone / empty DB)
On server start, for each discoverable board mirror on disk, if the DB has **no** rows for that
`(board, scope)`, import the file into the DB and (re)compute embeddings — the board comes back
after a clone. Mirrors the `STATE.json` fallback in `next_action`/`complete_stage`. If the DB
already has rows, DB wins (it's authoritative); a divergent mirror is overwritten on the next
write.

### Backfill (one-time)
Idempotent startup pass (pattern: `backfill_invocations_from_events`): for every distinct
`(board, scope)` in `comms_messages` with a resolvable disk home, write its `BOARD.json` once.
Behavior-neutral — pure export.

## Key problems to solve

1. **★ scope → project_root mapping for feature boards.** The central DB stores a feature board
   under `scope = <feature-id>` with **no project root**, but the mirror must be written to
   `<project-root>/pathly/features/<feature-id>/BOARD.json`. Project boards are fine (`scope`
   *is* the root); feature boards are not. Options:
   - (a) Persist the owning `project_root` on each feature-board row (new nullable column) —
     set from the posting context (Studio posts carry it; `/comms/post` would need to thread it).
     Backfill infers it from the feature's existing on-disk home.
   - (b) A `scope_roots` side table mapping `feature-id → project_root`, populated on first
     write and by the discovery scan.
   - Recommendation: **(a)** — least indirection, and the mirror writer already needs a root.
   This is the one decision that must be settled before P1.
2. **Deletions.** A hard-deleted board (all rows gone) should leave an **empty** `BOARD.json`,
   not a stale one. Mirror writer must handle "0 live rows" (write empty, don't skip).
3. **Git-merge noise.** Two branches editing the same board conflict on `BOARD.json`. Stable
   sort (by `ts`,`id`) minimizes churn; a `.gitattributes merge=union` hint can reduce
   conflicts. Acceptable for v1; documented, not solved automatically.
4. **Concurrency / atomicity.** Multiple writers to one board → temp-file + atomic rename under
   the existing DB write lock's scope; last-writer-wins is fine since the DB is truth.
5. **Global home discovery.** `~/.pathly/global/` must be created lazily and excluded from every
   project scan.

## Phased plan

- **P0 — foundation (behavior-neutral):** path resolver `(board, scope, root?) → mirror path`;
  the atomic `write_board_mirror(board, scope)` exporter; the idempotent backfill. No hook yet —
  export is opt-in/manual. Ships value (git-trackable boards) with zero runtime-path change.
- **P1 — live mirror:** settle problem ★ (project_root on feature rows), wire the debounced
  write hook into the comms mutation choke point. Boards now mirror continuously.
- **P2 — hydration:** import-on-start when DB is empty for a `(board, scope)` present on disk;
  the fresh-clone story. Includes embedding recompute.

Each phase is independently shippable; P0 alone already makes boards appear on disk.

## Risks / open questions

- Busy boards → large `BOARD.json` rewrites on every card change (debounce mitigates; revisit
  chunked/per-message files only if it hurts).
- Problem ★ threading `project_root` through `/comms/post` touches the write API contract.
- Global-board hydration across machines is best-effort (no cross-machine merge).

## Out of scope

- Artifact **files** (already canonical on disk).
- Embeddings on disk (derived; rebuilt on hydration).
- Real-time multi-writer merge / CRDT semantics (last-writer-wins via DB authority).
