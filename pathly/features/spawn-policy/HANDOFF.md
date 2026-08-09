# Spawn-Policy — Session Handoff

**Purpose:** let a FRESH Claude Code session (any machine) continue this feature with zero prior
chat context. Read top-to-bottom, then do **Task 1**. Portable state = this file + `SPEC.md`
(the board DB does **not** travel between machines — only git does). **Refreshed 2026-08-09.**

Repo: `pathly-adapters`. Branch: **`feat/unified-control-plane`** (do NOT push to master; commit +
push each piece to this branch — the owner approves that flow). Use the venv python
(`./.venv/bin/python`) — the system python3.14 has no pytest.

---

## Goal
One Settings control plane for EVERY agent spawn: **(1)** which model per agent/role, **(2)** where
logs go — DB-backed, read by BOTH the renderer gate and the Python resolver, applied at the one
spawn door. Purpose: uniform control of the build + **cost + monitoring**.
Read first: [SPEC.md](SPEC.md) (the plan + code-verified wiring audit).

## THE INVARIANT (never break)
The cost/monitor spine (`run_history`, `agent_invocations`, `completion-report`, gate liveness) is
**ALWAYS ON** — never a togglable setting. Only agent BOARD narration (`comms-post` /
`progress-logging` fragments) is configurable. Tests enforce this
(`test_logging_config_never_exposes_the_monitor_spine`).

---

## Already shipped this session (all tested/typechecked, pushed). `git log master..HEAD`

- **Run registry:** `studio/src/renderer/src/store/runRegistryStore.ts` +
  `commsStore.rehydrateActiveRuns` → board/goal/flow RunPills survive a full renderer reload.
- **Editor one-shots survive reload:**
  `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useOneShotReconcile.ts` +
  new `terminal:get-engines` IPC (main + preload + `global.d.ts`) + persisted `mdEditorActions`.
- **Spawn-policy DB config + API:**
  - `src/pathly_orchestrator/db/queries/app_settings.py`: `resolve_agent_model(role)` (layered:
    per-role → global default → engine default; never raises), `set/clear_agent_model`,
    `get_model_policy`, `get_logging_config`, `set_logging_board_enabled`.
  - `src/pathly_orchestrator/http_server/blueprints/comms/settings.py`: GET/POST
    `/comms/model-policy` + `/comms/logging-config`.
- **Resolver (where the model choice TAKES EFFECT):**
  `src/pathly_orchestrator/supervisor/spawn_policy.py::effective_model(agent, adapter, model)` —
  fail-safe; applies a configured model only when there's no explicit model AND the config's adapter
  == the run's adapter (**model-within-company**; company-override is deliberately out of scope).
  Wired at: **board runs** (`supervisor/board_run.py::_default_spawn`), **FSM stages**
  (`supervisor/orchestrator.py::_loop`, right after `_stage_model_for`), **FSM feedback**
  (`supervisor/orchestrator_stage.py::_resolve_stage_supervised`).
- **Summaries are CLI-only:** `studio/src/renderer/src/components/shared/AiTargetSelector/` gained
  `allowLocalModels` (default false) so it lists CLI engines only; `summarizeArtifact.ts` +
  `useResummarize.ts` coerce a stale stored local-model target → `{engine, claude}`. **Chat keeps
  local models** (a separate system: `store/modelStore.ts`).
- **Board posts carry run_id:** `db/queries/comms_messages.py::post_message(run_id=…)` writes the
  (already-existing) `comms_messages.run_id` column; `blueprints/comms/runs.py` posters stamp it.
  The read-model already JOINs on run_id → the RunDetail **Board tab can be exact**.

**Model config takes effect for:** board runs ✅ · FSM stages ✅ · FSM feedback ✅.

---

## NEXT TASKS (in order)

### 1. Settings UI (frontend — the visible payoff; typecheck-only, verify in-app)
In `studio/src/renderer/src/components/Settings/` (mirror `IntelligenceSettings`/`RunsSettings`,
add to `SettingsNav` + `SettingsPanel`), a new section with:
- **Models:** a global default (company + model) + grouped per-agent overrides —
  *Pipeline:* architect·planner·builder·reviewer·tester·scout·designer·director·evaluator;
  *Editor:* split·analyze·diagram·comment·summarize. Companies from `services/cliEngine`
  `ADAPTER_META`. Model = a free-text input (custom-model escape hatch) — or add a GET endpoint
  returning `db/pricing.py::PRICING` models per provider for a dropdown + cost display.
  Wire to GET/POST `/comms/model-policy` via a new hook (mirror `Settings/hooks/useDefaultProgress.ts`
  / `useDefaultSummaryTarget.ts`; use `lib/config::apiFetch`, never bare fetch).
- **Logging:** board on/off toggle + verbosity (reuse `ProgressSelect` + `useDefaultProgress`) +
  a LOCKED "Monitor + Cost — always on" row. Wire to GET/POST `/comms/logging-config`.
- Surface the precedence in the UI: per-run override → per-role → global default → engine default.

### 2. make_board_posters tail (backend)
Thread `run_id` through `goals.py` + `tasks.py` posters (same pattern as `runs.py` — the
`_on_start(_run_id)`/`_on_done(_run_id)` callbacks already receive it); add `run_id` to the
`/comms/post` route + the `comms-post` fragment (agents post it — the fragment already has
`<run_id>` substituted). Optional SOLID dedup: `blueprints/control/_lifecycle.make_board_posters`.

### 3. Editor/summary renderer config (last "takes effect" piece)
Editor one-shots + summaries spawn from the renderer (`services/cliEngine`); have them read
`/comms/model-policy` and apply the configured model before spawning (mirror `effective_model`'s rule).

---

## Verify
```bash
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json    # renderer
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json   # main
PYTHONPATH=src .venv/bin/python -m pytest tests/db/test_spawn_policy.py \
  tests/http_api/test_spawn_policy_routes.py tests/db/test_comms_run_id.py -q
.venv/bin/python scripts/gen_test_index.py    # after adding a test
```
Studio runs under electron-vite dev (HMR live); FSM server on `127.0.0.1:8765`.

## Gotchas
- **Board DB is per-machine** (`~/.pathly/pathly.db`) — the unified-control-plane feature board is
  empty on a fresh machine; the `.md` docs are the portable state.
- **Design intent** (verified in `pathly/features/unified-control-plane/ARCHITECTURE.md`): logs
  already go to the control plane (`run_log` → **Logs** tab); board posts STAY and get
  run_id-correlated (**Board** tab). Do NOT remove the board — it's governance. The board on/off
  toggle is *optional narration control*, not a board removal.
- **Everything is fail-safe:** unconfigured → behaves exactly as before.
- **Doc-sync:** update the matching `CLAUDE.md` / `SPEC.md` in the same commit.

Start by reading [SPEC.md](SPEC.md), then do **Task 1 (Settings UI)**.
