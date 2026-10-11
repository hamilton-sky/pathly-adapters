# User Stories — Role Read Policy

Acceptance criteria are the testable definition of done. Design: [SPEC.md](SPEC.md).

## US-1 — The reviewer judges the diff, not the builder's story
> **Given** a feature board where the builder posted `discovery`/`status` notes and the architect
> posted a `discovery` and a pending `decision`,
> **When** the reviewer stage is spawned with `read_policy.mode=enforce`,
> **Then** its injected context contains the architect discovery and the decision, and none of
> the builder's discovery/status/nudge/warning posts.

Acceptance:
- Governance (pending decisions, active escalations), `decision`, `constraint`, `goal`, `task`
  are never withheld.
- The tester gets the same wall without `warning` (SPEC C2).
- In `warn` the prompt is unchanged and the run's context record counts what would be withheld.

## US-2 — A post cannot lie about its author
> **Given** a builder run,
> **When** it posts with `from: "explorer"` or a body `run_id` naming another run,
> **Then** the row is stored with `author_role=builder` and `author_run_id=<builder run>`, and the
> reviewer's wall still hides it.

Acceptance:
- `author_role` / `author_run_id` / `author_source` come only from the run token (or `system` for
  server-internal writers); a post with no token is `author_source=none`.
- Rows from before the upgrade are backfilled as `legacy` with a best-effort role.

## US-3 — Pulling the board gives no more than the push path
> **Given** a reviewer run with its token,
> **When** it calls `POST /comms/search` or `GET /comms` (even with `role: "human"` in the body),
> **Then** it gets exactly the rows its wall allows, and a call with no token gets no more than
> the strictest wall.

Acceptance:
- Body `role` / `run_id` never change the policy.
- The Studio UI (UI token) keeps the unrestricted view; spawned agents' env has no UI token.
- Filtering happens before `k` / `limit` (5 builder rows + 1 architect row, `k=5` → architect row
  returned).

## US-4 — A run cannot read another feature's board
> **Given** a run on feature A,
> **When** it searches `board=feature, scope=B`,
> **Then** it gets `403` with a reason in `enforce` (counted in `warn`), while a `board-init`
> lookup of goal/task rows on a new feature still works and posts no duplicate root goal.

## US-5 — I can see the wall
> **Given** the context preview for `role=reviewer`,
> **Then** withheld rows appear greyed with the rule that hid them, and the run record shows
> withheld counts by reason (`type`, `author`, `unverified`, `pair`) and how many rows were shown
> on `legacy` attribution.

## US-6 — Future read paths cannot reopen the wall
> **Given** a new query that reads `comms_messages` or a memory table derived from it,
> **When** it does not go through `policy_predicate`,
> **Then** CI fails.
