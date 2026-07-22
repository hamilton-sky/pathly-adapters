# IMPLEMENTATION_PLAN — state-one-authority

_Role: planner · Feature: state-one-authority · Rigor: standard · 2026-07-22_
_Inputs: ARCHITECTURE_PROPOSAL.md (authoritative design), SPEC.md, AUDIT_MIRROR_READS.md_

This plan decomposes the architect's 3 phases into 3 GOALS, each a self-contained task-DAG,
for the board's Goals → Task-DAG → pluggable-executor model. No source files were edited to
produce this plan — see the Pre-flight section below for what was verified read-only.

## Pre-flight verification (L-001/L-002 — done at plan time, not deferred)

Every load-bearing file/line claim in `ARCHITECTURE_PROPOSAL.md`'s Component Map and
`AUDIT_MIRROR_READS.md` was re-read against live HEAD before this plan was written. All
confirmed exact, no drift:

- `db_api_explorer.py` is 412 lines (confirms the 400-line SRP-split prerequisite for Goal 2).
- `fsm/engine_actions.py:468-478` is exactly the disk-only `write_state` (Goal 3).
- `eventlog.py:1-14`, `telemetry_activity.py:41`, `telemetry_phase.py:70` all still carry the
  stale "writes EVENTS.jsonl" claim verbatim (Goal 3).
- `commsApi.ts:1058/1093`, `useMonitorSession.ts:59/114`, `useProjectPlans.ts:23`,
  `PlanBoard/index.tsx:148/156/166` all confirmed — the exact `readFile(...STATE.json/
  EVENTS.jsonl)` call sites the audit named (Goal 2; line 156's `PROGRESS.md` read is
  confirmed a separate, already-retired path — left alone).
- `board_mirror.py` (the model for `event_mirror.py`), `eventlog.append_event` (confirmed
  `feature_dir`/`project_root`/`feature` are all local variables at the exact wiring point),
  `artifact_reconcile.py` (109 lines, two clearly separable jobs), `db_features()`'s exact
  dict-building loop, `DbFeature` at `global.d.ts:53`, and `lint.yml`'s `consistency` job shape
  were all read in full to ground Goal 1/2/3 task prompts precisely.

**One correctness finding from this pass that changes how Goal 3 must be dispatched — see
"Cross-goal dependency rationale" below before running this DAG.**

## Goals overview

| Goal | Executor | Tasks | Purpose |
|---|---|---|---|
| `events-artifacts-authority-cutover` | **team** | 3 | P1 — EVENTS.jsonl becomes a real export, ARTIFACTS.jsonl is dropped |
| `studio-db-read-migration` | **loop** | 3 | P2 — Studio stops reading disk mirrors, reads `/db/features` instead |
| `enforce-and-cleanup` | **single** | 4 (1 optional) | P3 — CI gate + delete the test-only writer + doc fixes |

## Cross-goal dependency rationale

