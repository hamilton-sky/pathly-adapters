# Unified Control Plane — Session Handoff

**Purpose:** let a FRESH Claude Code session (any machine) pick up this feature with zero prior
chat context. Read this top-to-bottom once, then continue. It is the portable version of the
board + the design conversation — because the board DB and per-session memory do **not** travel
between machines (only git does). Refreshed **2026-07-31**.

---

## TL;DR (start here)
1. `git checkout feat/unified-control-plane` (now on origin). Do NOT push master; ask before pushing.
2. **P0 BACKEND IS COMPLETE + PUSHED.** The next task is **P0(e)** — the frontend. Its design was
   converged in the 2026-07-31 session; read **§E** below (it supersedes the standalone-pane sketch
   in `DESIGN.md §1/§6` where they conflict).
3. The board (task DAG) lives in a per-machine DB — on a new machine it's empty. Use the
   **§Board snapshot** here as the backlog. If the FSM server is up (`curl -s http://127.0.0.1:8765/health`),
   the live board mirrors it; if not, this doc is authoritative.
4. Implement → typecheck/test → commit. One task = one commit.

`project_root` = `C:/Users/Yafit/pathly-adapters` (Windows) — **swap for the local path on another
machine**. Feature slug = `unified-control-plane`.

---

## 1. What this feature is
One Azure-pipeline-style **control plane** over Pathly's 6 spawn facades: start any run kind from
one place, watch every log + board post live, **all keyed by `run_id`**. MVP = **P0 + P1 + P2**
(P3 later). `run_id` is the spine: a spawn *mints* one; observability *reads* everything by it
(run_history=status, agent_invocations=cost/tokens, run_log=prompt+stdout, comms_messages=board
posts); control *targets* one. Design docs in this folder:
- `SPEC.md` — initiative + the "complete run record" data model.
- `ARCHITECTURE.md` — **authoritative, code-verified, file-by-file design** (§0–10=P0, §11=P1, §12=P2).
- `DESIGN.md` — the pane UX. **NOTE:** its §1/§6 describe a *standalone* pane; §E below revises that
  to a *shared page wired into Monitor* — follow §E where they differ. The tab/badge/state specs in
  DESIGN.md §2–§5 still hold.
- `PO_NOTES.md` / `RESEARCH.md` — scope boundary + SSE/retention findings.

## 2. State (2026-07-31)
Branch `feat/unified-control-plane` — **pushed to origin** (github.com/hamilton-sky/pathly-adapters).
7 commits. **P0 backend done and tested; frontend (e) is next.**

| Commit | What |
|---|---|
| `7b0ef133` | P-1 fixes (silent-failure guards) + SPEC |
| `63500f1f` | consultation artifacts (PO/arch/research/design) |
| `7d7302e4` | **P0(a)** run_log schema + store |
| `0b3276d0` | (this handoff, original) |
| `2d89f217` | **P0(c)** read-model (`run_history_read.py`) + overlay (`dispatch.py`) — tests/db 63 |
| `80c86311` | **P0(d)** `/control` blueprint GET /runs + /runs/<id> — tests/http_api 72 |
| `c0d1857b` | **P0(b)** two best-effort run_log write seams + AC-6 test — tests/runner_supervisor 137 |

**Data path is end-to-end + green:** spawn writes prompt (P0b) → result writes stdout (P0b) →
read-model lists/details (P0c) → `GET /runs` serves it (P0d). 0 regressions.

**The backend I shipped (reference for the frontend):**
- `src/pathly_orchestrator/db/queries/run_history_read.py` — `_classify_kind`, `list_runs`,
  `get_run_detail`. Payload of `get_run_detail`: `{run, stages[], logs[], board[], artifacts[], cost}`
  (shapes in ARCHITECTURE §4.2).
- `src/pathly_orchestrator/supervisor/dispatch.py` — `overlay_live_status` (upgrades a persisted
  'running' row to live registry status; attaches per-kind `capabilities`).
- `src/pathly_orchestrator/http_server/blueprints/control/runs_read.py` — `GET /runs?project_root=…`
  (list) + `GET /runs/<run_id>` (detail 200 / 404). Registered in `app.py`.
