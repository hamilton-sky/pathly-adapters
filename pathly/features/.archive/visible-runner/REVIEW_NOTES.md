# visible-runner Review Notes

This file combines the three requested outputs:

1. A concise critique of the plan.
2. A file-by-file plan-to-code mismatch check.
3. A revised architecture recommendation set.

## Priority Order

1. Parser robustness in `runner.py`.
2. Callback lifecycle cleanup in `supervisor.py` and `http_server.py`.
3. SSE reconnect and event ordering in `useHQ.tsx`.
4. Visual simplification in the Studio UI.

## Must Fix Before Build

- The plan needs explicit parser tests for PTY output, not just a function split.
- The plan needs monotonic callback handling for duplicate, late, or stale `run_id` callbacks.
- The plan needs a verified reconnect story for SSE delivery before the live runner becomes the source of truth for stage state.
- The plan needs a cleaner visual hierarchy so the runner state does not become noisy in the Studio UI.

## 1) Concise Critique

### What is strong

- The core boundary is correct: Python supervisor broadcasts SSE, Studio claims the run, Electron main owns PTYs, and Studio posts results back.
- The plan keeps parsing on the Python side instead of leaking adapter result logic into the renderer.
- The UI direction is coherent: runner-owned tabs, a compact run log, and a single jump-to-live affordance.

### What needs tightening

- The plan is too optimistic about output parsing. `runner.py` currently assumes a clean JSON blob from the subprocess, but PTY output can contain noise, partial lines, and adapter-specific variation.
- The lifecycle around `run_id` events needs explicit cleanup and idempotency. Started/result callbacks, fallback timeouts, aborts, and duplicate responses all need deterministic behavior.
- The UI has a risk of over-signaling. Runner tab styling, live pill, card, and pulsing status dots should not all compete for attention.
- SSE reliability needs explicit verification. The visible-runner flow depends on event ordering and reconnect behavior, but the current renderer handler is only happy-path oriented.

## 2) File-by-File Mismatches

### `src/pathly_orchestrator/runner.py`

- The plan says to extract `resolve_argv()` and `parse_result()`, which is appropriate.
- Mismatch risk: the plan does not yet specify enough parser tests for PTY-style output.
- Recommendation: add tests for ANSI escape sequences, truncated output, multiple JSON-like fragments, and adapter-specific result shape drift.
- Severity: high. If this parser is wrong, the runner can report the wrong cost/session state or fail after a visually successful terminal run.

### `src/pathly_orchestrator/supervisor.py`

- The plan adds `threading.Event` orchestration for started/result callbacks, which fits the existing runner loop.
- Mismatch risk: cleanup semantics are underdefined for duplicate callbacks, timeout fallback, abort, and stale `run_id` state.
- Recommendation: make event lifecycle idempotent and explicitly clear registry entries on every terminal completion path.
- Severity: high. Unclean lifecycle handling here can wedge a stage, leak stale state, or create a false headless fallback.

### `src/pathly_orchestrator/http_server.py`

- The two callback endpoints fit the supervisor boundary well.
- Mismatch risk: the plan should explicitly define what happens if a callback arrives twice or arrives after headless fallback has already taken over.
- Recommendation: return stable no-op responses for duplicate terminal callbacks and make the handler state transitions monotonic.
- Severity: high. This is the race boundary between renderer and supervisor, so duplicate or late callbacks must never corrupt state.

### `studio/src/main/ipc/terminal.ts`

- The plan correctly keeps PTY ownership in Electron main.
- Mismatch risk: buffer management, exit handling, and result POST retries need to be treated as part of the core runner contract, not just implementation detail.
- Recommendation: keep runner metadata in a dedicated map, cap the output buffer, and ensure exit events always clean up tab ownership and submission state.
- Severity: medium-high. Bugs here are user-visible and can break the “visible runner” promise even if the backend is correct.

### `studio/src/renderer/src/components/HQ/useHQ.tsx`

- The plan wires the SSE events in the right place.
- Mismatch risk: reconnect behavior and event ordering are not yet proven by the current code path.
- Recommendation: verify that the renderer can recover from missed SSE messages without duplicating tabs or losing the stage log entry.
- Severity: high. If SSE ordering drifts, the UI can show the wrong run state even though the backend is healthy.

