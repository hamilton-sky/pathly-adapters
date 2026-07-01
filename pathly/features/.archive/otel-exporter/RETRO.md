# Retro — otel-exporter

## What shipped

Zero-dependency OTLP export for the Pathly pipeline. `otel_export.py` sends spans and logs via stdlib `urllib.request` (no opentelemetry-sdk required). Fire-and-forget integration into `http_server.py /record_activity`. Batch CLI `pathly-otel-export` reads `pathly.db`, filters `AGENT_DONE` events, and exports synchronously with `--dry-run` support. 25 acceptance criteria verified; 445 tests pass.

## What went well

- Zero-dep constraint held throughout — no third-party imports needed.
- Conv 1 scope was tight: one module, one integration point, 9 tests, all green first run.
- Review caught a real correctness bug (misleading dry-run stdout) before it shipped. The fix was surgical and tests updated in the same pass.
- Tester verified all 25 ACs in a single pass with no failures.

## What to improve

**convs_done stuck at 0 / FSM state mismatch.** Manual edits to `STATE.json` don't sync to SQLite. `eventlog.write_state` validates transitions against the DB value, so a stale `fsm_state` in SQLite blocks progress with a confusing error. Fix: add a `pathly-fsm-repair` CLI (or FSM endpoint) that reconciles `STATE.json` → SQLite in one command, or make `write_state` accept a `--force` flag for recovery.

**REVIEWING→TESTING gate needs an explicit artifact.** The FSM required `REVIEW.md` to exist before advancing. This was not called out in the conversation plan. Fix: document required artifacts per gate in `CONVERSATION_PROMPTS.md` or surface them in the FSM `next_action` response when the gate is about to be checked.

**Review conv token cost dominated.** Conv 2 review alone was 5x the build cost (0.77 vs 0.15). The reviewer re-read the full test suite. Scoping reviewer reads to changed files only would reduce this.

## Metrics

| Event | Agent | cost_usd | wall_seconds |
|---|---|---|---|
| Conv 1 build | builder | $0.1498 | 7 474 s |
| Conv 2 review | reviewer | $0.7689 | 420 s |
| Test pass | tester | $0.1651 | 998 s |
| **Total** | | **$1.0838** | **8 892 s** |