- run_log write seams: `supervisor/terminal.py` (spawn: prompt) + `blueprints/runner/api_lifecycle.py`
  (result: stdout). `board_context_injected` is **NULL in P0** (embedded in `prompt_sent`) → discrete in P1.

## Board snapshot (the DAG — this is your backlog on a fresh machine)
3 goals / 15 tasks, all `executor=loop`, dependency-gated. `feature=unified-control-plane`.

```
P0  goal 6c224221-0e91-4065-a1d9-4962af52b4c8  (p0-run-record)   4/6 done
  a db3afcbe  schema + run_log store ............................. DONE  7d7302e4
  b 708ad4de  two best-effort write seams ......................... DONE  c0d1857b
  c 037813ec  read-model + dispatch overlay ....................... DONE  2d89f217
  d cf747291  /control blueprint (GET /runs, /runs/<id>) .......... DONE  80c86311
  e 23d8a58c  Studio frontend  → see §E ........................... NEXT  (claimed, not built)
  f 3066d7c9  P0 test suite (depends b,c,d,e) ..................... PENDING
P1  goal b8d499ac-92ce-4d48-8b52-a7f9232ac33d  (p1-live-feed)     0/5   a→{b,c,d}→e
  a SSE _broadcast_run_event + GET /events/runs   b make_board_posters (dedup 3 closures)+run_id
  c discrete board_context_injected (§11.4)       d live RunDetail   e tests
P2  goal 67dd7837-8315-46ad-a6fa-79422427df9f  (p2-launcher)      0/4   a→b→c→d
  a RunSpec + dispatch_run   b POST /runs   c NewRunButton + thin openers   d tests
```
(Task `id` = message_id for claim/complete. On a fresh-DB machine these ids won't exist yet — the
work is fully specified by ARCHITECTURE + §E, so you can implement without re-seeding the board;
re-seed only if you want the live board UI. Goal/task create recipe in §Gotchas.)

---

## §E — P0(e) frontend design (CONVERGED 2026-07-31 — the important part)

**Decision: do NOT build a standalone pane. Build ONE shared `RunDetailPage`, reachable from
multiple entrances, keyed by `run_id`.** Rationale: Studio's existing **Monitor** panel (nav row
labeled "Pipeline", panel key `monitor`, component `Monitor`) is *already* a run list — it shows
finished runs from `/db/recent` as cards with kind badges + cost + a shallow "Details" modal. A
second list would duplicate it. The real gaps are (1) **depth** — the modal is shallow *and wrong*
for finished runs (header says `LIVE OUTPUT`, tokens/cost blank, because it reads live tab state
that empties when the engine exits), and (2) **grain** — Monitor shows one card PER SPAWN (a 6-stage
flow = 6 cards; e.g. `goal-…-6d5f5a23` appears 5×). Our `/runs` folds to one row per top-level run.

Mirror DB Explorer's **already-shipped** pattern (`studio/src/renderer/src/components/DBExplorerRedesign/`):
`FeatureCard → FeaturePreview (popover, takes onOpenDetail) → FeatureDetailPage (full page, onBack)`.
`DBExplorerRedesign.tsx:62` does `if (detail) return <FeatureDetailPage feature={detail} onBack={…}/>`
— the page swaps the panel body while the app shell stays. `FeatureDetailPage.tsx` doc even says it
"replaces the old FeatureModal" — we're finishing that same migration for runs.

