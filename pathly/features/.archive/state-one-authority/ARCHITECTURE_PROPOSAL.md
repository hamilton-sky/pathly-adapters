# ARCHITECTURE PROPOSAL — state-one-authority

_Role: architect · Feature: state-one-authority · Rigor: standard · 2026-07-22_
_Implements: docs/ARCHITECTURE_ONE_AUTHORITY.md **Issue #4 (State)** · Inputs: SPEC.md, AUDIT_MIRROR_READS.md_

## Executive Summary

The DB (`~/.pathly/pathly.db`) is already the runtime authority for state, events, and
artifacts. Two of the four per-feature disk files honor that (`STATE.json`, `BOARD.json` are
DB→disk exports); two do not (`EVENTS.jsonl`, `ARTIFACTS.jsonl` are **agent-side appends** that
can silently diverge). This feature closes the gap by making every disk file a clean **SEED-in
XOR EXPORT-out**, migrating the last runtime *readers* of a mirror onto the DB, and adding a CI
gate so the rule can't rot.

The releasable spine is three clean seams: **(P1)** turn `EVENTS.jsonl` into a real DB→disk
export and drop `ARTIFACTS.jsonl` (its export already lives inside `BOARD.json`), retiring the
agent dual-write; **(P2)** migrate the 5–6 Studio sites that read `STATE.json`/`EVENTS.jsonl`
directly onto the already-wired `/db/features` endpoint (extended with `last_summary` + `flow`);
**(P3)** land the enforcement gate + delete the test-only disk-only `write_state` + fix the 3
stale docstrings. Every phase is behavior-neutral on the happy path; the gate lands **last**
because it would (correctly) fail red until P1+P2 remove the un-sanctioned reads.

The recommendation takes a firm position on the one genuinely balanced decision — **keep
`EVENTS.jsonl` as an export, drop `ARTIFACTS.jsonl`** — with the trade-off spelled out below.

## Canonical classification (SPEC in-scope #1)

The one table every disk file must fit into. This is the doc + the root-`CLAUDE.md` one-liner.

| File | Scope | Class (after this feature) | Direction | DB authority |
|---|---|---|---|---|
| `STATE.json` | feature | EXPORT | DB→disk (atomic) | `fsm_state` |
| `BOARD.json` | feature/project/global | EXPORT | DB→disk (debounced) | `comms_*` |
| `EVENTS.jsonl` | feature | **EXPORT** (was agent-append) | DB→disk (debounced) | `fsm_events` |
| `ARTIFACTS.jsonl` | feature | **DROPPED** (export folds into `BOARD.json`) | — | `comms_artifacts` |
| `*.flow.yaml` | core (packaged) | SEED | disk→DB on server start | `flow_nodes`/`flow_yaml` |
| `abilities/*.md`, `prompts/*.md` | project/global | SEED (file *is* authority) | disk→compose | n/a (no DB twin) |

**One-line rule (for root `CLAUDE.md`):** *The SQLite DB is the single runtime authority. Every
per-feature disk file is a SEED read once into the DB or an EXPORT written DB→disk for git/audit —
never round-tripped for a runtime decision. Runtime code reads the DB (or a DB-first, allow-listed
fallback), never the mirror.*

## In scope

- `EVENTS.jsonl` → pure DB→disk EXPORT (new `event_mirror.py`, modeled byte-for-byte on
  `board_mirror.py`); retire the agent dual-write in `completion-report` + `log-agent-done`.
- `ARTIFACTS.jsonl` → dropped; retire the `artifact-register` ledger append; `artifact_reconcile`
  keeps its feedback-file job, loses its ledger job.
- Studio: migrate 5–6 direct-mirror-read sites onto `/db/features` (+ `db.events`), extended with
  `last_summary` + `flow`.
- CI gate: `scripts/check_no_mirror_reads.py` + allow-list, wired into `lint.yml`.
- Delete the test-only disk-only `write_state`; fix the 3 stale docstrings.

## Out of scope

