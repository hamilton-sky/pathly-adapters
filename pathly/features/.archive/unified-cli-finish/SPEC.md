# unified-cli-finish — finish unified-cli-composition + storage-path-alignment

Finishing the two plans that were "mostly built": make skills agnostic (connection
via fragments), align storage on `pathly/<feature>/`, and expose the composition
override so user-added skills can pick their fragments.

## Part 1 — Agnosticism migration

Closer reading of the 8 "violators" splits them three ways:

| Skills | Nature | Action |
|---|---|---|
| `team/research`, `team/architect` | incidental: post ONE artifact via a body curl | **strip curl, compose `comms-post`** (Phase 1) |
| `team/build`, `development/build` | duplicate the task claim/complete/fail loop | **extract `task-drain` fragment**, compose it (Phase 2) |
| `planning/evaluate`, `planning/consolidate`, `planning/plan` | board CRUD **is the skill's purpose** (goal/task seed, supersede) | **reclassify as board-native** (utility exception) + document (Phase 3) |

`development/drain-dag` is already the canonical `single`-executor drain loop and is the
extraction source for `task-drain`; it keeps its inline loop (or composes the new fragment).

## Part 2 — Storage-path alignment

Replace hardcoded `pathly/plans/<feature>` with the injected `<feature_path>` variable in
pipeline skills (category A), and dual-scan discovery globs (`pathly/*/` + `pathly/plans/*/`,
excluding reserved `plans`/`.archive`) in the utility skills + Python CLI (category B).
Infra is already done: `_resolve_storage_path` prefers `pathly/<topic>/`. Inventory in the
archived `storage-path-alignment/README.md`.

## Part 3 — Custom-skill composition UI

Backend override layer already exists (`skill_composition` table +
`set/get/delete_composition_override` + `load_effective_manifest` merge). Expose it: a
Studio fragment-picker that reads the fragment catalog + a skill's effective fragment list
and writes an override (global or per-project). Wire a `/skills/composition` GET/POST route
if not already present.

## Adapter sync (after any core skill/fragment edit)

`pathly-setup claude --apply --repair && python -m build`, then re-run
`tests/test_compose.py tests/test_fsm_ops.py`.

## Phases

1. **research + architect** → comms-post, strip curls. (tested)
2. **task-drain fragment** → team/build + development/build compose it.
3. **evaluate/consolidate/plan** → document as board-native (CLAUDE.md + comms-post table).
4. **storage-path category A** → `<feature_path>` substitution in pipeline skills.
5. **storage-path category B** → dual-scan globs in utility skills + `cli/*.py`, `db_api`.
6. **composition UI** → Studio fragment-picker + route.
