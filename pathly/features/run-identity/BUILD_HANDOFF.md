# BUILD HANDOFF — run-identity (then board-scoped-storage P2+P3)

_Written 2026-07-22 after state-one-authority shipped (3 goals / 10 tasks, merged to master).
Paste this whole file as the opening prompt of a new Claude Code session._

## TL;DR

Two features, IN ORDER:
1. **run-identity** — issue run identity at spawn; retire the `<feature>` vs `<fsm_feature>`
   guessing (the recurring telemetry bug class). Goal + 6-task DAG already seeded on the board.
2. **board-scoped-storage P2+P3** — move the 9 shared-bucket run folders under their boards and
   retire the buckets. IN-SESSION ONLY (never via a Studio-hosted headless run — folder moves
   under `pathly/` collide with Studio's chokidar watcher handles on Windows → EPERM).

Order matters: run-identity makes identity independent of storage location; THEN moving storage
is safe. Its SPEC's "slug collision" follow-up (board-scoped-storage SPEC.md line ~142) is closed
by run-identity — note that in its retro.

## Setup

- Repo `C:\Users\Yafit\pathly-adapters`. Work on branch `dogfood/run-identity` (branched off
  master after the state-one-authority merge). `git branch --show-current` to confirm. Never
  commit to master, never push without explicit user request.
- FSM server: `curl -s http://127.0.0.1:8765/health`. It must be running the REPO code
  (`pip install -e .` was run / PYTHONPATH=src) — otherwise fragments compose stale.
- Local Python reads stale site-packages unless editable-installed — run every
  python/pytest/pathly-setup/build with `PYTHONPATH=src` to be safe.
- Verification gotchas: never `cmd | tail` for pass/fail (masks exit code) — redirect to a file
  and `echo EXIT=$?`. Studio typecheck: `cd studio && node_modules/.bin/tsc --noEmit -p
  tsconfig.web.json`. Per-goal verification must include `black --check src/ tests/` (two files
  once slipped through unformatted) and the mirror gate `python scripts/check_no_mirror_reads.py`.

## READ FIRST

- `pathly/features/run-identity/SPEC.md` — problem, design step 1 + step 2, non-goals, 4 risks.
  The tasks' context_refs anchor here.
- `src/pathly_orchestrator/CLAUDE.md` — "Telemetry feature key" section (the two-identity split
  being retired) + the db/ layer notes (invocation_projection, run_history).
- Board tasks (exact prompts + Files + Done-when):
  `curl -s "http://127.0.0.1:8765/comms/tasks?feature=run-identity&board=feature&scope=run-identity"`

## Build approach (as agreed)

In-session build (or the user may dispatch the goal via Studio's loop executor — if so, just
supervise). If in-session, replicate the fragment cadence per task:

1. **Claim**: `POST /comms/tasks/claim {"message_id":"<id>","run_id":"insession-<slug>"}`
2. **Ground**: board-context preview (`POST /comms/agent-context/preview` with
   scope=run-identity, board=feature, project_root, task_description, task_id) + `/code/query`
   impact on the files you'll touch (`scope":"(interactive)"`) + read the task's context_refs.
   GROUND BEFORE EDITING — a prior feature shipped a false claim through the whole planning
   chain; the cadence's grounding step is what catches those.
3. **Build**, then **verify the task's Done-when by running it**.
4. **Status**: `POST /comms/post {"feature":"run-identity","scope":"run-identity","board":
   "feature","from":"builder","type":"status","reply_to":"<id>","text":"..."}`
   (fields are `feature` + `from`, NOT `from_agent`).
5. **Complete**: `POST /comms/tasks/complete {"message_id":"<id>","feature":"run-identity"}`.
6. Commit per feature-goal on the branch; STOP + summarize for review before starting
   board-scoped-storage.

## Feature 1 — run-identity (goal `460f8f5b`, executor `loop`)

6 tasks, respect `depends_on` (t1 → {t2, t3} → {t4, t5} → t6):

| # | Slug | id | depends_on |
|---|---|---|---|
| 1 | `board-scope-column` | `5b071261-274a-498b-802e-9a8a57c16bdb` | [] |
| 2 | `completion-report-stamps-board-scope` | `acbdc8e0-c014-4ab7-a1fb-c9325b96ee1d` | [1] |
| 3 | `server-injects-run-id-and-scope` | `4f12a201-23b3-419c-b227-f46a9e909724` | [1] |
| 4 | `run-history-identity-map` | `30ef8b59-2bb8-41c5-865c-6a58275578c7` | [3] |
| 5 | `projection-stamps-board-scope` | `db623fd2-ee78-49d2-abe5-41a6477e7e1f` | [3] |
| 6 | `consumers-pivot-run-id` | `dee9ed97-75df-4ddd-8d26-26a3bae3a05e` | [4, 5] |

The board task text is the authoritative prompt for each (fetch it — Files + Done-when are
inside). Inline summary so this file stands alone if the server is down:

| # | Files (primary) |
|---|---|
| 1 | `src/pathly_orchestrator/db/migrations.py` · `src/pathly_orchestrator/db/queries/fsm_events.py` |
| 2 | `src/pathly_data/core/skills/fragments/completion-report.md` · `src/pathly_data/core/skills/utilities/log-agent-done.md` (**core fragments** — regen + snapshots, see below) |
| 3 | `src/pathly_orchestrator/supervisor/terminal.py` · `src/pathly_orchestrator/runner/events.py` · `supervisor/board_run.py` (verify-only) |
| 4 | `db/migrations.py` · `db/queries/run_history.py` · supervisor write sites (ground) · `src/pathly_orchestrator/CLAUDE.md` |
| 5 | `db/migrations.py` · `db/queries/invocation_projection.py` |
| 6 | `http_server/blueprints/ops/db_api_rollup.py` · `http_server/blueprints/ops/db_api_feature_detail.py` · `src/pathly_orchestrator/CLAUDE.md` |

**Fragment/skill facts for task 2** (learned in state-one-authority G1, same two files):
- `completion-report` is composed into MANY skills; `log-agent-done` is composed by
  `team/retro`. Editing them changed exactly these 7 golden snapshots last time — expect the
  same set again: `tests/snapshots/{development__build, planning__plan, team__build,
  team__design, team__retro, team__review, team__test}.claude.md`.
- `composition.yaml` needs NO change — the fragments are already in the manifest; only their
  CONTENT changes.
- Regen order: edit core files → `PYTHONPATH=src pathly-setup claude --apply --repair` →
  `PYTHONPATH=src python -m build` (both exit 0) → rerun
  `tests/install_skills/test_compose.py`, eyeball each snapshot diff is ONLY the added
  `board_scope` field, write the new compose output back to the snapshot files.
- The `<feature>` / `<fsm_feature>` / `<run_id>` placeholders are substituted by
  `fsm_compose._inject_prompt_vars` (flow runs) and `board_run._inject_board_prompt_vars`
  (board runs; `<run_id>` handled downstream in `_run_stage_via_terminal`) — task 2 only ADDS
  a field that uses an EXISTING placeholder; it must not invent new placeholders.

Non-negotiables baked into the task prompts:
- Migrations idempotent (try/except ALTER TABLE pattern in `db/migrations.py`); legacy NULL
  rows keep their current heuristic fallbacks everywhere — behavior-neutral for old data.
- Stamping is COALESCE-style: fill only when absent, NEVER overwrite an agent-provided value.
- Task 2 edits core fragments → `PYTHONPATH=src pathly-setup claude --apply --repair` +
  `PYTHONPATH=src python -m build` (both exit 0) + regenerate golden compose snapshots
  (`tests/install_skills/test_compose.py` asserts byte-equality) after eyeballing the diff.
  ASCII only in code blocks (Windows cp1252).
- Task 6 is doc-sync: rewrite the "Telemetry feature key" CLAUDE.md section to the new rule —
  identity is ISSUED at spawn (run_id primary, board_scope + slug as columns), never derived
  from storage location — in the SAME commit.
- After adding/moving any test: `PYTHONPATH=src python scripts/gen_test_index.py`.

Commit the goal, STOP + summarize. Get user review before feature 2.

## Feature 2 — board-scoped-storage P2+P3 (IN-SESSION ONLY)

Authoritative: `pathly/features/board-scoped-storage/SPEC.md` (P1 shipped; treat P2+P3 as ONE
unit — its own boxed note explains why). No DAG seeded yet — either seed a small 3-task goal
first (board-honest) or work directly; ask the user which they prefer.

1. **Re-run the inventory first**: `pathly/features/board-scoped-storage/p2_inventory.py` — the
   "9 folders, 0 DB refs" verification is from 2026-07-05 and runs have happened since. If new
   DB refs exist, STOP and report before moving anything.
2. **P2 move**: `git mv` the shared-bucket folders (`pathly/debugs|explorations|fixes/<slug>`)
   under their boards (8 → `pathly/project/<kind>/`, 1 → its feature). Studio must be CLOSED
   (or watchers paused) — open chokidar handles under `pathly/` make folder renames EPERM-fail
   on Windows. Pure move; no re-keying (nesting-aware `_project_root_of` already landed, and
   run-identity has made identity location-independent).
3. **P3 visibility**: add `project` to Studio's `KNOWN_PATHLY_DIRS` (`useProjectFiles.ts`);
   retire `debugs`/`explorations`/`fixes` from the shared-bucket discovery paths (NOTE:
   `cli/_discovery.py` ALREADY walks the nested kinds — verified 2026-07-22 — so this is
   mostly removals + Studio + docs); keep the names in the reserved-name set
   (`storage_paths.py`). Extend the layout-invariant test (reads AND writes land in the same
   place). Doc-sync root + orchestrator CLAUDE.md storage sections in the same commit.
4. **Out of scope**: S2 (`pathly/plans/` DB refs) — a separate DB-only migration; do NOT fold in.
5. Retro note: the SPEC's tracked slug-collision follow-up is closed by run-identity.

Commit, STOP + summarize. Both features done.

## Rules

1. ORDER: run-identity fully, then board-scoped-storage. Within the goal, respect depends_on.
2. Verify every Done-when by running it. Suite green + black + gate + tsc (when studio touched).
3. Living docs sync in the SAME commit as the code they describe.
4. Never push; never commit to master; don't include unrelated working-tree changes
   (board-differ, SkillCompositionKit, user files) in any commit.
5. Keep the board honest: claim/status/complete every task; deviations get flagged in the
   status post, not silently absorbed.
