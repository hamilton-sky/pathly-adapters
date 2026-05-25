# Token Usage — studio-polish

**Date:** 2026-05-25 | **Total agent spawns:** 5

> Cost columns not captured (duration_ms used as proxy).

---

## Per-Agent Breakdown

| Conv | Agent | Tokens | Tool Uses | Duration (ms) | Wall (s) |
|------|-------|--------|-----------|---------------|----------|
| 0 | designer | 0 | 0 | 0 | 14 |
| 1 | builder | 26,727 | 26 | 308,371 | 348 |
| 2 | builder | 28,293 | 20 | 111,395 | 143 |
| 3 | builder | 24,360 | 18 | 161,093 | 540 |
| 4 | builder | 42,462 | 15 | 293,575 | 412 |
| 4 | reviewer | 21,131 | 14 | 44,824 | 146 |
| **Total** | | **143,973** | **93** | **919,258** | **1,603** |

---

## Scout Invocations (pre-analyze, read-only)

| Conv | Scout target | Purpose |
|------|-------------|---------|
| 1 | Button.tsx, FlowWizard | Props + save button shape |
| 1 | FlowEditor/index.tsx, useFlowFile.ts | Loading state + YAML catch |
| 2 | FlowEditor, store, NewItemDialog | Dirty state + modal pattern |
| 3 | useFlowFile.ts, validateFlow.ts | Signatures for test writing |
| 3 | studio/package.json | Existing test infra check |
| 4 | setup_command.py | Split boundary analysis |
| 4 | pyproject.toml | Entry point check |
| review-4 | ARCHITECTURE_PROPOSAL.md | Architectural rules |
| review-4 | install_cli/*.py | Dependency graph check |

Scout invocations are not included in AGENT_DONE token counts above.