**Goal 1 and Goal 2 are mutually independent** — no shared files (Goal 1 is server Python +
skill-fragment markdown; Goal 2 is one server-Python split plus Studio TypeScript) and no
behavioral coupling (the EVENTS export doesn't gate the Studio migration or vice versa). They
can be dispatched in either order, or concurrently once cross-goal parallel lanes (P3 of the
DAG-scheduler roadmap) exist.

**Goal 3's CI gate genuinely depends on BOTH Goal 1 and Goal 2** — `check_no_mirror_reads.py`
fails red on any real, still-live mirror read, and Goal 1/2 are exactly what removes those
reads. The architect's brief calls this out as a literal `depends_on` edge ("3a depends on
BOTH 1b AND 2b"). **It cannot be encoded as a literal task `depends_on` in this board**,
verified by reading the scheduler code, not assumed:

- `get_ready_tasks(conn, boards, scopes, goal_id=...)` (`db/queries/comms_tasks.py`) — the
  function backing BOTH the `loop` executor's frontier (`scheduler.py:242`) and the `single`
  executor's `drain-dag` skill (`GET /comms/tasks?ready=true&...&goal_id=$GOAL_ID`) — scopes
  its `done_ids` lookup by `goal_id`. A `depends_on` entry naming a task from a *different*
  goal will never appear in that goal's own `done_ids` set, no matter how long it waits.
- `scheduler.py`'s own "deadlock guard" (~line 374-399) actively **marks such a task
  `blocked`** with `fail_reason: "deadlocked: unsatisfiable dependency"` once its goal's queue
  drains — an actively misleading status for a task that isn't deadlocked, just gated on a
  different goal.

**Resolution applied in this plan:** the CI-gate task (`ci-mirror-read-gate`) and the
classification-table task (`fix-docstrings-and-claude-md-classification`, which also can't
honestly describe the end state until Goal 1+2 land) carry `depends_on: []` in the BOARD_DAG
below — a literal cross-goal ID would only cause an incorrect auto-block. The precondition is
instead (a) written as an explicit **PRECONDITION** paragraph in each task's own prompt, so the
agent self-checks `GET /comms/goals` before starting and reports blocked rather than proceeding
on a partially-migrated tree, and (b) called out here for whoever dispatches goals: **run
`events-artifacts-authority-cutover` and `studio-db-read-migration` to completion first, then
dispatch `enforce-and-cleanup`.** This is a goal-*dispatch-order* requirement, not something the
task DAG mechanically enforces today.

Within a goal, ordering IS mechanically enforced: `retire-events-dual-write` depends on
`event-mirror-export` (the additive-before-removal safety window the architect's Risk 1 calls
for), `studio-planboard-migration` depends on `studio-data-layer-migration` which depends on
`split-db-api-explorer`, and `migrate-cli-back-py` depends on `ci-mirror-read-gate` (it removes
an allow-list entry the gate task seeds).

---

## Goal 1 — EVENTS/ARTIFACTS authority cutover

**Executor: `team`** (full FSM flow — build+review per task, one shared test pass at the end).
Justification: HIGH risk (architect's Risk 1: retiring the agent dual-write before the exporter
is proven silently drops events; Risk 6: dropping ARTIFACTS.jsonl loses the server-down safety
net) and every touched file is agent-facing infrastructure — the skill fragments get composed
into *every* future agent invocation across the whole system once regenerated. A review pass
catches a mis-sequenced cutover or a broken fragment edit before `pathly-setup --repair` +
`python -m build` push it into all 4 adapters; the shared TESTING phase validates the DAG
end-to-end (a real run still produces correct `EVENTS.jsonl` + attached artifacts) once both
`1a` and `1b` land.

| Slug | Title | Depends on |
|---|---|---|
| `event-mirror-export` | Add `event_mirror.py` — additive DB→disk EXPORT for EVENTS.jsonl | — |
| `retire-events-dual-write` | Retire the agent-side EVENTS.jsonl dual-write | `event-mirror-export` |
| `drop-artifacts-jsonl` | Drop ARTIFACTS.jsonl and its ledger scan | — |

### `event-mirror-export`
- **Files:** `src/pathly_orchestrator/event_mirror.py` (NEW, model: `board_mirror.py`);
  `src/pathly_orchestrator/eventlog.py` (edit — one call added in `append_event`)
- **What to build (gist):** `event_mirror.py` mirrors `board_mirror.py`'s shape exactly — path
  resolver keyed by the resolved `feature_dir` (not a reconstructed path, so debug/explore/goal
  runs export correctly), atomic `write_event_mirror` with a change-guard, a debounced
  dirty-set + flusher (`mark_event_dirty`), and a `run_history`-driven startup backfill. One
  wire-in call added to `eventlog.append_event` right after its existing DB append. Purely
  additive — the existing agent-side dual-write is untouched.
- **Done when:** an appended event reaches `EVENTS.jsonl` within one debounce window; a no-op
  flush doesn't rewrite the file; backfill produces a correct file for a feature with DB history
  but no prior file; the existing dual-write still fires unmodified; full test suite green.
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `ARCHITECTURE_PROPOSAL.md#phased-rollout`

### `retire-events-dual-write`
- **Files:** `src/pathly_data/core/skills/fragments/completion-report.md`;
  `src/pathly_data/core/skills/utilities/log-agent-done.md`
- **What to build (gist):** delete the unconditional "dual-write to EVENTS.jsonl" block and the
  except-clause "last resort" disk write in both fragments (verified line ranges in the full
  prompt below); keep the DB-primary `eventlog.append_event` path. Regen all 4 adapters.
- **Done when:** neither file writes EVENTS.jsonl unconditionally or as a fallback; the
  DB-primary path is untouched; `pathly-setup claude --apply --repair` + `python -m build` both
  exit 0; a real stage run still writes `AGENT_DONE` with `EVENTS.jsonl` updated only by the export.
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `ARCHITECTURE_PROPOSAL.md#risks-prioritized`

### `drop-artifacts-jsonl`
- **Files:** `src/pathly_data/core/skills/fragments/artifact-register.md`;
  `src/pathly_orchestrator/supervisor/artifact_reconcile.py`;
  `src/pathly_orchestrator/supervisor/terminal.py`; `src/pathly_orchestrator/fsm_ops_complete.py`
- **What to build (gist):** delete the ARTIFACTS.jsonl ledger-append step from the fragment and
  job #1 (the ledger scan) from `artifact_reconcile.py`; keep job #2 (feedback scan) and the
  board-POST step. Compensate for the lost server-down safety net by having
  `reconcile_artifacts` attach the stage's own known `<out_path>` directly (one viable approach:
  reuse `manifest_role_file`, already used by `fsm_compose.build_prompt` for the same
  resolution), threaded in from its two call sites as a new optional parameter.
- **Done when:** no ARTIFACTS.jsonl write remains; `artifact_reconcile.py` stays under 400
  lines with no ledger read; a stage's declared output still attaches to the board with the
  ledger gone; adapters regenerated; full test suite green.
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `ARCHITECTURE_PROPOSAL.md#risks-prioritized`

---

## Goal 2 — Studio → DB read migration