### `studio/src/renderer/src/store/runnerStore.ts`

- The stage log and navigation state are the right new store concepts.
- Mismatch risk: the log can become inconsistent if stage start, terminal claim, fallback, or result events arrive out of order.
- Recommendation: store state transitions as append/update operations with explicit "no-op if missing" guards.
- Severity: medium. This is mostly correctness and UX consistency, but it can still confuse the operator during live runs.

### `studio/src/renderer/src/components/HQ/RunnerLogCard/*`

- The component is a good addition, but it should stay a projection of store state.
- Mismatch risk: if it starts deriving too much behavior locally, the UI and live runner state will drift.
- Recommendation: keep it read-only, store-driven, and minimal.
- Severity: medium. The main risk is drift and complexity creep, not backend breakage.

## 3) Revised Architecture Recommendations

### A. Keep the transport split

- Keep SSE for supervisor -> Studio.
- Keep HTTP callbacks for Studio -> supervisor.
- Do not add polling or a second coordination transport.

### B. Make the output parser a first-class unit

- Treat `parse_result()` as a separate, test-heavy boundary.
- Make it robust to PTY noise, ANSI sequences, and adapter output drift.
- Prefer predictable adapter output formats over ad hoc scanning rules.

### C. Make callback handling monotonic

- `started` should only move a run from pending to claimed.
- `result` should only move a run to completed once.
- Duplicate callbacks should be safe no-ops, not state corruption.
- Timeout fallback should close the terminal-claim path cleanly.
- Add explicit state tables for `pending`, `claimed`, `headless`, `completed`, and `aborted` so every transition is unambiguous.

### D. Reduce visual noise

- Use one ownership marker on tabs.
- Use one live affordance in HQ.
- Use one run-history card.
- Keep the status dot and the live pill, but do not stack extra animation or duplicate emphasis.
- Remove any decoration that does not answer a distinct user question.

### E. Make fallback visible

- If the run falls back to headless execution, surface that state clearly.
- Do not bury the fallback as an invisible implementation detail.

### F. Narrow Conv 2

- Keep Conv 2 focused on PTY claim, result POST, and styling.
- Avoid adding extra polish work into the same phase.
- Anything that changes the information architecture should move to the HQ log-card conversation.
- Do not let Conv 2 absorb log-card behavior or decision-state polish.

## Final Recommendation

Proceed with the feature, but revise the implementation to:

- harden parsing,
- define terminal-event cleanup semantics,
- verify SSE reconnect behavior,
- and simplify the UI signals.

That keeps the feature implementable without turning the visible runner into a fragile cross-process state machine.

## Reviewer Summary

- Build it, but only after the parser, lifecycle, and SSE guarantees are tightened.
- The backend contract is the highest-risk area.
- The UI should be simplified, not embellished.

## Addendum: Build-Ready Review Checklist

Use this checklist before implementation starts:

- Verify the real `runner.py` output shape with tests before changing the terminal path.
- Define duplicate-callback behavior for `POST /runner/terminal/started` and `POST /runner/terminal/result`.
- Make stale `run_id` cleanup explicit on timeout, abort, and fallback.
- Confirm `useHQ.tsx` can survive SSE reconnects without duplicating the stage log or opening duplicate tabs.
- Keep `terminal.ts` as the only PTY owner and ensure it always clears tab ownership on exit.
- Keep the UI to one ownership signal per surface: tab border, live pill, or log card, not all three fighting for attention.

## Addendum: Recommended Implementation Order

1. Finish parser extraction and tests in `src/pathly_orchestrator/runner.py`.
2. Lock down callback lifecycle in `src/pathly_orchestrator/supervisor.py` and `src/pathly_orchestrator/http_server.py`.
3. Wire `studio/src/main/ipc/terminal.ts` result posting and exit cleanup.
4. Verify `studio/src/renderer/src/components/HQ/useHQ.tsx` reconnection and event ordering.
5. Add the runner UI polish last, after the live data path is stable.

## Addendum: Short Form Recommendation

- The plan is directionally correct.
- The risk is not the architecture; it is the edge handling.
- Harden the backend contract first, then keep the UI restrained.
