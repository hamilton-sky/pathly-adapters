# Feature Index — unified-cli-composition (Gate 2)

## What

Gate 2 of the unified-cli-composition feature. Gate 1 (composition seam + client-file-output + artifact-transform + Summary/Analyze/Split conversion) is complete. Gate 2 delivers the board-connected fragment pair (`board-start-context`, `task-dag-post`), the Decompose conversion to `compose_skill()`, and the drift-prevention helper.

## Why

Decompose is the first goal-backed proof of the composition model. If it works cleanly, Gate 3 (loop/drain board-I/O conversion) is much safer. Decompose currently hard-codes a Python prompt string and parses stdout — the last major call site in World B.

## Scope

Gate 2 only. Gate 3 (loop board-I/O, `profiles:` rename) is explicitly deferred.

## Plan files

| File | Purpose |
|---|---|
| `USER_STORIES.md` | 10 stories (US-01 – US-10) with binary acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | 3 phases, 8 steps, risk register, Gate 2 done-when checklist |
| `CONVERSATION_PROMPTS.md` | 3 self-contained builder prompts (Conv 1 – 3) |
| `PROGRESS.md` | Conversation status table (3 rows, all TODO) |
| `EDGE_CASES.md` | 10 edge cases: fragment gating, board unreachable, migration risk, dash-safety |
| `HAPPY_FLOW.md` | 5 end-to-end happy-path flows |
| `FLOW_DIAGRAM.md` | Before/after diagrams, component interaction map, data flow comparison |
| `ARCHITECTURE_PROPOSAL.md` | Architect-authored technical contract (do not recreate) |

## Conversations

| Conv | Delivers | Blocked on |
|---|---|---|
| 1 | US-01, US-02, US-03, US-04 | Nothing — starts immediately |
| 2 | US-05, US-06, US-07, US-08 | Conv 1 complete + fragments validated in isolation |
| 3 | US-09, US-10 | Conv 2 complete |

## Key files touched

- `src/pathly_data/core/skills/fragments/board-start-context.md` (new)
- `src/pathly_data/core/skills/fragments/task-dag-post.md` (new)
- `src/pathly_data/core/skills/composition.yaml` (planning/plan entry)
- `src/pathly_orchestrator/skills/compose.py` (goal_id capability + build_adapter_caps)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (compose_skill conversion)
- `src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py` (build_adapter_caps call)
- `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` (Summary error pill)
