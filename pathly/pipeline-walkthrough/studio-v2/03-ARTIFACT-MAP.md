# Artifact Map — studio-v2 Conv 6

**Date:** 2026-05-19

---

## Feedback Artifacts

| File | Created by | Resolved by | Conv |
|------|-----------|-------------|------|
| TEST_FAILURES.md | tester | builder | 6 |

---

## Source Files Changed (Conv 6)

| File | Change |
|------|--------|
| `studio/src/renderer/src/components/Monitor/EventLog.tsx` | Replace EventRow with RawEventLine (raw JSON.stringify + color-coding) |
| `src/pathly_orchestrator/runner.py` | Add tool_uses counting + patching in _patch_last_agent_done |
| `studio/tsconfig.web.json` | Bump target/lib ES2020 → ES2021 |
| `studio/src/renderer/src/types/global.d.ts` | Add clipboard type declaration |
| `studio/src/renderer/src/types/css.d.ts` | New: ambient CSS module declaration |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Fix TS2352 type cast |
| `studio/src/renderer/src/components/Editor/index.tsx` | Fix stale FrontmatterValues import |
| `studio/src/renderer/src/components/FlowWizard.tsx` | Fix stepDot TS2560/TS2349 |