**Executor: `loop`** (supervisor-owned frontier, dependency-ordered dispatch). Justification:
MED risk (architect's Risk 3: a feature card silently vanishing if the migration isn't
behavior-neutral) with a cheap, objective verification gate at every task (`tsc --noEmit` plus
an explicit before/after behavioral check) — the frontier naturally sequences
`split-db-api-explorer` → `studio-data-layer-migration` → `studio-planboard-migration` without
the overhead of a full build→review→test flow per task that this mechanical repoint doesn't need.

| Slug | Title | Depends on |
|---|---|---|
| `split-db-api-explorer` | Split `db_api_explorer.py` + add `last_summary`/`flow` to `/db/features` | — |
| `studio-data-layer-migration` | Migrate Studio data/hook layer onto `db.features` | `split-db-api-explorer` |
| `studio-planboard-migration` | Migrate PlanBoard onto `db.features` + `db.events` | `studio-data-layer-migration` |

### `split-db-api-explorer`
- **Files:** `src/pathly_orchestrator/http_server/blueprints/ops/db_api_explorer.py`;
  `src/pathly_orchestrator/http_server/blueprints/ops/db_api_feature_detail.py` (NEW);
  `studio/src/renderer/src/types/global.d.ts`
- **What to build (gist):** extract the 4 per-feature detail routes into a new file (verified
  412-line SRP-split prerequisite), then add `last_summary` (via `read_last_agent_done(conn, pr,
  feat)`, same key the row is already built from — this is what makes goal-run features resolve
  correctly) and `flow` (already in the parsed state blob) to the `/db/features` list route and
  its filesystem-fallback path. Extend `DbFeature` with both fields.
- **Done when:** `db_api_explorer.py` under 400 lines; the split routes behave identically;
  `/db/features` rows carry `flow` + `last_summary` (including for a goal-run feature keyed by
  its run slug); `DbFeature` updated; `tsc --noEmit` clean; full test suite green.
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `ARCHITECTURE_PROPOSAL.md#key-decisions`,
  `ARCHITECTURE_PROPOSAL.md#risks-prioritized`

### `studio-data-layer-migration`
- **Files:** `store/commsApi.ts`; `components/Monitor/hooks/useMonitorSession.ts`;
  `components/HomeScreen/hooks/useProjectPlans.ts` (all under `studio/src/renderer/src/`)
- **What to build (gist):** build one `Map<feature, DbFeature>` per fetch from
  `window.pathly.db.features`; repoint `fetchFeatureState`/`fetchLastSummary`, the
  `useMonitorSession` proactive scan + active-flow detection, and `useProjectPlans`'s
  `scanRoot` onto that map instead of `readFile`. Delete the now-dead file reads.
- **Done when:** no `readFile` against STATE.json/EVENTS.jsonl remains in these 3 files; `tsc
  --noEmit` clean; a never-run feature still lists (server fallback); active-flow auto-select on
  startup still works; a feature card's last-activity line still populates for a goal-run feature.
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `AUDIT_MIRROR_READS.md#studio-typescript`

### `studio-planboard-migration`
- **Files:** `studio/src/renderer/src/components/PlanBoard/index.tsx`
- **What to build (gist):** repoint `fsmState` onto the same `db.features` map and the events
  list onto the existing `window.pathly.db.events` IPC. Leave the `PROGRESS.md` read untouched
  (separate, already-retired path).
- **Done when:** no `readFile` against STATE.json/EVENTS.jsonl remains; `tsc --noEmit` clean;
  stage + event content shown for an active feature is unchanged before/after; the PROGRESS.md
  read is untouched (diff-confirmed).
- **Context:** `ARCHITECTURE_PROPOSAL.md#component-map`, `AUDIT_MIRROR_READS.md#studio-typescript`

---

## Goal 3 — Enforce + cleanup

**Executor: `single`** (one agent drains the whole DAG in one session). Justification: mostly
independent, low-risk leaves (`delete-test-only-write-state`, the docstring/CLAUDE.md fix) plus
one moderate task (the CI gate) and one explicitly optional task — one continuous session drains
this backlog efficiently, and the same session that seeds the CI gate's allow-list can also
verify Goal 1+2 completion for its own precondition check without a fresh spawn.

**Dispatch this goal only after `events-artifacts-authority-cutover` and
`studio-db-read-migration` both show every task `done`** — see "Cross-goal dependency
rationale" above. `ci-mirror-read-gate` and `fix-docstrings-and-claude-md-classification` both
self-check this precondition via `GET /comms/goals` and will report blocked rather than proceed
if it isn't met.

| Slug | Title | Depends on |
|---|---|---|
| `ci-mirror-read-gate` | CI gate: fail the build on an un-marked mirror-file read | — *(cross-goal precondition, see above)* |
| `delete-test-only-write-state` | Delete the disk-only test-only `write_state` | — |
| `fix-docstrings-and-claude-md-classification` | Fix stale docstrings + add the classification table to CLAUDE.md | — *(cross-goal precondition, see above)* |
| `migrate-cli-back-py` *(optional)* | Migrate `cli/back.py` off direct disk reads | `ci-mirror-read-gate` |