### Build order
1. **`RunDetailPage`** (standalone shared component; NOT nested under Monitor/Pipelines). Mirror
   `FeatureDetailPage.tsx`'s shell exactly: `← back` · header (kind·feature·adapter·status) ·
   big-stats (cost·tokens·stages·duration) · **tab bar** · body. Tabs = **Stages · Logs · Board ·
   Cost**. Data via `useRunDetail(run_id)` → `GET /runs/<id>`. Each entrance holds its own
   `detailRunId` + back-target and does the `if (detailRunId) return <RunDetailPage …/>` swap.
   - Stages: local stage rows (see reuse note) — completed/failed/running/pending, click → Logs.
   - Logs: stage rail + collapsible `prompt_sent` (with the "may contain paths/tokens" hint) +
     stdout well chip "PTY tail — may be truncated" + a `board_context` note ("embedded in the
     prompt above" in P0; becomes discrete in P1). Empty stdout → "No stdout captured for this stage."
   - Board: correlated posts (run_id-when-present, else time-window). **Empty → "No board posts
     correlated to this run." (AC-3)**. Artifacts = `{title·type·path}` only, NO hydrate (AC-4).
   - Cost: `$cost · k tok · N agents` readout + per-stage table (makes the parity contract legible).
2. **Entrance #1 (do first):** Monitor's card "Details" modal (`Monitor/EngineBoard/EngineDetailModal`).
   **ESCALATE it, don't delete** — keep it as a live-glance preview (useful for a *running* engine)
   and add **`Open run →`** beside `Open terminal` → opens `RunDetailPage`. Fix the finished-run
   wrongness (label + blanks) by reading `/runs/<id>`. **Step 0: confirm Monitor cards carry
   `run_id`** (they should — run-identity stamps `RunningEngine.runId` + `/db/recent` rows). A
   gate-queued card has none → `Open run →` simply absent (correct). Two grains: terminal = the PTY,
   run = the record.
3. **Entrance #2 + per-run grain:** the folded run list (5 cards → 1 row — only `/runs` can do this;
   biggest legibility win). **HOME UNDECIDED — decide when building it:** its own "Pipelines"
   section vs a "by run" toggle inside Monitor. Both open the same `RunDetailPage`.
4. **Relabel** nav "Pipeline" → "Monitor" (`sidebar/shell/BottomNav.tsx` line ~51 label +
   `IconStrip.tsx` tooltip/aria; panel key stays `monitor`; the panel header already says "Monitor").

### Reuse map (verified this session — reuse, don't reinvent)
- **Fetch:** `import { apiFetch } from '<rel>/lib/config'` (base `http://127.0.0.1:8765`, injects
  `X-Pathly-Secret` — never bare `fetch`). project_root: `useStore((s) => s.projectPath)`. Poll
  pattern (mirror `Monitor/hooks/useRecentEngines.ts`): `let cancelled=false` +
  `window.setInterval(load, 8000)` + cleanup; no AbortController.
- **Reuse as-is:** `SegmentedControl` (`Monitor/ConfigurePhaseModal/components/SegmentedControl`) for
  the tab bar; `StagePill` + `AdapterBadge` + `EngineAdapter` type (barrel `Monitor/EngineBoard`);
  `<Timestamp>` (`components/Timestamp`) + `utils/timestamp` (`formatRelative`/`formatClock`).
- **BUILD LOCAL (do NOT extend Monitor's `EngineStatus`/`EngineCategory` unions — that violates AC-7
  "don't touch Monitor"):** `KindBadge` (flow/single/loop/decompose — mirror the `CategoryBadge`
  recipe + a `decompose` variant) and `StatusBadge` (6 statuses queued/running/succeeded/failed/
  aborted/canceled — mirror the tinted-pill recipe + reuse `StatusDot` shape). `adapterFromProvider`
  is module-private in `useRecentEngines.ts` → copy it (maps gpt*/codex→Codex, gemini/agy→Gemini,
  else Claude; return null for flow-name adapters so no badge shows).
- **`deriveFlowSteps`/`StepRow` do NOT fit** — the detail payload has no FSM `events`, and `StepStatus`
  can't express a *failed* stage without editing Monitor. Render stages as **local rows** (StagePill +
  StatusBadge + adapter + cost).
