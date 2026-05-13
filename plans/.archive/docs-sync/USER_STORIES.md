# User Stories — docs-sync

## Background

A contributor reads the docs to understand the codebase. Five claims are either
wrong or absent, causing confusion about file locations, module responsibilities,
and package structure. This feature corrects all five in a single pass over
three existing doc files.

---

## Story 1 — Remove the phantom `materialize.py` module entry

**As a** contributor reading the install_cli module table,
**I want** every listed module to actually exist at the path shown,
**so that** I can open any file the docs reference without hunting.

**Context.**
Both `docs/ARCHITECTURE.md` (line ~100, module table and tree at line ~43) and
`docs/PATHLY_ARCHITECTURE.md` (line ~61, tree; line ~77, module table) list
`install_cli/materialize.py` as if it lives one level below the repo root.
The real file is `src/install_cli/materialize.py`. The path prefix `src/` is
missing in all references.

**Acceptance criteria.**
- `docs/ARCHITECTURE.md`: every occurrence of `install_cli/materialize.py`
  (tree and table) is updated to `src/install_cli/materialize.py`.
- `docs/PATHLY_ARCHITECTURE.md`: every occurrence of `install_cli/materialize.py`
  (tree and table) is updated to `src/install_cli/materialize.py`.
- No other module paths in those files are changed.
- A reader can `grep -r "install_cli/materialize.py" docs/` and find zero
  results that lack the `src/` prefix.

---

## Story 2 — Remove the `pathly-engine` monorepo claim

**As a** developer evaluating the project structure,
**I want** the docs to reflect the real repo layout,
**so that** I don't waste time looking for a `pathly-engine` package or a
`runners/` directory that don't exist.

**Context.**
`docs/MULTI_TOOL_DESIGN.md` lines 9-31 show a monorepo tree with two top-level
packages: `pathly-adapters/` and `pathly-engine/`. `pathly-engine` does not
exist. `orchestrator/` is not inside a `pathly-engine` package; it lives at
the repo root as a local Python module. The CLI adapter column also references
`pathly-engine/engine_cli/` which does not exist.

**Acceptance criteria.**
- The monorepo tree in `MULTI_TOOL_DESIGN.md` is replaced with the real
  single-package layout: `pathly-adapters/` at root (no wrapping monorepo dir),
  `orchestrator/` at repo root (not inside any sub-package).
- The `pathly-engine` row is removed from the adapter table (or corrected if a
  CLI entry point exists — it does not, so remove it).
- References to `pathly-engine/engine_cli/`, `runners/`, and `team_flow/`
  are removed.
- A reader can `grep -r "pathly-engine" docs/` and find zero results.

---

## Story 3 — Fix `pathly_data/` path (add `src/` prefix)

**As a** developer looking for the package data directory,
**I want** the docs to show the correct path `src/pathly_data/`,
**so that** I find the directory on the first try.

**Context.**
`docs/PATHLY_ARCHITECTURE.md` lines 82-102 show a `pathly_data/` tree starting
at the repo root. The actual directory is `src/pathly_data/`.

**Acceptance criteria.**
- The tree header in `PATHLY_ARCHITECTURE.md` reads `src/pathly_data/` not
  `pathly_data/`.
- Any prose sentence in that file that says "pathly_data/ is the installed
  package data" is updated to reference `src/pathly_data/`.
- A reader can `grep "pathly_data/" docs/PATHLY_ARCHITECTURE.md` and every
  result includes the `src/` prefix.

---

## Story 4 — Add Python package layout section

**As a** new contributor setting up the project,
**I want** a doc section that explains the `src/` layout,
**so that** I understand why `src/pathly_adapters/` and `src/pathly_data/` are
under `src/` and how entry points are wired.

**Context.** No current doc explains the `src/` layout convention or the
`pyproject.toml` entry points. This creates confusion when contributors look
for modules at the repo root.

**Acceptance criteria.**
- `docs/PATHLY_ARCHITECTURE.md` contains a new "Python Package Layout" section
  (or equivalent heading) that:
  - Identifies `src/pathly_adapters/` and `src/pathly_data/` as the two source
    packages under `src/`.
  - States that `pyproject.toml` declares the entry points (`pathly-setup`,
    `pathly-tokens`).
  - States that `src/install_cli/` contains the CLI implementation modules.
- The section is no longer than 15 lines of prose/table.
- A reader can find the section by searching for "src/" in the file.

---

## Story 5 — Add `orchestrator/` scope note

**As a** developer reading about the orchestrator,
**I want** a short explanation of what `orchestrator/` is and is not,
**so that** I don't confuse it with a user-facing CLI tool or a separate package.

**Context.** No current doc explains that `orchestrator/` is a local FSM library
for tracking LLM conversation context, not a user-facing command.

**Acceptance criteria.**
- At least one doc file (target: `docs/ARCHITECTURE.md` or
  `docs/PATHLY_ARCHITECTURE.md`) contains a note or table row for
  `orchestrator/` that:
  - Identifies it as a local Python module at the repo root.
  - States it is an FSM event-log library used internally for LLM context
    tracking.
  - States it is not a user-facing CLI tool.
- The note is no longer than 4 lines.
- A reader can `grep -r "orchestrator" docs/` and find the new note.
