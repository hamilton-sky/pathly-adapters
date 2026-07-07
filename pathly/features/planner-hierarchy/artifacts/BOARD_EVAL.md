# Board Evaluation

## Classification
CODE

## Summary
The planner-hierarchy board is executing a 3-goal plan to build recursive decomposition at every level of the Pathly hierarchy (project→features→goals→tasks). G1 (feature-planner: feature→goals) is fully complete — skill, flow, route, sibling awareness, UI surface, and tests all shipped. G2 (project-planner: spec→features) had its 6-task DAG seeded today and is ready to execute; no G2 files exist yet. G3 (modernize BMAD/PRD import to the goal-DAG model) has a goal message but no task DAG — this is the primary gap. A secondary constraint is that `comms_messages.py` sits at 389 lines and G2-T2 will add `count_features_for_project` to it, which will exceed the 400-line limit without a pre-split.

## Key unknown / risk
G3 cannot fully integrate until G2's `/comms/project/decompose` route and `project-consultation.flow.yaml` exist, but the prd-import skill update (G3-T1) can be written and tested in isolation since it posts directly to `/comms/post` rather than going through the route.

## Gaps identified

### Gap 1 — G3 has no task DAG (blocker for import modernization)
G3 goal exists (`9f77f795`) but has zero tasks. SPEC: rework `planning/prd-import.md` to emit type=feature on the project board and type=goal on each feature board, replacing the old CONVERSATION_PROMPTS/phases output. BMAD maps naturally (PRD → project, epics → features, stories → goals). Two tasks needed — skill update and tests.

### Gap 2 — G2-T2 will push comms_messages.py over the 400-line limit
`db/queries/comms_messages.py` is at 389 lines (flagged in the G1-T2 Review PASS). G2-T2 adds `count_features_for_project` to it, which will push it past the hard 400-line limit. The builder for G2-T2 must split the file before adding the new function. This is under-specified in the current T2 task description. Posted as a constraint to the board.

### Gap 3 — G2-T5 (project-decompose UI) doesn't mention boardScope threading (minor)
T5 says "when the active board is the PROJECT board" but `useEvaluateBoardButton` currently only receives `boardKey`, not `boardScope`. The builder must pass `boardScope` from `GoalsView` down through `EvaluateBoardButton` → `useEvaluateBoardButton` to conditionally show "Decompose into features" vs "Decompose into goals" in the TARGET dropdown. This is derivable from the code but not spelled out in the task. Non-blocking since `boardScope` is available on `GoalsView`.

## Recommended next steps
- Seed G3 task DAG under the existing G3 goal (two tasks: skill update + tests)
- Post a constraint about the comms_messages.py 400-line pre-split required for G2-T2
- G2 tasks are ready to execute — no new tasks needed for G2