- Issues #1–#3 (Prompts / Telemetry / Context) — separate features.
- Any change to `STATE.json` / `BOARD.json` write behavior (they already obey the rule).
- The SEED side (flow-YAML replace-semantics — already fixed; only re-documented in the table).
- No DB schema migration (constraint: P0 is behavior-neutral, DB stays authoritative).

## Before / after — the two divergent files

```
BEFORE (diverges)                        AFTER (one authority)
─────────────────                        ─────────────────────
agent ─┬─► /runner/event ─► fsm_events    agent ─► /runner/event ─► fsm_events (DB)
       └─► open("a") EVENTS.jsonl  ⚠         (append_event)              │
           (server events never reach it)                               │ debounced hook
                                                              event_mirror.flush_dirty
Studio ─► readFile(EVENTS.jsonl) ⚠                                      ▼ atomic temp+rename
        readFile(STATE.json)   ⚠           EVENTS.jsonl  (pure DB→disk EXPORT, git-trackable)

                                          Studio ─► window.pathly.db.features / db.events
                                                    (DB-first; server-side FS fallback only)

agent ─► ARTIFACTS.jsonl ─► reconcile     agent ─► /comms/post ─► comms_artifacts (DB)
         (disk→DB import) ⚠                                          │ already serialized into
                                                                     ▼ BOARD.json "artifacts"
                                          (no separate ARTIFACTS.jsonl file)
```

## Component Map

**Server (Python)** — respects the 400-line SRP cap; the one over-limit file is split, not grown.

| File | New/Edit | What changes |
|---|---|---|
| `pathly_orchestrator/event_mirror.py` | **NEW** (~150 ln) | DB→disk EXPORT for `EVENTS.jsonl`: path resolver, atomic temp+rename, change-guard, debounced flusher, startup backfill — mirror of `board_mirror.py` |
| `pathly_orchestrator/eventlog.py` | edit | wire `event_mirror.mark_event_dirty(feature_dir, project_root, feature)` into `append_event` (single append chokepoint); fix module docstring (P3) |
| `core/skills/fragments/completion-report.md` | edit | delete the "always dual-write to EVENTS.jsonl" block (~130–135) + the last-resort disk write (~124–128); DB path (`/runner/event` + eventlog fallback) stays |
| `core/skills/utilities/log-agent-done.md` | edit | delete the "AC2.5 dual-write" block (~124–128) + last-resort disk write (~117–122) |
| `core/skills/fragments/artifact-register.md` | edit | delete step 2 (ARTIFACTS.jsonl append); keep step 3 (board POST) as the DB path |
| `adapters/*/_meta/**`, built skill outputs | **regen** | `pathly-setup claude --apply --repair` + `python -m build` (adapter sync rule — all 4 adapters) |
| `supervisor/artifact_reconcile.py` | edit | retire ledger job #1 (ARTIFACTS.jsonl scan); keep job #2 (`feedback/*.md` → board) |
| `http_server/blueprints/ops/db_api_explorer.py` | edit | add `last_summary` + `flow` to `/db/features`; **SPLIT** feature-detail routes out (file is 412 ln, already over cap) |
| `http_server/blueprints/ops/db_api_feature_detail.py` | **NEW** | extracted `/db/features/<feature>/{events,agents,otel,runs}` routes (SRP split, lands db_api_explorer back under 400) |
| `http_server/blueprints/ops/telemetry_activity.py` | edit | docstring fix (line 41: writes DB, not EVENTS.jsonl) |
| `http_server/blueprints/ops/telemetry_phase.py` | edit | docstring fix (line 70) |
| `fsm/engine_actions.py` | edit | **delete** disk-only `write_state` (468–478) |
| `fsm/__init__.py`, `fsm/engine.py` | edit | drop the re-export of the deleted `write_state` |
| `tests/fsm_flows/test_fsm.py` | edit | repoint `write_state` calls to `eventlog.write_state` (DB-first) |
| `scripts/check_no_mirror_reads.py` | **NEW** | CI gate: fail on an un-marked runtime read of a mirror file |
| `scripts/mirror_reads_allowlist.txt` | **NEW** | sanctioned DB-first-fallback sites (reviewed exemptions) |
| `.github/workflows/lint.yml` | edit | add the check to the `consistency` job |
| `tests/consistency/test_no_mirror_reads.py` | **NEW** (opt) | run the checker inside pytest too |
| root `CLAUDE.md`, `pathly_orchestrator/CLAUDE.md` | edit | classification table + one-line rule + new EVENTS-export note (doc-sync) |

