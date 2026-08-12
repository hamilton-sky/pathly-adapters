# AUDIT — mirror-file reads/writes (state-one-authority)

_Scout audit (2026-07-22), **verified** by the main session — the two load-bearing claims
were re-checked against code. Advisory: confirm any single line before editing._

## Runtime reads of disk mirrors — the real blast radius

### Server (Python) — DB-first, disk-FALLBACK (resilience; keep, but allow-list explicitly)
- `fsm/engine_actions.py:410-424` — scope_gate `build_baseline`: reads DB (`read_state`) **first**,
  STATE.json only if the DB returns nothing. ✅ pattern-correct (DB-first).
- `fsm/engine_recover.py:27-38` — FSM recovery: STATE.json fallback when no DB `state_doc`.
- `fsm/engine_transitions.py:272` — feedback routing reads `retry_count_by_key` from STATE.json.
→ All three are DB-first fallbacks. The Issue #4 CI gate should **allow guarded fallback reads**
  (explicitly commented) and **forbid unconditional** runtime disk-mirror reads.

### Studio (TypeScript) — reads the disk mirror DIRECTLY, NO DB fallback (the true violations)
- STATE.json: `store/commsApi.ts:1058` (feature-card stage badge), `Monitor/hooks/useMonitorSession.ts:59,114`
  (active-flow detection on startup), `HomeScreen/hooks/useProjectPlans.ts:23` (feature list),
  `PlanBoard/index.tsx:148` (stage).
- EVENTS.jsonl: `store/commsApi.ts:1093` `fetchLastSummary` (feature-card "last activity" — scans for
  the last `AGENT_DONE.summary`).
→ Studio treats the disk file as the source of truth. **This is the hardest part of Issue #4** and the
  main runtime mirror-read to remove. NOTE: a `/db/features` DB read-API already exists (telemetry) —
  verify whether it can serve `state` + `last_summary`, and migrate Studio onto it rather than
  inventing a new endpoint.

## Writers
- STATE.json: `eventlog._write_state_db` (DB→disk export ✅); `cli/back.py:84` (human CLI).
- **`fsm/engine_actions.py:468-478` `write_state` (disk-only, NO DB): TEST-ONLY** — re-exported via
  `fsm/__init__.py` + `engine.py` but called only by `tests/fsm_flows/test_fsm.py`. **NOT a live
  production bug** (the scout over-stated "clear bug"); it is a latent trap + cleanup candidate
  (delete, or make it delegate to `eventlog.write_state`).
- BOARD.json: `board_mirror.py` (DB→disk export, debounced, change-guarded ✅) — **the model to copy.**
- EVENTS.jsonl: agent-direct `open("a")` append (`completion-report` / `log-agent-done` fragments);
  `cli/back.py:93` (CLI). **No DB→disk exporter.**
- ARTIFACTS.jsonl: agent-direct append (`artifact-register`); read disk→DB by `artifact_reconcile.py`.
  **No DB→disk exporter.**

## Design questions this surfaces (for the architect)
1. **CI gate** — allow guarded DB-first-fallback reads (commented) but fail on unconditional runtime
   disk-mirror reads. Detect via grep-heuristic + an allow-list file? (Same shape as the dash-safety
   mirror test.)
2. **Studio DB-first migration** — move the 5 disk-read sites onto a DB read-API (`/db/features`
   + maybe one new field). A real chunk of the work; it's what actually removes the runtime mirror reads.
3. **EVENTS.jsonl / ARTIFACTS.jsonl** — make them pure DB→disk exports (mirror `fsm_events` /
   `comms_artifacts`) and retire the agent-side dual-write? Or **drop them** — once Studio's
   `fetchLastSummary` reads the DB, EVENTS.jsonl has no runtime consumer left.
4. **The test-only disk-only `write_state`** — delete or delegate.
