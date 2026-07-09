# Board Evaluation

## Classification
CODE

## Summary
The board describes a phased hardening plan to take Pathly from "usable-with-significant-gaps" to a
trustworthy production-grade board-driven control plane. Two P0 storage tasks are already delivered
(T2 storage resolver, T3 layout-invariant test, both 2026-07-03) and the code-intelligence initiative
is shipped to master (2026-07-07). The board is currently in an actionable state: the critical P0
blocker — T1, the end-to-end golden-path smoke test — has not been started, and the P1 drift-stoppers
(T4–T7) and a blocking telemetry bug (B1: PATHLY_PROJECT_ROOT never exported by Studio) sit behind it.
This classification is CODE because all remaining work is concrete implementation with identified files
and acceptance criteria in SPEC.md.

## Key unknown / risk
Whether the golden-path (Studio Start → decompose → executor → DONE) passes 5 consecutive unattended
green runs — T1 is the gate that must pass before any P1/P2 work is trusted.

## Recommended next steps
- **T1** — End-to-end golden-path smoke test: drive the real FSM through all stages headlessly, no mocks
  on the FSM↔driver boundary; exit gate = 5 green runs (P0 — must go first).
- **B1 fix** — Export `PATHLY_PROJECT_ROOT` from Studio when spawning the FSM server and every CLI child
  (`index.ts` / `ipc/terminal.ts`); this single env-var turns the entire already-built cost/token display
  chain on (highest-leverage telemetry fix, gate: headless run produces ≥1 `BILLING_UPDATE` with non-null cost).
- **T4** — CI gates: 400-line limit check over `src/pathly_orchestrator/**` and `studio/src/**`;
  extend `check_version_sync.py` to cover README/CLAUDE.md/SECURITY prose docs (P1).
- **T5 + T6** — Doc-structure test (CLAUDE.md lists vs filesystem) + dash-safety contract test
  (3 mirrors → 1 asserted behavior); prevents doc drift from repeating this audit (P1).
- **T7** — Wire `evaluator` `_meta/*.yaml` in all 4 adapters (`claude`, `codex`, `copilot`, `antigravity`)
  and add adapter-parity test so the `evaluator` agent actually installs (P1).