**Studio (TypeScript)** — renderer → preload → main; renderer stops reading files.

| File | New/Edit | What changes |
|---|---|---|
| `store/commsApi.ts` | edit | `fetchFeatureState` (1058) + `fetchLastSummary` (1093) → look up a `Map<feature, DbFeature>` from `window.pathly.db.features`; drop the STATE.json/EVENTS.jsonl `readFile` |
| `components/Monitor/hooks/useMonitorSession.ts` | edit | active-flow scan (59) + pipelineStates resolve (114) → the features list (`state`, `flow`); drop STATE.json reads |
| `components/HomeScreen/hooks/useProjectPlans.ts` | edit | feature list (23) → `db.features` (its server-side FS fallback already covers never-run features); drop per-folder STATE.json scan |
| `components/PlanBoard/index.tsx` | edit | fsmState (148) → `db.features`; events list (**166**, EVENTS.jsonl) → `window.pathly.db.events`; PROGRESS.md (156) is a separate retired path, leave |
| `renderer/src/types/global.d.ts` (+ `DbFeature` type home) | edit | add `last_summary: string` + `flow: string` to `DbFeature` |

Reused as-is: `window.pathly.db.features` / `db.events` IPC (already wired in `main/ipc/db.ts` +
`preload/index.ts`), `board_mirror.py` (the copy source), `read_last_agent_done`
(`db/queries/fsm_events.py`).

## Key Decisions

### 1. `EVENTS.jsonl` = keep-as-EXPORT · `ARTIFACTS.jsonl` = DROP

Treat the two files separately — their *directions* differ, so "keep vs drop" resolves oppositely.

- **`EVENTS.jsonl` → convert to a pure DB→disk EXPORT.** It is a would-be mirror of `fsm_events`
  currently mis-implemented as an agent-side append. Build `event_mirror.py` as a line-for-line
  analogue of `board_mirror.py` and retire the fragment dual-write. **Why export, not drop:** its
  only remaining runtime reader (Studio `fetchLastSummary`) migrates to the DB in P2, so *drop* is
  defensible — **but** `EVENTS.jsonl` carries lifecycle + telemetry events (`STATE_TRANSITION`,
  `AGENT_DONE` with cost/tokens, `GATE_FAILED`, `RETRY`) that `BOARD.json` does **not**, so the
  git-diff/audit value is real and *not* already covered. Keeping it as an export also preserves
  the symmetry that makes the model teachable: **all three** feature-dir JSON files
  (`STATE`/`BOARD`/`EVENTS`) are DB→disk exports. And an export *cannot* diverge — it fixes the
  SPEC's stated bug (server-originated events never reaching disk) for free.
  *Trade-off:* ~150 lines of new exporter + a debounced flusher for a file no runtime code reads.
  If the team decides the DB backup alone satisfies audit, dropping `EVENTS.jsonl` is the lighter
  path and still satisfies the north-star — this is the single call I'd re-open if surface budget
  is tight.

- **`ARTIFACTS.jsonl` → DROP the separate file.** It is an *import* buffer (agent→disk→DB via
  `artifact_reconcile`), and its content — artifact metadata — is **already exported to disk inside
  `BOARD.json`** (`serialize_board` embeds the `artifacts` array). So a separate artifacts export
  would be pure redundancy. The live DB path is the `/comms/post` the `artifact-register` fragment
  already sends (step 3). In runner/headless mode the FSM server is up *by construction* (it drives
  the run), so that POST succeeds; the ledger only ever backstopped server-down interactive runs.
  *Trade-off:* an artifact produced while the server is down and never reconciled is lost — mitigated
  because (a) headless always has the server, (b) `reconcile_artifacts` can attach the stage's known
  `<out_path>` (which the gate already validates) without any disk mirror. `artifact_reconcile` job #2
  (`feedback/*.md`) is unrelated and stays.