- **Conventions:** relative imports (the `@renderer/*` alias exists but is unused); `import type`;
  `export function … : JSX.Element`; `import styles from './X.module.css'`; `type="button"`; data-*
  variants; tokens-only (no inline styles except CSS custom props carrying data); ≤150 lines +
  folder-per-component; responsive to ≤200px. Renderer typecheck:
  `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (from repo root; redirect + `echo $?`).

### Load-bearing facts
- `run_history` has **NO row for a queued-but-not-spawned engine** (identity is issued *at spawn*).
  So `/runs` cannot show the gate queue — Monitor's live board is the ONLY source for queued/live.
  That's *why* Monitor stays (live + queue) and the run page/list is a separate concern.
- Per-run cost for a flow = SUM over the stage time-window (approximate under back-to-back same-board
  runs; exact in P1). single/loop cost = exact `WHERE run_id=?`. Parity with Monitor RECENT cards.

---

## Follow-ons after P0(e)
- **P0(f)** — the P0 test suite (each subtask already shipped its own test; f aggregates + adds
  `test_run_log_migration`, `test_runs_read` [exists], and any integration). ARCHITECTURE §8.1.
- **B — board-context block (P1 §11.4):** make `board_context_injected` discrete. Mostly BACKEND —
  thread `board_block` out of `fsm_compose.build_prompt` (a `capture` hook) → `next_action`
  (`agent_hint.board_context`) → supervisor → the spawn write fills the column (today it writes NULL).
  Frontend is one render in the Logs tab's reserved slot. Touches the hot compose path.
- **C — launcher (P2 §12):** `[+ New Run]` → `POST /runs` (RunSpec: flow|board|goal|decompose|task|
  feature|project) → `dispatch_run` routes to existing `start_*`. Reuses the `FlowGatePreview` /
  `SendPreviewModal` gates for prompt config. Makes the surface write-capable.

## Mechanics — implement one task (when the FSM server is up)
```bash
curl -s "http://127.0.0.1:8765/comms/goals?feature=unified-control-plane&project_root=<ROOT>"   # rollup
curl -s -X POST http://127.0.0.1:8765/comms/tasks/claim   -H 'Content-Type: application/json' \
  -d '{"message_id":"<id>","feature":"unified-control-plane","project_root":"<ROOT>","run_id":"<unique>"}'
# … implement, read each target file before editing, verify against ARCHITECTURE + §E …
curl -s -X POST http://127.0.0.1:8765/comms/tasks/complete -H 'Content-Type: application/json' \
  -d '{"message_id":"<id>","feature":"unified-control-plane","project_root":"<ROOT>"}'
git add <only this task's files>          # NOT git add -A
git commit -m "feat(unified-control-plane): P0(x) — <what>"
```
Layer rules: `db → runner → supervisor → http_server` (no upward imports; supervisor/db imports lazy
inside Flask handlers; ≤400 lines/file). Doc-sync: update the matching CLAUDE.md in the same commit.

## Gotchas
- **Restart to go live.** The running FSM server + Studio predate this code, so the live
  `~/.pathly/pathly.db` lacks `run_log`, `GET /runs` 404s, and the write seams don't fire until the
  FSM server (and Studio) restart from repo code. On a NEW machine this is automatic on first launch.
- **FSM server may be stopped** (Studio starts it; it force-restarts port 8765 on app launch). If
  `curl /health` is empty, launch Studio or start the server; the board comes from the DB either way.
- **DB/board is per-machine, not in git.** This snapshot + the design docs ARE the portable state.
  `BOARD.json` / `EVENTS.jsonl` in this folder are gitignored DB exports — **do not commit them**.
  Also never stage `pathly/features/board-differ/artifacts/BOARD_EVAL.md` (pre-existing, unrelated).
- **Read-model learnings (P0c):** window-join upper bounds bind a Python ISO `now`, NOT SQL
  `datetime('now')` (space-format sorts before 'T' ISO → drops rows). `_classify_kind` regex
  false-positives an all-numeric-tail uuid as 'stage' — rare, accepted per ARCH §1.1.
- New `db/queries` modules are NOT added to `__init__.py` (direct-path imports). Pyright
  `reportMissingImports` on `src/pathly_orchestrator…` is a path artifact — if `PYTHONPATH=src` tests
  pass, it's fine. Never `cmd | tail` for pass/fail (masks exit code) — redirect + `echo $?`.
- P-1 left `#5 halt-vs-warn` (nano/lite) open; the 400-line CI gate needs a grandfather allowlist.

## Recommended order
`P0(e) → P0(f)`, then P1 `a → (b,c,d) → e`, then P2 `a → b → c → d`. Within P0(e): RunDetailPage →
Monitor "Open run →" (entrance #1) → per-run list (entrance #2, decide its home then).