### `ci-mirror-read-gate`
- **Files:** `scripts/check_no_mirror_reads.py` (NEW); `scripts/mirror_reads_allowlist.txt`
  (NEW); `.github/workflows/lint.yml`; `tests/consistency/test_no_mirror_reads.py` (NEW,
  optional); plus one allow-mirror-read marker comment per seeded allow-list site
- **What to build (gist):** a checker matching the `consistency` job's existing pattern
  (`check_version_sync.py` etc.) — regex-scans for read-ish access to the 4 mirror filenames,
  ignores writes, requires an inline `pathly:allow-mirror-read` marker + allow-list entry for
  any exemption. Seed the allow-list with the audit's confirmed DB-first fallbacks (verified
  read sites in the full prompt below) and mark those sites. Wire one new step into `lint.yml`.
- **Done when:** the checker exits 0 against the current tree; an injected unmarked read makes
  it fail with file:line, then reverted; the new `lint.yml` step runs; every allow-list entry
  has a live marker.
- **Context:** `ARCHITECTURE_PROPOSAL.md#key-decisions`, `AUDIT_MIRROR_READS.md#server-python`

### `delete-test-only-write-state`
- **Files:** `src/pathly_orchestrator/fsm/engine_actions.py`; `src/pathly_orchestrator/fsm/__init__.py`;
  `src/pathly_orchestrator/fsm/engine.py`; `tests/fsm_flows/test_fsm.py`
- **What to build (gist):** delete the verified disk-only `write_state` (468-478) + its two
  re-exports; repoint the test onto `eventlog.write_state` (DB-first), adjusting any pure-disk
  assertion to also check the DB.
- **Done when:** no `write_state` def under `fsm/`; no re-export in either module; the test
  calls `eventlog.write_state`; `tests/fsm_flows/` and the full suite are both green.
- **Context:** `ARCHITECTURE_PROPOSAL.md#key-decisions`, `AUDIT_MIRROR_READS.md#writers`

### `fix-docstrings-and-claude-md-classification`
- **Files:** `src/pathly_orchestrator/eventlog.py`;
  `src/pathly_orchestrator/http_server/blueprints/ops/telemetry_activity.py`;
  `src/pathly_orchestrator/http_server/blueprints/ops/telemetry_phase.py`; `CLAUDE.md`;
  `src/pathly_orchestrator/CLAUDE.md`
- **What to build (gist):** correct the 3 verified-stale docstrings; transcribe the canonical
  classification table + one-line rule from `ARCHITECTURE_PROPOSAL.md` into both CLAUDE.md files
  (only once Goal 1+2 are actually done — see PRECONDITION in the full prompt).
- **Done when:** no docstring claims a direct EVENTS.jsonl write; both CLAUDE.md files carry the
  table + rule; surrounding paragraphs still match live code (verify-then-fix, no blind rewrite);
  full test suite green (docstring-only change).
- **Context:** `ARCHITECTURE_PROPOSAL.md#canonical-classification-spec-in-scope-1`,
  `ARCHITECTURE_PROPOSAL.md#key-decisions`

### `migrate-cli-back-py` (optional)
- **Files:** `src/pathly_orchestrator/cli/back.py`; `scripts/mirror_reads_allowlist.txt`
- **What to build (gist):** lowest priority in this feature. Migrate `cli/back.py`'s disk
  round-trip onto `eventlog.read_state`/`read_events`/`write_state`; remove it from the
  allow-list and delete its marker once migrated.
- **Done when:** `cli/back.py` uses the DB-first helpers; it's off the allow-list with no
  marker; the CI checker still passes; `pathly-back` still rolls back correctly on a real
  feature; full test suite green.
- **Context:** `ARCHITECTURE_PROPOSAL.md#risks-prioritized`, `AUDIT_MIRROR_READS.md#writers`

---

## BOARD_DAG

