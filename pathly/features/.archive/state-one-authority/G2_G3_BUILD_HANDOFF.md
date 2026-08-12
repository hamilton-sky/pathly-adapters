# BUILD HANDOFF — state-one-authority G2 + G3 (fresh session)

_Written 2026-07-22 after G1 landed. Paste this whole file as the opening prompt of a new
Claude Code session to finish the feature. G1 is DONE; this covers the remaining two goals._

## TL;DR

Implement the rest of `state-one-authority` (docs/ARCHITECTURE_ONE_AUTHORITY.md Issue #4) — make
the DB the single runtime authority, every disk file a one-way SEED/EXPORT. **G1 (EVENTS/ARTIFACTS
cutover) is BUILT + committed** (`8ced01d9`). Build **G2 → then G3**, gated per goal, IN ORDER.

## Setup

- Repo `C:\Users\Yafit\pathly-adapters`. Work on the EXISTING branch `dogfood/state-one-authority`
  (`git checkout dogfood/state-one-authority`; confirm `git branch --show-current`). Never commit to
  master, never push.
- FSM server: `curl -s http://127.0.0.1:8765/health`. If down, start it, then continue.
- Local Python reads STALE site-packages — run every python/pytest/pathly-setup/build with
  `PYTHONPATH=src`.
- Verification gotcha: never `cmd | tail` for pass/fail (masks the exit code). Redirect to a file and
  `echo "EXIT=$?"` separately. Studio typecheck is `studio/node_modules/.bin/tsc`, not root tsc.

## READ FIRST (authoritative, on disk + on the board)

- `pathly/features/state-one-authority/ARCHITECTURE_PROPOSAL.md` (design — Component Map, Key
  Decisions, Risks)
- `pathly/features/state-one-authority/IMPLEMENTATION_PLAN.md` (the final ```json BOARD_DAG block =
  every task's exact prompt + Files + Done-when)
- `pathly/features/state-one-authority/AUDIT_MIRROR_READS.md` (the Studio disk-read sites G2 removes)

## Build approach (as agreed with the user)

Build **in-session** (NOT the headless runner — it needs Studio as a PTY host and none is connected:
`/health` shows `sse_clients:0`; also a headless builder would edit Pathly's own src and collide).
Replicate the Pathly fragments for grounding, and keep the board honest with a strict per-task cadence:

1. **Claim**: `POST /comms/tasks/claim {"message_id":"<task id>","run_id":"insession-<slug>"}`
   (auto-posts a "Started" status).
2. **Ground the task the fragment way** (do this before editing):
   - board-context block: `POST /comms/agent-context/preview
     {"scope":"state-one-authority","board":"feature","project_root":"C:/Users/Yafit/pathly-adapters",
     "task_description":"<task text>","task_id":"<id>"}` → read the `block`.
   - code intel on files you'll touch: `POST /code/query
     {"op":"impact","target":"<file>","role":"builder","project_root":"C:/Users/Yafit/pathly-adapters","scope":"(interactive)"}`.
   - context_refs: the task's `context_refs` point at ARCHITECTURE_PROPOSAL sections — read them.
3. **Build** the task's Files, then **VERIFY its Done-when** (run it, don't trust it).
4. **Status**: `POST /comms/post {"feature":"state-one-authority","scope":"state-one-authority",
   "board":"feature","from":"builder","type":"status","reply_to":"<task id>","text":"..."}`
   — NB the fields are `feature` + `from` (NOT `from_agent`).
5. **Complete**: `POST /comms/tasks/complete {"message_id":"<task id>","feature":"state-one-authority"}`.
6. **Commit per GOAL** on the branch (not per task). STOP + summarize after each goal for review.

List task ids by slug:
`curl -s "http://127.0.0.1:8765/comms/tasks?feature=state-one-authority&board=feature&scope=state-one-authority"`
Goal rollup: `GET /comms/goals?feature=state-one-authority&scope=state-one-authority&project_root=C:/Users/Yafit/pathly-adapters`

## Learnings from G1 that carry forward

- **`get_ready_tasks` resolves `depends_on` ONLY within a goal.** Cross-goal ordering is a prose
  precondition, not a DAG edge. So finish G2 fully, THEN G3. Within a goal, respect `depends_on`.
- **`EVENTS.jsonl` / `ARTIFACTS.jsonl` are now gitignored** (`pathly/**`, like `BOARD.json`) and
  untracked. This was the user-approved fix for the exporter/migrations backfill writing real files
  during tests. Do not re-track them.
- **Editing a core skill/fragment requires**: `PYTHONPATH=src pathly-setup claude --apply --repair`
  then `PYTHONPATH=src python -m build` (both must exit 0), THEN regenerate any changed golden
  compose snapshots — `tests/install_skills/test_compose.py` asserts
  `compose_skill(sk,"claude") == tests/snapshots/<sk>.claude.md`; regenerate by writing the compose
  output back to the snapshot file, after eyeballing the diff is exactly your intended change. Keep
  code-block comments ASCII (Windows cp1252). **G2 is mostly Python + TypeScript, NOT fragments —
  so G2 likely needs NO setup/build/snapshot step; G3 has none either.**
- After adding/moving a test, rerun `PYTHONPATH=src python scripts/gen_test_index.py`.

---

## GOAL 2 — Studio → DB read migration (goal `e9884243`, executor `loop`)

Run these 3 tasks IN ORDER (real `depends_on` chain):

1. **`split-db-api-explorer`** (`a1f35df7-2dd8-4139-ba4f-2d5d865b0c4e`, depends_on: [])
   - Files: `src/pathly_orchestrator/http_server/blueprints/ops/db_api_explorer.py`,
     `.../ops/db_api_feature_detail.py` (NEW), `studio/src/renderer/src/types/global.d.ts`
   - `db_api_explorer.py` is 412 lines (over the 400 cap) — SPLIT FIRST: extract the 4 per-feature
     detail routes (`/db/features/<feature>/{events,agents,otel,runs}`) into `db_api_feature_detail.py`
     (same bp registration pattern as sibling `db_api_*`). THEN add `last_summary` (via
     `db.queries.fsm_events.read_last_agent_done(conn, pr, feat)` — same (pr,feat) key the row is
     built from, so goal-run features resolve) + `flow` (`state_obj.get('flow')`) to the `/db/features`
     list route AND the `_scan_filesystem_features` fallback. Extend the `DbFeature` interface with
     `last_summary: string` + `flow: string`.
   - Done-when: explorer < 400 lines; split routes behave identically; `/db/features` rows carry
     `flow` + populated `last_summary` (incl. a goal-run feature by run slug); `DbFeature` updated;
     `cd studio && node_modules/.bin/tsc --noEmit -p tsconfig.web.json` exits 0; `PYTHONPATH=src
     python -m pytest tests/ -q` green.

2. **`studio-data-layer-migration`** (`3c95a278-1ee8-431d-85b5-278efacc9856`, depends_on:
   [split-db-api-explorer])
   - Files (under `studio/src/renderer/src/`): `store/commsApi.ts`,
     `components/Monitor/hooks/useMonitorSession.ts`, `components/HomeScreen/hooks/useProjectPlans.ts`
   - Build one `Map<feature, DbFeature>` per fetch from `window.pathly.db.features(projectRoot)` and
     read `.state`/`.last_summary`/`.flow` off it instead of `readFile`. Repoint
     `fetchFeatureState` (was STATE.json) + `fetchLastSummary` (was EVENTS.jsonl scan), the
     `useMonitorSession` proactive scan + active-flow detection, and `useProjectPlans` scanRoot. Do
     NOT add a client-side fallback (the server `_scan_filesystem_features` already covers never-run
     features). Delete the dead STATE.json/EVENTS.jsonl `readFile` calls.
   - Done-when: no `readFile` of STATE.json/EVENTS.jsonl in these 3 files; tsc clean; a never-run
     feature still lists; active flow still auto-selects on startup; last-activity still populates
     (incl. goal-run feature).

3. **`studio-planboard-migration`** (`92797ac3-da5b-4570-a163-c80345fcc0c8`, depends_on:
   [studio-data-layer-migration])
   - File: `studio/src/renderer/src/components/PlanBoard/index.tsx`
   - `fsmState` (was STATE.json) → `db.features` lookup by `activeTopic`; events list (was hand-parsed
     EVENTS.jsonl) → existing `window.pathly.db.events` IPC, adapted into the same `EventEntry[]`
     shape. LEAVE the `PROGRESS.md` read untouched (separate, already-retired path).
   - Done-when: no STATE.json/EVENTS.jsonl `readFile`; tsc clean; same stage + events shown as
     before; PROGRESS.md read untouched (diff-confirm).

Then commit G2 on the branch, stop + summarize for review.

---

## GOAL 3 — Enforce + cleanup (goal `ae858041`, executor `single`)

**PRECONDITION: only start G3 after G1 + G2 both show every task done** (`GET /comms/goals`). The CI
gate fails red on any still-live mirror read; G1+G2 are exactly what remove them. Do NOT widen the
allow-list to force a green — if a precondition isn't met, STOP and report blocked.

- **`ci-mirror-read-gate`** (`d0dd028f-...`): `scripts/check_no_mirror_reads.py` (NEW) +
  `scripts/mirror_reads_allowlist.txt` (NEW) + wire one step into `.github/workflows/lint.yml`
  consistency job (+ optional `tests/consistency/test_no_mirror_reads.py`). Regex-scan `src/**.py` +
  `studio/src/**.{ts,tsx}` for read-ish access to the 4 mirror filenames; require an inline
  `# pathly:allow-mirror-read: <reason>` marker + allow-list entry for any exemption. Seed the
  allow-list with the audited DB-first fallbacks (fsm/engine_actions build_baseline, engine_recover,
  engine_transitions retry_count_by_key, db_api_explorer _scan_filesystem_features/_parse_json_file,
  board_mirror_hydrate, cli/back.py) and mark each site.
- **`delete-test-only-write-state`** (`2a1e477f-...`): delete the disk-only `write_state` at
  `fsm/engine_actions.py:468-478` + its re-exports in `fsm/__init__.py` + `fsm/engine.py`; repoint
  `tests/fsm_flows/test_fsm.py` onto `eventlog.write_state` (DB-first).
- **`fix-docstrings-and-claude-md-classification`** (`0ffcd8f3-...`): fix 3 stale docstrings
  (`eventlog.py:1-14`, `telemetry_activity.py:41`, `telemetry_phase.py:70` — they claim a direct
  EVENTS.jsonl write; it's the DB). Add the canonical classification table + one-line rule to root
  `CLAUDE.md` + `src/pathly_orchestrator/CLAUDE.md`. **IMPORTANT correction from G1:** phrase the
  `EVENTS.jsonl` row as a **gitignored EXPORT (like BOARD.json)**, NOT "git-trackable" — G1 gitignored
  it because the exporter rewrites it on every server start (the proposal's "git-trackable" wording is
  superseded by that reality). `ARTIFACTS.jsonl` = DROPPED (also gitignored). Verify-then-fix the
  surrounding CLAUDE.md paragraphs — don't blind-rewrite.
- **`migrate-cli-back-py`** (`b7bc3dc9-...`, OPTIONAL, depends_on: [ci-mirror-read-gate]): migrate
  `cli/back.py`'s STATE.json+EVENTS.jsonl round-trip onto `eventlog.read_state/read_events/write_state`;
  remove it from the allow-list + its marker.

Then commit G3, stop + summarize. Feature complete.

## Rules

1. ORDER: G2 fully, then G3. Within a goal, respect `depends_on`.
2. Verify each Done-when (run it). Python: `PYTHONPATH=src python -m pytest tests/ -q` green. Studio:
   `cd studio && node_modules/.bin/tsc --noEmit -p tsconfig.web.json`, redirect + echo exit code.
3. Keep living docs in sync in the SAME commit (that IS G3's docstring task).
4. Commit per GOAL. STOP + summarize after each goal. Never push; never commit to master.
5. Don't include the unrelated `pathly/features/board-differ/*` changes in any commit.
