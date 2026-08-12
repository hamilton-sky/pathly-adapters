# SPEC — state-one-authority

**Status:** DESIGN · **Created:** 2026-07-22 · **Branch:** `dogfood/state-one-authority`
**Source:** [docs/ARCHITECTURE_ONE_AUTHORITY.md](../../../docs/ARCHITECTURE_ONE_AUTHORITY.md) — **Issue #4 (State)**

Collapse Pathly's parallel state/event/artifact/board disk files to one rule:
**the DB is the single runtime authority; every disk file is SEED-in XOR EXPORT-out,
never round-tripped for truth, and nothing reads a mirror to make a runtime decision.**

## Problem (verified at HEAD 2.23.0)

Per-feature runtime state is persisted across four disk files + SQLite, with **three
different write mechanisms** and a loosely-stated "DB authoritative, disk mirror" rule.
Two of the four disk files are **not true mirrors** and can silently diverge from the DB:

| File | Authority | Writer | Direction | State |
|---|---|---|---|---|
| `STATE.json` | `fsm_state` (DB) | `eventlog._write_state_db` (DB-first, atomic) | DB→disk export | ✅ true mirror |
| `BOARD.json` | `comms_*` (DB) | `board_mirror.py` (debounced, change-guarded, hydratable) | DB→disk export | ✅ true mirror — **the model to copy** |
| `EVENTS.jsonl` | — | agent `python3 -c` open-append (`completion-report` / `log-agent-done` fragments) | agent→disk | ⚠️ diverges from `fsm_events` |
| `ARTIFACTS.jsonl` | — | agent `python3 -c` open-append (`artifact-register` fragment); swept **into** the DB by `artifact_reconcile.py` | agent→disk, then disk→DB import | ⚠️ diverges; import direction |

**Consequences:**
- `eventlog.append_event` writes the **DB**, not `EVENTS.jsonl` — but three docstrings still
  claim it writes the file: `eventlog.py:1-14`, `http_server/blueprints/ops/telemetry_activity.py:41`,
  `http_server/blueprints/ops/telemetry_phase.py:70`. Documentation/reality drift.
- Server-originated events (telemetry handlers, `supervisor/terminal.py` reconciliation,
  `cli/back.py` rollback) **never reach** disk `EVENTS.jsonl`, so the on-disk backup silently
  diverges from the authoritative `fsm_events` stream.
- The rule being "stated loosely" is exactly where the stale-seed bug class lives (per the doc).

## Goal

Generalize the already-shipped `BOARD.json` export pattern to events + artifacts, retire the
agent-side dual-write so nothing can diverge, and make the rule **enforceable**, not just
documented.

## In scope
1. **Classify** every per-feature/global disk file as **SEED / EXPORT / DB-mirror** — one
   canonical table + a one-line rule in root `CLAUDE.md`.
2. **`EVENTS.jsonl` → DB→disk EXPORT** (mirror `fsm_events` the way `board_mirror` mirrors
   comms), retiring the agent-side dual-write — OR decide to drop it if `BOARD.json` + the DB
   already cover the audit/git-diff need.
3. **`ARTIFACTS.jsonl` → same treatment** (given `artifact_reconcile` already imports it into
   the DB, the disk file may become a pure export or be folded into `BOARD.json`).
4. **CI enforcement:** a gate that fails the build on any runtime read of a mirror file outside
   its export writer — same shape as the dash-safety mirror test.
5. **Fix the 3 stale docstrings.**

## Out of scope (this pass)
- Issues #1–#3 of the same doc (Prompts / Telemetry / Context) — separate features.
- The SEED side (flow-YAML replace-semantics) — already fixed; only re-document.
- Any behavior change to `STATE.json` / `BOARD.json` (they already obey the rule).

## Constraints
- **Behavior-neutral on the happy path.** DB stays authoritative; no DB schema migration for P0.
- Windows path-safety + atomic temp-file rename (match `board_mirror`).
- Best-effort writes never fail a run (match `board_mirror` + `STATE.json`).

## Acceptance
- Every disk file is labeled SEED/EXPORT/DB in one doc + a root `CLAUDE.md` one-liner.
- `EVENTS.jsonl` (and `ARTIFACTS.jsonl`) are written **only** by a DB→disk exporter; no
  agent-side dual-write remains; no runtime code reads them to decide anything.
- A CI check fails the build on a new runtime read of a mirror file.
- The 3 docstrings are corrected. Full test suite green.
