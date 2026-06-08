# EDGE_CASES.md — agent-done-early-advance

## EC-1 — PTY exits before AGENT_DONE is written

**Scenario:** The agent crashes or is killed before writing AGENT_DONE. The PTY exits
and the billing POST arrives first.

**Behaviour:**
- `result_evt` fires before `_agent_done_events[run_id]`.
- The race in `_run_stage_via_terminal` takes the slow path (existing code).
- The watcher thread is cancelled by setting its stop_evt.
- `_agent_done_events[run_id]` and `_agent_done_stop_events[run_id]` are cleaned up
  by the slow-path cleanup block.
- No early advance occurs. No `STAGE_RECONCILIATION_FAILURE` is written.

**Acceptance:** Existing `test_supervisor.py` tests cover this path (S-5, Test 3).

---

## EC-2 — Double-fire guard (AGENT_DONE written more than once)

**Scenario:** An agent writes multiple `AGENT_DONE` lines to EVENTS.jsonl (e.g., due
to a retry loop or a bug).

**Behaviour:**
- `tail_agent_done` yields the first AGENT_DONE and the watcher sets
  `_agent_done_events[run_id]`.
- `threading.Event.set()` is idempotent — a second call is a no-op.
- The watcher breaks after the first yield (returns immediately).
- FSM advance is called exactly once.

**Acceptance:** The `break` after first yield in the watcher method is the guard.
No test needed beyond asserting "FSM advance called once" in Test 1.

---

## EC-3 — No AGENT_DONE ever written (timeout)

**Scenario:** The agent runs for the full 1800-second timeout without writing AGENT_DONE,
and never exits the PTY either.

**Behaviour:**
- Both `_agent_done_events[run_id]` and `result_evt` are still unset after 1800 s.
- The existing timeout handling in `_run_stage_via_terminal` fires.
- The watcher thread's `stop_evt` is set during timeout cleanup.
- `tail_agent_done` returns cleanly when `stop_evt` is set and no new bytes remain.
- Existing timeout error path runs unchanged.

**Acceptance:** Covered by existing timeout tests (not new work). Builder must confirm
the watcher cleanup is called in the timeout branch.

---

## EC-4 — exit_code != 0 after early advance

**Scenario:** The watcher fires and the FSM advances early. Later the PTY exits with
a non-zero exit code (e.g., the agent encountered a Python exception after writing
AGENT_DONE).

**Behaviour:**
- The PTY still POSTs to `/runner/terminal/result` with the non-zero exit_code.
- The reconciliation window receives the billing data and records `cost_usd` and
  `session_id`.
- The non-zero `exit_code` is written to EVENTS.jsonl as part of the billing update.
- The FSM is NOT rolled back — early advance is final.
- Studio shows the stage as complete. The non-zero exit is surfaced as a warning in
  the stage metadata, not as a failure.

**Policy decision:** Early advance is optimistic. The product assumption is that
AGENT_DONE is written only after the agent has verified its own output. A non-zero
PTY exit after AGENT_DONE is treated as a teardown issue, not a work failure.

**Acceptance:** Builder must record `exit_code` from billing POST in the billing
update event. Reviewer checks that no rollback logic was introduced.

---

## EC-5 — Windows file polling

**Scenario:** On Windows, file locking and buffering may delay visibility of appended
bytes to a polling reader.

**Behaviour:**
- `tail_agent_done` opens the file in binary mode (`rb`), which avoids CRLF
  translation issues.
- The generator seeks to the known offset, reads all available bytes, and processes
  only complete lines (lines ending in `\n`).
- Partial lines (file written mid-line) are buffered until the next poll completes
  the line.
- Windows does not support `inotify` — the polling loop with `poll_interval=0.1` is
  the only mechanism. This is acceptable given the 0.1-second latency target.

**Acceptance:**
- `test_tail_agent_done_yields_and_stops` passes on Windows (the CI environment).
- Partial-line writes do not cause JSON parse errors — the generator silently skips
  lines that fail JSON parsing.
