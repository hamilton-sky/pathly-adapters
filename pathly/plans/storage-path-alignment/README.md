# storage-path-alignment — deferred follow-up

**Goal:** finish aligning Pathly so a feature created at the **new root `pathly/<topic>/`**
works through the **full team pipeline** — not just single-agent runs. Today the FSM
resolver + Studio + board_run use the resolved root, but some skill/CLI prose still
**hardcodes `pathly/plans/<feature>/`**, which is wrong for a new-path feature.

> **Status: PARKED — not urgent.** There are zero `pathly/<topic>/` features in use yet.
> Every existing feature (`pathly/plans/<feature>/`) works unchanged. **Trigger to do
> this:** the first time you run the **full team flow** on a feature created via
> `+ New feature` (single-agent runs are already safe — see "Done" below).

---

## The principle
Stop hardcoding the path in skills. The FSM already resolves it
(`fsm_ops._resolve_storage_path` → prefers `pathly/<topic>/`, falls back to
`pathly/plans/<topic>/`) and hands it to the agent as the **`Storage path:`** line.
So every reference should use the **injected `<storage_path>` / `<feature_path>`
variable**, never a literal `pathly/plans/…`.

## Two fix categories

### A. Specific-file references → use the variable
Anywhere a skill writes/reads a specific file as `pathly/plans/<feature>/X.md`,
change it to `<storage_path>/X.md` (the FSM substitutes the resolved root).
Grep target: `grep -rn "pathly/plans/<feature>" src/pathly_data/core/skills`.

### B. Discovery globs → dual-scan or DB
Skills/CLI that **enumerate features** by globbing `pathly/plans/*/STATE.json`
(sorted by mtime) miss `pathly/<topic>/` features. Fix each to scan **both**
`pathly/*/` (excluding reserved: `plans`, `.archive`) **and** `pathly/plans/*/`,
or use the DB query `db/queries/fsm_state.read_all_states(conn, project_root)`.

## Inventory (verify with grep before editing)

**Skill prose — discovery globs (category B):**
`utilities/reflect.md`, `utilities/archive.md`, `controls/pause.md`,
`controls/pathly.md`, `development/build.md`, `development/test.md`,
`development/fix.md`, `planning/retro.md`, `team/discover.md`.

**Skill prose — specific-file refs (category A):** scan all migrated skills for any
residual `pathly/plans/<feature>/…` literals.

**Python CLI — discovery globs (category B):**
`cli/status.py`, `cli/log.py`, `cli/ff.py`, `cli/back.py`,
`http_server/blueprints/db_api.py` (`_scan_filesystem_features`).

## Already done (do NOT redo)
- `fsm_ops._resolve_storage_path` — prefers `pathly/<topic>/`, falls back to legacy.
- FSM `next_action` passes the resolved `Storage path:` to flow agents.
- `health.py /status` — enumerates via `read_all_states` (DB), not a glob.
- Studio `commsStore.loadFeatures` — dual-scans `pathly/*/` + `pathly/plans/*/`.
- `board_run` — injects the resolved feature root into the single-agent prompt
  (so single-agent runs on new-path features are already correct).

## Execution plan
1. Category A edits across skills (variable substitution).
2. Category B edits across the discovery skills + Python CLI (dual-scan / DB).
3. `pathly-setup claude --apply --repair && python -m build` (skills are core; adapters re-stitch).
4. Run `python -m pytest tests/test_compose.py tests/test_fsm_ops.py -q` (snapshots may need regenerating).
5. **Interactive smoke test:** create a feature via `+ New feature` (lands at `pathly/<topic>/`),
   run `/pathly build → review → test`, and confirm every artifact/plan/feedback file
   lands in `pathly/<topic>/`, not split into `pathly/plans/<topic>/`.

Recommended as a focused workflow (like the STATE.json→FSM skill migration), not a blind find/replace.