### 2. Studio DB-first migration → `/db/features` (+ `last_summary`, `flow`)

The endpoint already exists, is DB-first, has a server-side FS fallback, and is already wired to
the renderer as `window.pathly.db.features(projectRoot): Promise<DbFeature[]>`. It returns
`{project_root, feature, state, events, invocations, total_tokens, cost_usd, updated_at, source}`.
Two fields are missing for full parity with the disk reads:

- **`last_summary`** — replaces `fetchLastSummary`'s EVENTS.jsonl scan. Source it from
  `read_last_agent_done(conn, project_root, feature)` (`fsm_events`, `ORDER BY seq DESC LIMIT 1`) —
  keyed identically to how `/db/features` keys features, so a **goal-run** feature (where the event
  is keyed by the run slug `<fsm_feature>`, not the board scope `<feature>`) resolves correctly.
- **`flow`** — replaces the `state.flow` read in `useMonitorSession`/`useProjectPlans` (team vs
  debug vs explore). It is already in the parsed `state_json` blob; expose it (zero extra query).

Migration then collapses **all** the disk reads to one fetch per project: build a
`Map<feature, DbFeature>` and read `.state` / `.last_summary` / `.flow` off it. Drop the
per-folder STATE.json scan entirely — `_scan_filesystem_features` already covers never-run
features server-side (and is the *one* sanctioned mirror read, allow-listed). `PlanBoard`'s events
list moves to the existing `db.events` IPC.
*Trade-off:* the migration centralizes the last legitimate disk-read into a single server endpoint
rather than spreading it across the renderer — exactly "one authority," at the cost of one endpoint
edit that must stay backward-compatible (additive fields only).

**SRP note:** `db_api_explorer.py` is **412 lines** — already over the 400-line cap. The two new
fields cannot just be appended. Extract the four `/db/features/<feature>/{events,agents,otel,runs}`
detail routes into a new `db_api_feature_detail.py`; that drops the explorer file well under 400
and leaves room for the `last_summary`/`flow` logic in the list route. This split is a prerequisite
of P2, not optional.

### 3. CI enforcement gate — marker-comment + reviewed allow-list

No existing test enforces the dash-safety mirrors (verified — the "mirror test" is conceptual); the
real precedent is the `consistency` job in `lint.yml`, which runs `scripts/check_*.py` steps
(`check_version_sync`, `check_adapters`, `check_entry_points`). Model the gate on that.

**Mechanism (robust to line churn, self-documenting):**
- `scripts/check_no_mirror_reads.py` scans `src/**.py` + `studio/src/**.{ts,tsx}` for **read-ish**
  access to the four literal filenames (`STATE.json`, `EVENTS.jsonl`, `ARTIFACTS.jsonl`,
  `BOARD.json`) — `read_text`/`readFile`/`open(...,'r')`/`json.load(open(...))`/`.read(`. **Writes**
  (`json.dump`, `os.replace`, `open(...,'w')`, `.write(`) are ignored — exporters must write.
- Any flagged read must carry an inline marker: `# pathly:allow-mirror-read: <reason>` (Py) or
  `// pathly:allow-mirror-read: <reason>` (TS) on the same or previous line. A read without a marker
  **fails the build**.
- `scripts/mirror_reads_allowlist.txt` enumerates the *files* permitted to carry a marker. A marker
  in a non-listed file fails (no silent self-exemption); a list entry with **no** live marker warns
  (stale allow-list). This is the dash-safety "canonical list + enforced parity" shape.
- Seed the allow-list with the audit's sanctioned DB-first fallbacks: `fsm/engine_actions.py`
  (`build_baseline`), `fsm/engine_recover.py`, `fsm/engine_transitions.py` (`retry_count_by_key`),
  `db_api_explorer.py` (`_scan_filesystem_features`/`_parse_json_file`),
  `board_mirror_hydrate.py` (fresh-clone SEED import), and `cli/back.py` (human CLI) unless P3d
  migrates it.

