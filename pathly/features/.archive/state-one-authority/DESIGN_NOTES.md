# DESIGN NOTES — the four JSON files: today vs. after consolidation

Companion to `SPEC.md` / `ARCHITECTURE_PROPOSAL.md`. Explains what each per-feature disk
file provides today, which subsystem it serves, and how this feature collapses them to
"one authority, everything else a one-way projection."

## 1. What each disk file gives you today (and which subsystem)

There is **no `RUNNER.json`** — the runner/supervisor state lives in the DB (`runner_state`)
+ in-memory, never on disk. The four disk files are:

| File | What it gives you | Subsystem ("place") | DB authority | Written by | Direction | Can drift? |
|---|---|---|---|---|---|---|
| **STATE.json** | current FSM stage (`BUILDING`…), retry counts, `build_baseline` | FSM / orchestrator (control) | `fsm_state` | `eventlog._write_state_db` | DB→disk **export** | no |
| **EVENTS.jsonl** | event log: `STATE_TRANSITION`, `AGENT_DONE` (cost/tokens/summary), `GATE_FAILED`, `RETRY` | telemetry / event log | `fsm_events` | the **agent** (open-append) | agent→disk | **YES** |
| **ARTIFACTS.jsonl** | ledger of files a run produced (role, path, summary) | artifact registration (reconcile) | `comms_artifacts` | the **agent** (open-append) | agent→disk→DB | **YES** |
| **BOARD.json** | full board snapshot — cards + artifact metadata | comms board (knowledge substrate) | `comms_messages` + `comms_artifacts` | `board_mirror.py` | DB→disk **export** | no |
| *(runner state)* | active run: status, current stage, session id | runner / supervisor | `runner_state` + memory | supervisor | DB only, **no file** | n/a |

Problem in one line: **`STATE` and `BOARD` are real DB exports that can't drift; `EVENTS` and
`ARTIFACTS` are written by the agent on a *different* path than the DB, so they silently diverge.**

## 2. How the consolidation changes it

The rule enforced everywhere: **the DB is the one runtime authority; every disk file is a
one-way EXPORT (or a read-once SEED); nothing reads a mirror to make a decision.**

- **STATE.json** — write path unchanged (already a DB export); but **Studio stops reading it**.
- **EVENTS.jsonl** — stops being agent-written; becomes a DB→disk **export** via a new
  `event_mirror.py` (copy of `board_mirror.py`). Can no longer drift, and finally captures the
  server-side events (transitions, reconciled billing) the agent-written version missed.
- **ARTIFACTS.jsonl** — **deleted**; its metadata already lives in `BOARD.json` + the live
  `/comms/post` the agent already sends. `artifact_reconcile` keeps only its `feedback/*.md` job.
- **BOARD.json** — unchanged (the model everything else copies).
- **Studio** — the 5–6 sites reading `STATE.json`/`EVENTS.jsonl` off disk now call
  **`GET /db/features`** (state · last_summary · flow). This removes the "read a mirror to decide."
- **New CI gate** — `check_no_mirror_reads.py` fails the build on any future runtime mirror read.

## 3. Diagram — TODAY (one authority, but 3 write paths; 2 files drift)

```
                 SQLite  ~/.pathly/pathly.db   <--- the real runtime authority
        fsm_state   fsm_events   comms_messages/artifacts   runner_state
            |           ^                |                      |
   DB-first |      agent POSTs      DB-first |            (in-memory + DB,
   then file|      /runner/event    then file|             NO disk file)
            v           :                     v
     +----------+ +-----+------+ +---------------+ +-----------+
     |STATE.json| |EVENTS.jsonl| |ARTIFACTS.jsonl| | BOARD.json|
     | EXPORT ok| |agent writes| | agent writes  | | EXPORT ok |
     |          | | the file ! | |  the file  !  | |           |
     +----+-----+ +-----+------+ +-------+-------+ +-----+-----+
          |             |                | disk->DB        |
       read by:      read by:        artifact_reconcile  read by:
       * scope gate  * Studio          (import buffer)   * hydration
       * FSM recover   "last activity"!                    only
       * Studio cards!* pathly-back
       * pathly-back

   ! = writes the FILE on a different path than the DB  -> the two can diverge
   ! = Studio decides UI state by reading the FILE, not the DB
```

## 4. Diagram — AFTER (DB is the one hub; every file is a one-way export; reads hit the DB)

```
                 SQLite  ~/.pathly/pathly.db   <--- single runtime authority
        fsm_state   fsm_events   comms_messages/artifacts   runner_state
            |           |                |
   EXPORT   | EXPORT    |       EXPORT    |        (all one-directional: DB --> disk)
  (eventlog)|(NEW event_mirror.py) (board_mirror)
            v           v                v
     +----------+ +----------+    +-----------+          ARTIFACTS.jsonl
     |STATE.json| |EVENTS.jsonl|  | BOARD.json|          ---  GONE  ---
     |  EXPORT  | |  EXPORT   |   |  EXPORT   |       (folds into BOARD.json
     +----------+ +----------+    +-----------+        + live /comms/post)
       git-trackable snapshots -- NOBODY reads them to make a decision

   ALL runtime reads now hit the DB:
     FSM    --> read_state / read_events        (disk only as allow-listed fallback)
     Studio --> GET /db/features  ->  state . last_summary . flow   (no file reads)
     CLI    --> eventlog.read_*   (DB)

   +---------------------------------------------------------------+
   |  CI GATE  scripts/check_no_mirror_reads.py                     |
   |  build fails on any NEW runtime read of a mirror file          |
   |  (allow-list = the handful of sanctioned DB-first fallbacks)   |
   +---------------------------------------------------------------+
```

**The shift in one line:** today the DB and the disk files are written by *different actors on
different paths* (so they drift); after, the DB is the sole writer of truth and every file is a
downstream photocopy nobody reads back — "one authority, everything else a projection."
