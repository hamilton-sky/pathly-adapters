# Retro — state-one-authority

**Feature:** state-one-authority (ARCHITECTURE_ONE_AUTHORITY Issue #4)
**Date:** 2026-07-22
**Pipeline:** consultation decompose → 3 goals / 10 tasks → built IN-SESSION (per-goal gated), board cadence per task (claim → ground → build → verify → status → complete)
**Commits:** `8ced01d9` (G1) · `3011b7f2` (G2) · `69aeb8fc` (G3) on `dogfood/state-one-authority`

---

## 1. What went well?

- **The board DAG carried a 3-session feature with zero drift.** The IMPLEMENTATION_PLAN's
  BOARD_DAG was the work queue; every task carried Files + Done-when + context_refs, and a
  fresh session (G2/G3) reached full productivity from the handoff + board alone — no
  re-discovery pass. `newly_ready` on each complete made the frontier visible in real time.
- **Done-when as a falsifiable contract worked.** Every task was verified by running its own
  gate (line counts, grep-zero checks, injection tests, isolated smoke of `pathly-back`,
  full suite per goal). Nothing shipped on "looks right."
- **The gate caught what the audit missed.** `check_no_mirror_reads.py` found 2 unaudited
  Studio mirror-readers (CommandCenter probe, HealthCheck ×2) and 2 more human-CLI readers
  (`_discovery.py`, `log.py`) that AUDIT_MIRROR_READS.md never listed. They were migrated /
  allow-listed deliberately instead of discovered as prod bugs later.
- **Additive-before-removal sequencing (G1 risk plan) held.** The exporter ran alongside the
  agent dual-write before the dual-write was retired; no event-loss window existed at any
  commit.
- **Verify-then-fix on docs paid off.** The CLAUDE.md sync task found 4 additional stale
  claims beyond the 3 target docstrings (pipeline diagram, agent_hint contract line, storage
  tree annotations, "synchronized mirror" paragraph).

## 2. What could have been better?

- **A false claim propagated unchecked through the whole planning chain.** The audit +
  architecture + task prompt all asserted `_scan_filesystem_features` "already covers
  never-run features" — false for the current `pathly/features/<name>/` layout. Only the
  per-task grounding step caught it, mid-build. The board preserves claims, not truths;
  nothing upstream re-verified the assertion after the layout changed.
- **The agent-written audit was ~75% complete.** Good enough to design from, not good enough
  to enforce from. The deterministic scan had to close the gap — which suggests audits
  should ship WITH their gate, not before it.
- **Two G1 files landed unformatted** (`event_mirror.py`, its test) and would have failed CI
  lint — caught only because G3 ran `black --check` repo-wide. Per-goal verification ran the
  suite but not the lint surface.
- **API field ergonomics cost a round-trip:** `from` vs `from_agent`, message `status` vs
  `task_status` — the handoff had to carry warnings about the board API's own field names.

## 3. What should we do differently next time?

- **Ship the gate with the audit.** When a feature's premise is "no code does X," write the
  checker FIRST (red), then let the migration tasks turn it green — the gate becomes the
  task list, and coverage gaps surface on day one. (Promoted to lessons: *agents audit,
  gates enforce*.)
- **Re-verify inherited claims at plan time, not build time** — a plan-stage pre-flight that
  re-runs the audit's load-bearing greps against HEAD (LESSONS L-001/L-002 already point
  here; this feature is a fresh source for them).
- **Add lint (`black --check`, tsc) to every per-goal verification**, not just pytest.
- **Fix identity at the root** — the `<feature>` vs `<fsm_feature>` split surfaced again in
  the design of `last_summary` keying. Seeded as the next feature: `run-identity` (identity
  issued at spawn, `run_id` primary).

## Metrics

Built in-session (no per-agent CLI spawns → no `agent_invocations` billing rows for the
build itself; board statuses carry the per-task record).

| Goal | Tasks | Verification |
|---|---|---|
| G1 EVENTS/ARTIFACTS cutover | 3/3 | byte-parity export + suite green |
| G2 Studio → DB reads | 3/3 | 5 new endpoint tests · tsc 0 · suite 1412 |
| G3 Enforce + cleanup | 4/4 | gate 0 both ways · smoke rollback · suite 1414 |
| **Total** | **10/10** | **1,414 passed / 5 skipped · gate live in CI** |
