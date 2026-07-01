# Retro — visible-runner

_Date: 2026-06-02 | Rigor: standard | 3 conversations_

---

## What went well

- **The 3-conversation split held clean.** Backend contracts (Conv 1), Studio wiring (Conv 2), RunnerLogCard polish (Conv 3) were self-contained and each verified independently.
- **Threading.Event for terminal spawn/result worked first time.** The 5-second headless fallback with `started_event`/`result_event` is clean, race-free, and covered the no-Studio case without special handling.
- **All CSS tokens planned upfront.** `--runner-bg`, `--runner-border`, `--runner-bg-active` defined in all 11 theme blocks once; never had to add a missing token mid-build.
- **SSE event structure was complete.** TERMINAL_SPAWN, TERMINAL_SIGNAL, RUNNER_WARNING, STAGE_CHANGE, DECISION_MENU — all wired end-to-end.

---

## What to improve

- **AC 3.1 (abort → TERMINAL_SIGNAL) was omitted from Conv 1.** The IMPLEMENTATION_PLAN.md mentioned it but the builder missed it. The abort path only killed the headless subprocess, not the Studio PTY. Fix: plan the abort→SSE broadcast path explicitly in the conversation prompt.
- **AC 2.2/2.3 first-focus ANSI warning was marked "bonus" in Conv 2 prompt** and never shipped — but it was a required acceptance criterion in USER_STORIES.md. Don't mark required AC as optional in builder prompts.
- **AC 1.5 banner label not stored in runnerTabMeta.** The banner was implemented but the label field was omitted from the metadata map at spawn time. A schema review step (listing all struct fields before coding) would catch this.
- **AC 4.4 multi-run history needed a design decision not captured in the plan.** "When does a new run start?" wasn't answered. Fix: add `RUN_STARTED` SSE to the event vocabulary at planning time, and wire `snapshotRun()` to it.
- **`global.d.ts` type declaration drifted from preload.ts.** The TypeScript builder updated the preload types but missed the renderer-side `Window` declaration. Pre-submit typecheck would catch this immediately.
- **Two review failure cycles (Conv 2 and Conv 3)** — both caught real violations. Conv 2: missing `mode` field in StageLogEntry + STAGE_CHANGE not calling recordStageStart + TERMINAL_SIGNAL ignoring tab_id. Conv 3: hardcoded rgba in .liveBtn:active + dead .cardRunning class reference.

---

## Lessons learned

1. **Every SSE event that requires a Studio response should have a companion Python broadcast.** If the renderer handles `X`, the supervisor must emit `X` — verify this mapping is 1:1 in the plan.
2. **Never mark a USER_STORIES.md acceptance criterion as "bonus" in a builder prompt.** The tester checks USER_STORIES, not the conversation prompt.
3. **Store all banner/display strings in the tab metadata map at spawn time.** Don't reconstruct display strings from raw IDs at exit time.
4. **For "multi-item history" UI patterns, define the snapshot boundary (RUN_STARTED SSE) at planning time.** Without an explicit signal for "new run begins", the store has no safe place to snapshot.
5. **When adding a field to preload.ts IPC types, always update `global.d.ts` in the same diff.** The two files must stay in sync; the typecheck catches drift, but only if you run it.