```json
{"goals":[{"slug":"events-artifacts-authority-cutover","title":"EVENTS/ARTIFACTS authority cutover","executor":"team","tasks":[{"slug":"event-mirror-export","title":"Add event_mirror.py — additive DB→disk EXPORT for EVENTS.jsonl","depends_on":[],"files":["src/pathly_orchestrator/event_mirror.py","src/pathly_orchestrator/eventlog.py"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"phased-rollout"}],"prompt":"What to build: Add event_mirror.py next to board_mirror.py in src/pathly_orchestrator/, modeled byte-for-byte on that file's shape: a path resolver keyed by the resolved feature_dir (not a reconstructed 'pathly/features/<name>' guess, so debug/explore/goal runs export correctly), write_event_mirror(conn, feature_dir, project_root, feature) (serialize via db.queries.fsm_events.read_events, atomic tmp-file + os.replace, change-guard skip on byte-identical content), a debounced dirty-set + flusher (mark_event_dirty(feature_dir, project_root, feature), DEBOUNCE_SECONDS=0.5, own per-thread get_db() in the flusher thread — copy board_mirror._flusher_loop exactly), and backfill_event_mirrors(conn) off run_history project roots (copy backfill_board_mirrors). Do not import eventlog from this module (avoid a cycle) — read events via db.queries.fsm_events directly. Wire exactly one call into eventlog.append_event right after its existing _db.append_event(conn, project_root, feature, event) call (~line 128): event_mirror.mark_event_dirty(feature_dir, project_root, feature) — all three values are already local variables there. This task is purely additive: do not touch the existing agent-side EVENTS.jsonl dual-write in the completion-report/log-agent-done fragments; both writers coexist after this lands.\nFiles: src/pathly_orchestrator/event_mirror.py (NEW, model: src/pathly_orchestrator/board_mirror.py); src/pathly_orchestrator/eventlog.py (edit, one call added in append_event).\nDone when: (1) appending an event via eventlog.append_event updates EVENTS.jsonl on disk within one debounce window with content matching the DB row; (2) a repeat flush with no new events does not rewrite the file (mtime unchanged); (3) backfill_event_mirrors produces a correct EVENTS.jsonl for an existing feature that has DB history but no prior file; (4) the existing agent-side dual-write in completion-report/log-agent-done is untouched and still fires; (5) python -m pytest tests/ -q is green."},{"slug":"retire-events-dual-write","title":"Retire the agent-side EVENTS.jsonl dual-write","depends_on":["event-mirror-export"],"files":["src/pathly_data/core/skills/fragments/completion-report.md","src/pathly_data/core/skills/utilities/log-agent-done.md"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"risks-prioritized"}],"prompt":"What to build: Retire the agent-side EVENTS.jsonl dual-write now that event-mirror-export is proven. In core/skills/fragments/completion-report.md: delete the unconditional 'always dual-write to EVENTS.jsonl' block that runs after the try/except (the bare path = pathlib.Path(...); open(path,'a')... block, ~line 130-135), and replace the except-clause 'last resort' raw EVENTS.jsonl write inside if not _written: (~line 123-128) with a soft failure (log/print only, no disk write) — keep the try body's DB-primary eventlog.append_event call untouched. Apply the identical pair of edits to core/skills/utilities/log-agent-done.md (its 'AC2.5 dual-write' block ~line 124-129 and its except-clause last-resort write ~line 116-122). Then run pathly-setup claude --apply --repair followed by python -m build to propagate to all 4 adapters — never hand-edit an adapter _meta/ file.\nFiles: src/pathly_data/core/skills/fragments/completion-report.md; src/pathly_data/core/skills/utilities/log-agent-done.md.\nDone when: (1) neither file contains an unconditional or fallback write to a path ending EVENTS.jsonl; (2) the DB-primary eventlog.append_event call remains in both; (3) pathly-setup claude --apply --repair and python -m build both exit 0; (4) a real stage run still writes AGENT_DONE to the DB and EVENTS.jsonl updates only via event_mirror's export, never an agent-side append."},{"slug":"drop-artifacts-jsonl","title":"Drop ARTIFACTS.jsonl and its ledger scan","depends_on":[],"files":["src/pathly_data/core/skills/fragments/artifact-register.md","src/pathly_orchestrator/supervisor/artifact_reconcile.py","src/pathly_orchestrator/supervisor/terminal.py","src/pathly_orchestrator/fsm_ops_complete.py"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"risks-prioritized"}],"prompt":"What to build: Drop ARTIFACTS.jsonl entirely (its content already lives inside BOARD.json's artifacts array). In core/skills/fragments/artifact-register.md: delete step 2 (the python3 -c block appending to <feature_path>/ARTIFACTS.jsonl, ~line 11-22); keep step 1 (write <out_path>) and step 3 (the /comms/post board POST), renumber step 3 to step 2, and fix its 'skip silently — ARTIFACTS.jsonl and the file are the source of truth' sentence since ARTIFACTS.jsonl no longer exists (the on-disk <out_path> file is the fallback source of truth). In src/pathly_orchestrator/supervisor/artifact_reconcile.py: delete job #1 (the ledger-scan block reading ARTIFACTS.jsonl, ~line 46-80) and its docstring mention; keep job #2 (feedback/*.md scan) unchanged. Compensate for the lost server-down safety net: give reconcile_artifacts a way to attach the calling stage's own declared <out_path> directly (no disk mirror) — one viable approach is reusing manifest_role_file(agent_role, skill) (already used by fsm_compose.build_prompt to resolve <out_path>, see fsm_compose.py ~line 149-152) plus the stage's feature_path, threaded in as a new optional parameter from the two call sites (supervisor/terminal.py ~line 618, fsm_ops_complete.py ~line 262) — keep it optional so a caller with no single known out_path still works.\nFiles: src/pathly_data/core/skills/fragments/artifact-register.md; src/pathly_orchestrator/supervisor/artifact_reconcile.py; src/pathly_orchestrator/supervisor/terminal.py; src/pathly_orchestrator/fsm_ops_complete.py.\nDone when: (1) artifact-register.md no longer writes ARTIFACTS.jsonl; (2) artifact_reconcile.py has no ARTIFACTS.jsonl read and stays under 400 lines; (3) a stage's declared out_path artifact still appears attached on the board after a real run with the ledger gone; (4) pathly-setup claude --apply --repair + python -m build regenerate all 4 adapters; (5) python -m pytest tests/ -q is green."}]},{"slug":"studio-db-read-migration","title":"Studio → DB read migration","executor":"loop","tasks":[{"slug":"split-db-api-explorer","title":"Split db_api_explorer.py + add last_summary/flow to /db/features","depends_on":[],"files":["src/pathly_orchestrator/http_server/blueprints/ops/db_api_explorer.py","src/pathly_orchestrator/http_server/blueprints/ops/db_api_feature_detail.py","studio/src/renderer/src/types/global.d.ts"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"key-decisions"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"risks-prioritized"}],"prompt":"What to build: Two ordered changes (the split is a hard prerequisite — db_api_explorer.py is already 412 lines, over the 400-line cap, so new fields cannot just be appended). First, extract the four per-feature detail routes (/db/features/<feature>/events ~line 241, /agents ~line 274, /otel ~line 297, /runs ~line 328) into a new db_api_feature_detail.py in the same blueprint package, same bp-from-_db_api_bp registration pattern as sibling db_api_* files. Second, extend the remaining GET /db/features list route (db_features(), ~line 144-238) with two new fields inside its results.append({...}) dict (~line 215-227): last_summary via db.queries.fsm_events.read_last_agent_done(conn, pr, feat), keyed by the same (pr, feat) tuple the row is already built from (this is what makes goal-run features, keyed by run slug, resolve correctly); flow, already present in state_obj (~line 210) as state_obj.get('flow'). Add both fields to the _scan_filesystem_features fallback too (empty/None values are fine there). Extend the Studio DbFeature interface in renderer/src/types/global.d.ts (~line 53-63) with last_summary: string and flow: string.\nFiles: src/pathly_orchestrator/http_server/blueprints/ops/db_api_explorer.py; src/pathly_orchestrator/http_server/blueprints/ops/db_api_feature_detail.py (NEW); studio/src/renderer/src/types/global.d.ts.\nDone when: (1) db_api_explorer.py is under 400 lines and still serves /db/features plus the filesystem-scan fallback; (2) db_api_feature_detail.py serves the 4 extracted routes with identical responses to before the split; (3) GET /db/features rows include a non-null flow for every stateful feature and a populated last_summary for a feature with AGENT_DONE history, including a goal-run feature keyed by its run slug; (4) DbFeature has both new fields; (5) tsc --noEmit -p studio/tsconfig.web.json exits 0; (6) python -m pytest tests/ -q is green."},{"slug":"studio-data-layer-migration","title":"Migrate Studio data/hook layer onto db.features","depends_on":["split-db-api-explorer"],"files":["studio/src/renderer/src/store/commsApi.ts","studio/src/renderer/src/components/Monitor/hooks/useMonitorSession.ts","studio/src/renderer/src/components/HomeScreen/hooks/useProjectPlans.ts"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"AUDIT_MIRROR_READS.md","anchor":"studio-typescript"}],"prompt":"What to build: Repoint the Studio data/hook layer onto the DB-first window.pathly.db.features(projectRoot) IPC (already wired; the server-side _scan_filesystem_features fallback already covers never-run features — do not add a second client-side fallback). Build one Map<feature, DbFeature> per fetch in each file and read .state/.last_summary/.flow off it instead of reading files: commsApi.ts's fetchFeatureState (~line 1055-1064, currently reads STATE.json) and fetchLastSummary (~line 1090-1109, currently scans EVENTS.jsonl) become map lookups with their existing signatures/return types unchanged; useMonitorSession.ts's proactive STATE.json scan over planFolders (~line 53-81) and its active-flow Promise.any over 3 root candidates (~line 94-129) both switch to the same map (one call per project, not per folder/root); useProjectPlans.ts's per-folder scanRoot read (~line 12-31) switches to the map, and its team/debug/explore split can come from each row's flow field instead of which physical directory was scanned. Delete the STATE.json/EVENTS.jsonl readFile calls once nothing references them; leave any unrelated readFile usage in these files alone.\nFiles: studio/src/renderer/src/store/commsApi.ts; studio/src/renderer/src/components/Monitor/hooks/useMonitorSession.ts; studio/src/renderer/src/components/HomeScreen/hooks/useProjectPlans.ts.\nDone when: (1) none of the three files call readFile against a path ending STATE.json or EVENTS.jsonl; (2) tsc --noEmit -p studio/tsconfig.web.json exits 0; (3) a never-run feature (STATE.json on disk, no DB row) still lists via the server fallback; (4) an active flow still auto-selects the right Monitor tab on startup; (5) a feature card's last-activity line still populates, including for a goal-run feature."},{"slug":"studio-planboard-migration","title":"Migrate PlanBoard onto db.features + db.events","depends_on":["studio-data-layer-migration"],"files":["studio/src/renderer/src/components/PlanBoard/index.tsx"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"component-map"},{"artifact":"AUDIT_MIRROR_READS.md","anchor":"studio-typescript"}],"prompt":"What to build: Repoint PlanBoard/index.tsx's two remaining direct mirror reads the same way studio-data-layer-migration just did. fsmState (~line 145-153, reads STATE.json) becomes a db.features lookup keyed by activeTopic. The events list (~line 165-176, hand-parses EVENTS.jsonl line by line into EventEntry[]) switches to the existing window.pathly.db.events IPC (already wired — do not invent a new endpoint), adapting its response into the same EventEntry[] shape the component already renders. Leave the PROGRESS.md read (~line 155-163) untouched — a separate, already-retired path per the Component Map, out of scope here.\nFiles: studio/src/renderer/src/components/PlanBoard/index.tsx.\nDone when: (1) the file has no readFile call against STATE.json or EVENTS.jsonl; (2) tsc --noEmit -p studio/tsconfig.web.json exits 0; (3) opening PlanBoard for an active feature shows the same stage and the same event content as before the change; (4) the PROGRESS.md read is untouched (confirm via diff)."}]},{"slug":"enforce-and-cleanup","title":"Enforce + cleanup","executor":"single","tasks":[{"slug":"ci-mirror-read-gate","title":"CI gate: fail the build on an un-marked mirror-file read","depends_on":[],"files":["scripts/check_no_mirror_reads.py","scripts/mirror_reads_allowlist.txt",".github/workflows/lint.yml","tests/consistency/test_no_mirror_reads.py"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"key-decisions"},{"artifact":"AUDIT_MIRROR_READS.md","anchor":"server-python"}],"prompt":"What to build: A CI gate matching the existing consistency-job pattern in .github/workflows/lint.yml (which already runs check_version_sync.py / check_adapters.py / check_entry_points.py as separate steps — follow that shape, do not fold this into an existing script). scripts/check_no_mirror_reads.py scans src/**.py and studio/src/**.{ts,tsx} for read-ish access to the four literal filenames STATE.json, EVENTS.jsonl, ARTIFACTS.jsonl, BOARD.json (patterns like read_text, readFile, open with 'r', json.load(open(...)), .read(; ignore write patterns like json.dump/os.replace/open with 'w'/.write( entirely). A flagged read is allowed only with an inline marker on the same or previous line: '# pathly:allow-mirror-read: <reason>' (Python) or '// pathly:allow-mirror-read: <reason>' (TypeScript) — an unmarked read fails the script with a printed file:line list. scripts/mirror_reads_allowlist.txt enumerates the files permitted to carry a marker; a marker in a file not on the list also fails; a listed file with no live marker warns but does not fail. Seed the allow-list with this feature's already-audited DB-first fallbacks — fsm/engine_actions.py (build_baseline), fsm/engine_recover.py, fsm/engine_transitions.py (retry_count_by_key), db_api_explorer.py (_scan_filesystem_features/_parse_json_file), board_mirror_hydrate.py, and cli/back.py (until migrate-cli-back-py lands) — and add the matching marker comment at each of those actual read sites, or the gate fails on its own seed list. Wire one new step into the consistency job in lint.yml, same shape as the existing three. Optionally add tests/consistency/test_no_mirror_reads.py that imports and runs the same checker so it fails locally in pytest too.\nFiles: scripts/check_no_mirror_reads.py (NEW); scripts/mirror_reads_allowlist.txt (NEW); .github/workflows/lint.yml; tests/consistency/test_no_mirror_reads.py (NEW, optional); plus one allow-mirror-read marker comment at each seeded allow-list site.\nDone when: (1) python scripts/check_no_mirror_reads.py exits 0 against the current tree; (2) temporarily adding an unmarked STATE.json read anywhere under src/ makes it exit nonzero with the offending file:line, then revert; (3) the consistency job in lint.yml runs the new step; (4) every allow-list entry has a live marker.\nPRECONDITION: this task assumes EVENTS.jsonl/ARTIFACTS.jsonl agent dual-writes are already retired (goal events-artifacts-authority-cutover, tasks retire-events-dual-write + drop-artifacts-jsonl) and the Studio mirror reads are already migrated (goal studio-db-read-migration, tasks studio-data-layer-migration + studio-planboard-migration) — otherwise this gate fails red on real, not-yet-allow-listable reads. Confirm via GET /comms/goals that both of those goals show every task done before starting; if not, stop and report blocked rather than widening the allow-list to force a false green."},{"slug":"delete-test-only-write-state","title":"Delete the disk-only test-only write_state","depends_on":[],"files":["src/pathly_orchestrator/fsm/engine_actions.py","src/pathly_orchestrator/fsm/__init__.py","src/pathly_orchestrator/fsm/engine.py","tests/fsm_flows/test_fsm.py"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"key-decisions"},{"artifact":"AUDIT_MIRROR_READS.md","anchor":"writers"}],"prompt":"What to build: Delete the disk-only, no-DB write_state function at fsm/engine_actions.py:468-478 (writes STATE.json directly with no DB write — a latent trap, not a live bug; called only by tests). Drop its re-export from fsm/__init__.py and fsm/engine.py. Repoint tests/fsm_flows/test_fsm.py's calls onto eventlog.write_state (DB-first: writes fsm_state then STATE.json as a snapshot) instead, so the test exercises the real DB-authoritative path. If any assertion currently checks pure disk-only semantics (no DB row), switch it to also check eventlog.read_state / the DB — file-content assertions against STATE.json still pass unchanged since eventlog.write_state writes both.\nFiles: src/pathly_orchestrator/fsm/engine_actions.py; src/pathly_orchestrator/fsm/__init__.py; src/pathly_orchestrator/fsm/engine.py; tests/fsm_flows/test_fsm.py.\nDone when: (1) no write_state function definition remains under fsm/; (2) neither __init__.py nor engine.py re-exports it; (3) test_fsm.py calls eventlog.write_state wherever it used to call the deleted function; (4) python -m pytest tests/fsm_flows/ -q and the full python -m pytest tests/ -q are both green."},{"slug":"fix-docstrings-and-claude-md-classification","title":"Fix stale docstrings + add the classification table to CLAUDE.md","depends_on":[],"files":["src/pathly_orchestrator/eventlog.py","src/pathly_orchestrator/http_server/blueprints/ops/telemetry_activity.py","src/pathly_orchestrator/http_server/blueprints/ops/telemetry_phase.py","CLAUDE.md","src/pathly_orchestrator/CLAUDE.md"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"canonical-classification-spec-in-scope-1"},{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"key-decisions"}],"prompt":"What to build: Fix three docstrings that claim a write to EVENTS.jsonl when the code writes the DB: eventlog.py's module header (lines 1-14, specifically the 'The LLM writes these files directly using its Write/Bash tools' line — append_event/write_state write the DB; describe the DB-first reality plus the STATE/EVENTS export instead), telemetry_activity.py:41 ('Append an AGENT_DONE event to the feature's EVENTS.jsonl so SSE subscribers see it.' — it writes the DB via the shared event-append path; EVENTS.jsonl is a downstream export, not this function's target), telemetry_phase.py:70 (same pattern for PHASE_START/PHASE_DONE). Then add the canonical classification table + one-line rule to both CLAUDE.md (root) and src/pathly_orchestrator/CLAUDE.md's state-paragraph sections — transcribe the table from this feature's ARCHITECTURE_PROPOSAL.md (Canonical classification section): STATE.json/BOARD.json/EVENTS.jsonl are DB-to-disk EXPORTs, ARTIFACTS.jsonl is DROPPED, *.flow.yaml is a SEED, abilities/*.md and prompts/*.md are SEEDs; add the one-line rule verbatim from that same section.\nFiles: src/pathly_orchestrator/eventlog.py; src/pathly_orchestrator/http_server/blueprints/ops/telemetry_activity.py; src/pathly_orchestrator/http_server/blueprints/ops/telemetry_phase.py; CLAUDE.md; src/pathly_orchestrator/CLAUDE.md.\nDone when: (1) none of the three docstrings claim a direct EVENTS.jsonl write; (2) both CLAUDE.md files contain the classification table and the one-line rule; (3) every other claim in the edited CLAUDE.md sections still matches live code (verify-then-fix, do not blind-rewrite surrounding paragraphs); (4) python -m pytest tests/ -q is green.\nPRECONDITION: only write the classification table once BOTH events-artifacts-authority-cutover and studio-db-read-migration are done (otherwise the table describes a not-yet-true state) — confirm via GET /comms/goals first; if incomplete, either wait or write the table describing the current state and flag the gap in your completion report."},{"slug":"migrate-cli-back-py","title":"(Optional) Migrate cli/back.py off direct disk reads","depends_on":["ci-mirror-read-gate"],"files":["src/pathly_orchestrator/cli/back.py","scripts/mirror_reads_allowlist.txt"],"context_refs":[{"artifact":"ARCHITECTURE_PROPOSAL.md","anchor":"risks-prioritized"},{"artifact":"AUDIT_MIRROR_READS.md","anchor":"writers"}],"prompt":"What to build: OPTIONAL, lowest priority in this feature — pick up only after the other three enforce-and-cleanup tasks are done. Migrate cli/back.py's disk round-trip (it reads STATE.json + EVENTS.jsonl directly to pick the prior state, per AUDIT_MIRROR_READS.md's Writers section) onto eventlog.read_state / eventlog.read_events + eventlog.write_state (DB-first, matching every other CLI/FSM entry point). Once migrated, remove cli/back.py from scripts/mirror_reads_allowlist.txt and delete its allow-mirror-read marker (added by ci-mirror-read-gate) since it no longer needs the exemption.\nFiles: src/pathly_orchestrator/cli/back.py; scripts/mirror_reads_allowlist.txt.\nDone when: (1) cli/back.py calls eventlog.read_state/eventlog.write_state instead of raw file reads for its rollback decision; (2) it is no longer listed in mirror_reads_allowlist.txt and carries no allow-mirror-read marker; (3) python scripts/check_no_mirror_reads.py still exits 0; (4) pathly-back still correctly rolls back one FSM state on a real feature (manual smoke test); (5) python -m pytest tests/ -q is green."}]}]}
```