**Wire-up:** one step in the `consistency` job of `.github/workflows/lint.yml`:
`- run: python scripts/check_no_mirror_reads.py`. Optionally also a pytest (`test_no_mirror_reads.py`)
that imports and runs the checker, so it fails locally in the suite too.
*Trade-off:* a regex heuristic can't follow an indirected read (`p = base + '/STATE.json';
readFile(p)`) — accepted, because in this codebase the four names are near-universally inline string
literals (verified across the audit sites). The gate targets the literal, documents the limitation,
and the allow-list makes every exemption a reviewed line.

### 4. Test-only disk-only `write_state` → DELETE + repoint the test

`fsm/engine_actions.py:468–478` `write_state` writes STATE.json with **no DB write**, re-exported
via `fsm/__init__.py` + `engine.py`, called only by `tests/fsm_flows/test_fsm.py`. It is not a live
bug (audit-verified — the scout over-claimed) but it is a loaded gun: a disk-only writer can plant a
STATE.json that diverges from `fsm_state`, the exact anti-pattern Issue #4 forbids, and it's
re-exported from two modules where a future caller could pick it up.
**Recommendation: delete it and repoint the test to `eventlog.write_state`** (DB-first + STATE.json
export). This also makes the test exercise the *real* path — echoing the FSM-next-state lesson
("drive the real FSM through a real transition," not a mock on both sides).
*Trade-off vs. delegate:* aliasing it to `eventlog.write_state` is one line and lower-risk, but
leaves a redundant name; deletion removes the trap outright. If `test_fsm.py` asserts pure
disk-no-DB semantics, switch those asserts to `read_state` (DB) — `eventlog.write_state` writes
STATE.json too, so file-content asserts still pass against the temp-sqlite fixture.

### 5. Docstring fixes (+ doc-sync)

Three docstrings claim a write to `EVENTS.jsonl` that actually goes to the DB: `eventlog.py:1–14`
(module header + the "LLM writes these files directly" line), `telemetry_activity.py:41`,
`telemetry_phase.py:70`. Correct them to describe the DB-first reality (+ the STATE/EVENTS export).
*Trade-off:* none — pure doc accuracy. Per the doc-sync rule these ride in the **same commit** as
the code they describe, and the root/orchestrator `CLAUDE.md` state paragraphs gain the
classification table + one-line rule in that commit.

## Dependency-direction check

**Server** — `db/ → runner/ → supervisor/ → http_server/`, lazy imports in handlers.
- `event_mirror.py` is a **top-level** module (like `board_mirror.py`), importing only
  `db.queries.fsm_events.read_events` + `db.connection.get_db` + `storage_paths`. It must **not**
  import `eventlog` (avoid a cycle — it reads events via `db` directly, exactly as `board_mirror`
  reads messages via `db`, never via the comms modules).
- `eventlog.append_event` (top-level) calling `event_mirror.mark_event_dirty` is a sibling
  top-level→top-level import — no layer crossing. The debounced flusher uses its own per-thread
  `get_db()` connection (sqlite is `check_same_thread`), copied from `board_mirror._flusher_loop`.
- **Nested-path nuance:** the exporter keys the dirty set by the **resolved `feature_dir`**
  (`append_event` already has it at `_resolve_path(...).resolve()`), not by a reconstructed
  `pathly/features/<name>`, so debug/explore/goal runs (which live under `pathly/debugs/…`,
  `pathly/explorations/…`, `…/goals/<slug>/`) export to the right directory. This is the one design
  divergence from `board_mirror` (which keys by `(board, scope)`), and it is deliberate.
- The `/db/features` split stays inside `http_server/blueprints/ops/` (may import `db`); no new
  cross-layer edge.

**Studio** — renderer → preload → main.
- The migrated hooks call `window.pathly.db.features` / `db.events` (preload contextBridge → `db.ts`
  `ipcMain.handle` → `fsmGet`). Removing the `readFile(...)` calls *enforces* the direction: the
  renderer no longer touches the filesystem for state; `main/ipc/db.ts` is the only hop that talks
  to the FSM server. No renderer `fs` access remains for these files.

## Risks (prioritized)

1. **[HIGH] EVENTS export cutover window.** Retiring the agent dual-write *before* the exporter is
   proven would drop events. *Mitigation:* land `event_mirror.py` **additively first** (P1a — it
   writes the same file alongside the still-live agent append; change-guard prevents churn), verify
   byte-parity on a real run, then retire the agent write (P1b). Two shippable steps, never a gap.
2. **[HIGH] `last_summary` keying for goal runs.** If sourced by the wrong key, goal-run cards show
   blank/stale "last activity" (the `<fsm_feature>` vs `<feature>` telemetry split). *Mitigation:*
   use `read_last_agent_done(project_root, feature)` keyed identically to the `/db/features` row;
   add a test over a goal-run feature.
3. **[MED] Studio behavior-neutrality — vanishing cards.** A feature with a STATE.json but no DB
   row must still list, or its card disappears post-migration. *Mitigation:* rely on the endpoint's
   `_scan_filesystem_features` fallback (allow-listed); test a never-run feature still appears.
4. **[MED] CI gate false pos/neg.** Regex over two languages can mis-classify a write as a read or
   miss an aliased read. *Mitigation:* target inline literals only, separate read vs write token
   sets, document the indirection limitation, keep every exemption a reviewed allow-list line.
5. **[MED] EVENTS full-rewrite cost.** `EVENTS.jsonl` grows unbounded; a full rewrite per flush is
   O(n). *Mitigation:* the 0.5s debounce coalesces bursts and per-feature logs are KB-scale;
   note a seq-tracked incremental append as a future optimization if a log ever grows large.
6. **[MED] `ARTIFACTS.jsonl` drop loses the server-down safety net.** *Mitigation:* headless always
   has the server; add the `<out_path>` attach in `reconcile_artifacts` so a declared output is
   attached from the FSM's own record, not a disk mirror.
7. **[LOW] `cli/back.py` remains a disk round-trip** (reads STATE.json + EVENTS.jsonl to pick the
   prior state, human-invoked). *Mitigation:* migrate to `read_state`/`read_events` + `write_state`
   (optional P3d); until then, allow-list it (human CLI, not a headless runtime decision).

## Phased Rollout

Ordered so each phase is independently shippable and behavior-neutral; the gate lands last (it
would fail red until the reads are gone). This is the planner's goal-decomposition seam.

**Phase 1 — EVENTS/ARTIFACTS authority cutover.**
- *1a (additive, ship):* add `event_mirror.py` (DB→disk export + debounced hook in
  `eventlog.append_event` + startup backfill). Runs alongside the existing agent dual-write; verify
  byte-parity on a real run. No removals yet.
- *1b (removal, ship):* retire the EVENTS.jsonl dual-write in `completion-report` + `log-agent-done`;
  retire the `artifact-register` ledger append and drop `ARTIFACTS.jsonl`; update
  `artifact_reconcile` (drop job #1, add `<out_path>` attach, keep job #2). Run
  `pathly-setup claude --apply --repair` + `python -m build` (all 4 adapters).

**Phase 2 — Studio → DB read migration.**
- *2a (server, additive, ship):* split `db_api_explorer.py` (extract feature-detail routes to
  `db_api_feature_detail.py`); add `last_summary` + `flow` to `/db/features`; extend the `DbFeature`
  type. Existing consumers unaffected.
- *2b (Studio, ship):* repoint the 5–6 sites (`commsApi.fetchFeatureState`/`fetchLastSummary`,
  `useMonitorSession` ×2, `useProjectPlans`, `PlanBoard` STATE.json + EVENTS.jsonl) onto
  `db.features` / `db.events`; delete the direct `readFile` calls.

**Phase 3 — Enforce + cleanup.**
- *3a:* add `scripts/check_no_mirror_reads.py` + `scripts/mirror_reads_allowlist.txt`; wire into
  `lint.yml` consistency job (+ optional pytest). Seed the allow-list with the sanctioned fallbacks.
- *3b:* delete the test-only disk-only `write_state` (+ re-exports); repoint `test_fsm.py` to
  `eventlog.write_state`.
- *3c:* fix the 3 docstrings; update root + orchestrator `CLAUDE.md` (classification table +
  one-line rule + EVENTS-export note).
- *3d (optional):* migrate `cli/back.py` to DB reads/writes and remove it from the allow-list.
