# Implementation Plan — docs-sync

## Scope

Three doc files, five targeted edits. No new files. No code changes.

| File | Stories addressed |
|---|---|
| `docs/ARCHITECTURE.md` | S1, S5 |
| `docs/PATHLY_ARCHITECTURE.md` | S1, S3, S4, S5 |
| `docs/MULTI_TOOL_DESIGN.md` | S2 |

---

## Approach

All five fixes are small, self-contained text edits. They share no dependency on
each other and can be done in a single pass. The builder reads each file,
applies the edits, and verifies with grep checks before closing the conversation.

There is no ambiguity about what the correct values are — the codebase layout
is established:
- `src/install_cli/` — CLI modules including `materialize.py`
- `src/pathly_data/` — package data directory
- `orchestrator/` — local FSM module at repo root
- No `pathly-engine` package exists

---

## Phase 1 — Fix stale claims (S1, S2, S3)

**Files touched:** all three docs.

Steps:
1. In `docs/ARCHITECTURE.md`: update the directory tree (line ~43) and the
   module table (line ~100) to replace `install_cli/materialize.py` with
   `src/install_cli/materialize.py`. Apply same `src/` prefix to the other
   `install_cli/` entries in the tree if they also lack it.
2. In `docs/PATHLY_ARCHITECTURE.md`: update the tree (line ~61) and the module
   table (line ~77) to prefix `install_cli/` entries with `src/`. Update the
   `pathly_data/` tree header (line ~88) to read `src/pathly_data/`.
3. In `docs/MULTI_TOOL_DESIGN.md`: replace the monorepo tree (lines 9-31) with
   the real single-package layout. Remove the `pathly-engine` row from the
   adapter table. Remove all references to `pathly-engine/`, `runners/`,
   `team_flow/` (engine-side), and `engine_cli/`.

Verification after Phase 1:
- `grep -r "pathly-engine" docs/` returns no results.
- `grep -r "install_cli/materialize" docs/` returns only results containing
  `src/install_cli/materialize`.
- `grep "pathly_data/" docs/PATHLY_ARCHITECTURE.md` returns only `src/`-prefixed results.

---

## Phase 2 — Add missing sections (S4, S5)

**Files touched:** `docs/PATHLY_ARCHITECTURE.md`, `docs/ARCHITECTURE.md`.

Steps:
1. In `docs/PATHLY_ARCHITECTURE.md`: add a "Python Package Layout" section after
   the existing folder structure section. Cover: `src/pathly_adapters/`,
   `src/pathly_data/`, `pyproject.toml` entry points.
2. In `docs/ARCHITECTURE.md`: add a short `orchestrator/` note (table row or
   callout) in or near the existing module summary table. State: local module at
   repo root, FSM event-log library for LLM context tracking, not user-facing.

Verification after Phase 2:
- `grep -n "Python Package Layout\|src/pathly_adapters\|pyproject.toml" docs/PATHLY_ARCHITECTURE.md`
  returns at least 3 matches.
- `grep -n "orchestrator" docs/ARCHITECTURE.md` returns the new note line.

---

## Done Definition

The conversation is complete when:
- All five acceptance criteria sets from `USER_STORIES.md` pass.
- No other content in the three doc files is altered.
- The docs still render as valid Markdown (no broken fences or tables).