- Builder adds a `try/except json.JSONDecodeError: continue` inside the generator.

---

## EC-6 — Feature flag toggled mid-run

**Scenario:** An operator changes `PATHLY_RUNNER_EARLY_ADVANCE` from `0` to `1` (or
vice versa) while a run is in progress.

**Behaviour:**
- `feature_flags.early_advance` reads the env var on each call (no caching).
- If a stage started with the flag off, no watcher thread was started; that stage
  uses the slow path through completion.
- If the flag is toggled on, the next stage (not the current one) picks it up.
- There is no mid-stage switch — the decision is made once at the start of
  `_run_stage_via_terminal`.

**Acceptance:** No special code needed. The property re-reads `os.environ` on each
access (verify this is the existing `_bool()` behaviour). Builder confirms with a
code comment.

---

## EC-7 — Interactive mode: Studio does not acknowledge TERMINAL_KILL

**Scenario:** The supervisor emits `TERMINAL_KILL` SSE but Studio is not connected or
the SSE client drops the event. The PTY keeps running.

**Behaviour:**
- The supervisor has already advanced the FSM and cleaned up all dicts for `run_id`.
- The PTY continues running until it naturally exits or the user closes the window.
- No billing POST will arrive (there is no reconciliation window in interactive mode).
- Cost data is taken from the AGENT_DONE event already in EVENTS.jsonl.
- The orphaned PTY causes no correctness problem — it simply exits on its own.

**Policy decision:** `TERMINAL_KILL` is best-effort. Interactive mode accepts the
trade-off that a dropped kill signal leaves an orphaned-but-harmless terminal window.

**Acceptance:** No code guard required. Builder adds a log line after `_emit_sse("TERMINAL_KILL", ...)`: `"[interactive] TERMINAL_KILL emitted for tab {tab_id}; PTY teardown is Studio's responsibility"`.

---

## EC-8 — Interactive mode enabled without early advance

**Scenario:** `PATHLY_RUNNER_INTERACTIVE=1` is set but `PATHLY_RUNNER_EARLY_ADVANCE` is unset or `0`.

**Behaviour:**
- On the first run attempt, the supervisor detects the invalid combination.
- Emits `RUNNER_WARNING` SSE with message: `"PATHLY_RUNNER_INTERACTIVE=1 requires PATHLY_RUNNER_EARLY_ADVANCE=1"`.
- Raises `RuntimeError` with the same message; the run is aborted.
- Studio surfaces the warning as a toast notification.

**Acceptance:** `test_interactive_mode_strips_headless_flags` (Test 2 in Conv 4) implicitly
verifies the guard runs without raising. A separate test verifies the guard raises when
early_advance is False.

---

## EC-9 — Pipeline History: EVENTS.jsonl has thousands of AGENT_DONE entries

**Scenario:** A long-running feature has accumulated 50+ AGENT_DONE entries across
retries and re-runs.

**Behaviour:**
- `build_pipeline_history_block` reads the full file but keeps at most `max_items=10` entries.
- The oldest entries are dropped; the 10 most recent are included.
- Prompt length increase is bounded at ~10 lines regardless of pipeline length.

**Acceptance:** `test_pipeline_history_block_format` uses `max_items=3` with 5 entries
and asserts only the 3 most recent appear.

---

## EC-10 — Pipeline History: EVENTS.jsonl is missing `summary` or `conversation` field

**Scenario:** An old or hand-crafted AGENT_DONE event is missing the `summary` or
`conversation` field.

**Behaviour:**
- `build_pipeline_history_block` uses `"?"` for a missing `conversation` value and
  `"(no summary)"` for a missing `summary` value.
- The block is still generated; no exception is raised.

**Acceptance:** Covered by format contract in S-8. Builder writes a defensive
`.get("summary", "(no summary)")` and `.get("conversation", "?")` access pattern.
