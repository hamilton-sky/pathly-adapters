---
name: Feature Index
---
# studio-polish — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer design decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | Studio component diagram |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Zustand dirty-state + skeleton pattern decisions |
| `EDGE_CASES.md` | yes | Corrupt YAML, concurrent saves, navigation with dirty file |
| `HAPPY_FLOW.md` | yes | Open flow → edit → save golden path |
| `FLOW_DIAGRAM.md` | yes | FlowEditor load/save state machine |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | Conv 1 | Add skeleton loader while `loading` is true |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts` | Conv 1 | Surface parse error line number in error state |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | Conv 1 | Disable Save button + show spinner during `saving` |
| `studio/src/renderer/src/components/ui/Button.tsx` | Conv 1 | Add `loading` prop to Button component |
| `studio/src/renderer/src/components/ui/Button.module.css` | Conv 1 | Add spinner animation style |
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | Conv 2 | Add unsaved-changes guard before switching away |
| `studio/src/renderer/src/store/index.ts` | Conv 2 | Wire unsaved-changes check into navigation |
| `studio/src/renderer/src/components/ui/Button.module.css` | Conv 1 | Change font-family from mono to base |
| `studio/vitest.config.ts` | Conv 3 | CREATE — vitest configuration |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.test.ts` | Conv 3 | CREATE — unit tests for load/save/error states |
| `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.test.ts` | Conv 3 | CREATE — unit tests for all validation rules |
| `src/install_cli/cli.py` | Conv 4 | CREATE — argparse + interactive menu extracted from setup_command.py |
| `src/install_cli/orchestrate.py` | Conv 4 | CREATE — _run_host, _run_host_uninstall extracted |
| `src/install_cli/setup_command.py` | Conv 4 | MODIFY — strip extracted logic, keep as thin dispatcher |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | FlowEditor skeleton + FlowWizard save UX + YAML error detail | S1, S2, S3 | TODO | `FlowEditor/index.tsx`, `useFlowFile.ts`, `FlowWizard.tsx`, `Button.tsx` |
| 2 | Unsaved-changes navigation guard | S4 | TODO | `FlowEditor/index.tsx`, `store/index.ts` |
| 3 | Vitest suite for useFlowFile + validateFlow | S5 | TODO | `vitest.config.ts`, 2 test files |
| 4 | Split setup_command.py | S6 | TODO | `cli.py`, `orchestrate.py`, `setup_command.py` |

---

## Feedback files (transient — deleted after resolution)

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
