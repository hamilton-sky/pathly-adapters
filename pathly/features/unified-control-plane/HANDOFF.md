# Unified Control Plane — Session Handoff

**Purpose:** let a FRESH Claude Code session pick up this feature and implement one task,
board-driven, with zero prior conversation context. Read this top-to-bottom once; then work
one task at a time.

---

## TL;DR (start here)
1. `git checkout feat/unified-control-plane` (do NOT push without asking; never push master).
2. The **board is the backlog**. The FSM server must be running on `127.0.0.1:8765` (Studio starts it; check `curl -s http://127.0.0.1:8765/health`).
3. Query ready tasks (§3), pick one, read its `text` (a self-contained spec) + the `ARCHITECTURE.md` section it cites.
4. Implement → test → mark done → commit (§4). One task = one commit.

`project_root` is `C:/Users/Yafit/pathly-adapters` everywhere below. Feature slug is `unified-control-plane`.

---

## 1. What this feature is
One Azure-pipeline-style **control plane** over Pathly's 6 spawn facades: start any run kind
from one place, watch every log + board post live, keyed by `run_id`. **MVP = P0 + P1 + P2**
(P3 = next milestone). Design docs in this folder:
- `SPEC.md` — the initiative + the "complete run record" data model.
- `ARCHITECTURE.md` — **the authoritative, file-by-file, code-verified design** (§0–10 = P0, §11 = P1, §12 = P2). Every task cites a section here.
- `DESIGN.md` — the read-only Pipelines pane UX (status badges, tabs, reuse).
- `PO_NOTES.md` / `RESEARCH.md` — scope boundary + SSE/retention findings.

## 2. State (2026-07-24)
Branch `feat/unified-control-plane`, 4 commits (unpushed):
`7b0ef133` P-1 fixes + SPEC · `63500f1f` consultation artifacts · `7d7302e4` **P0(a) done**.

DAG: **3 goals / 15 tasks**, all `executor=loop`, dependency-gated.
```
P0 p0-run-record  (goal 6c224221)  a✅ → {b,c ready now} ; c→d→e ; {b,c,d,e}→f
   a schema+run_log store ✅   b two write seams (708ad4de)   c read-model+overlay (037813ec)
   d GET /runs blueprint       e Studio Pipelines pane        f tests
P1 p1-live-feed   (goal b8d499ac, depends_on P0)  a→{b,c,d}→e
   a SSE _broadcast_run_event + /events/runs   b make_board_posters (dedup 3 closures)+run_id
   c discrete board_context_injected           d live RunDetail   e tests
P2 p2-launcher    (goal 67dd7837, depends_on P1)  a→b→c→d
   a RunSpec+dispatch_run   b POST /runs   c NewRunButton+openers   d tests
```
**Ready right now (independent — can run in parallel):** P0(b) `708ad4de`, P0(c) `037813ec`.

## 3. Get a ready task
```bash
# goal rollup (ready/done counts live under tasks:{})
curl -s "http://127.0.0.1:8765/comms/goals?feature=unified-control-plane&project_root=C:/Users/Yafit/pathly-adapters"
# a goal's tasks (GET /comms/tasks needs BOTH feature and project_root, not just goal_id)
curl -s "http://127.0.0.1:8765/comms/tasks?goal_id=6c224221-0e91-4065-a1d9-4962af52b4c8&feature=unified-control-plane&project_root=C:/Users/Yafit/pathly-adapters"
```
Pick a task whose `status` is `ready`. Its `id` is the message_id; its `text` is your spec.

## 4. Implement one task
```bash
# 4a. claim it
curl -s -X POST http://127.0.0.1:8765/comms/tasks/claim -H "Content-Type: application/json" \
  -d '{"message_id":"<id>","feature":"unified-control-plane","project_root":"C:/Users/Yafit/pathly-adapters","run_id":"<any-unique>"}'
```
4b. Read the `ARCHITECTURE.md` sections the task text cites — they contain exact code + insertion points. **Read each target file before editing** (verify the seam is where the doc says).

4c. Verify blast radius with code-intel (`target` MUST be a file path):
```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" \
  -d '{"op":"impact","target":"src/pathly_orchestrator/supervisor/terminal.py","role":"builder","project_root":"C:/Users/Yafit/pathly-adapters","scope":"(interactive)"}'
```
4d. Implement under the layer rules (`db → runner → supervisor → http_server`, no upward imports; supervisor/db imports lazy inside Flask handlers; **≤400 lines/file**; React ≤150 lines + folder-per-component; no inline styles).

4e. Test — **never `cmd | tail` for pass/fail** (masks the exit code); redirect + `echo $?`:
```bash
PYTHONPATH=src python -m pytest tests/db/ -q ; echo "EXIT=$?"     # backend
python scripts/gen_test_index.py                                  # after adding/moving a test
node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json        # renderer typecheck (studio tasks)
```
4f. Close the loop + commit ONLY this task's files:
```bash
curl -s -X POST http://127.0.0.1:8765/comms/tasks/complete -H "Content-Type: application/json" \
  -d '{"message_id":"<id>","feature":"unified-control-plane","project_root":"C:/Users/Yafit/pathly-adapters"}'
git add <the specific files you changed>          # NOT `git add -A`
git commit -m "feat(unified-control-plane): P0(x) — <what>"
# do NOT push; do NOT stage pathly/features/board-differ/BOARD_EVAL.md (pre-existing, unrelated)
```

## 5. Optional — run a task as a fragment-composed agent (the dogfood way)
Instead of implementing directly, compose the real Pathly build prompt and hand it to an agent:
```bash
curl -s -X POST http://127.0.0.1:8765/skills/compose -H "Content-Type: application/json" \
  -d '{"skill":"development/build","project_root":"C:/Users/Yafit/pathly-adapters","feature":"unified-control-plane","adapter":"claude"}'
```
Returns the prompt with `build-discipline` + `code-query` + `completion-report` + `progress-logging` fragments (board connection + code ability). Feed it to a Bash-capable agent scoped to the one task.

## 6. Gotchas (learned this session)
- `/comms/tasks` needs `feature` + `project_root`; goal rollup counts are under `tasks:{total,pending,ready,done}`.
- Goal create = `POST /comms/post {type:"goal", executor, ...}` (message_id IS the goal_id); task = `POST /comms/post {type:"task", goal_id, depends_on:[msg_ids], stage:"BUILDING"}`.
- Pyright `reportMissingImports` on a `src/pathly_orchestrator...` module is a **path artifact** (Pyright doesn't know `src/` is on the path) — if `PYTHONPATH=src` tests pass, it's fine.
- `tests/db/test_run_log.py` has an unused `tmp_path` fixture param (harmless; clean up if you touch it).
- P-1 left `#5 halt-vs-warn` (nano/lite) open and the 400-line CI gate needs a grandfather allowlist (18 files already over) before it can be enforced.
- The DB is the single runtime authority; `BOARD.json`/`EVENTS.jsonl` are gitignored exports — don't commit them.

## 7. Recommended order
P0: `a✅ → (b ∥ c) → d → e → f`, then P1 `a → (b,c,d) → e`, then P2 `a → b → c → d`.
Two agents can take P0(b) and P0(c) at once (independent). Everything else is gated by `depends_on`.
