# studio-visual-flow-builder - Feature Index

> Read this first. Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | Single entry point for feature context |
| `DESIGN.md` | Designer | Builder, Reviewer | Studio UX and interaction spec |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase implementation plan |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status |
| `HAPPY_FLOW.md` | Planner | Builder, Tester | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder, Reviewer | Visual interaction and data flow |
| `UI_ASCII_DIAGRAMS.md` | Designer | Builder, Reviewer | ASCII mockups for layout, canvas, inspectors, Monitor, validation, YAML, and export |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Graph model and export decisions |
| `EDGE_CASES.md` | yes | Canvas, YAML, validation, and export risks |
| `HAPPY_FLOW.md` | yes | Ideal authoring journey |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |
| `UI_ASCII_DIAGRAMS.md` | yes | ASCII UI diagrams and component-level visual recommendations |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` | Conv 1 | Make YAML to graph conversion deterministic and label edges from the real state-keyed `transition_rules` schema |
| `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` (CREATE) | Conv 3 | Pure validation utility returning `FlowValidationIssue[]` |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` | Conv 1 | Resync nodes and edges when selected flow data changes; keep graph edits canonical |
| `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` | Conv 1, Conv 3 | Add React Flow handles, compact node affordances, and validation badges |
| `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Conv 2, Conv 3, Conv 4 | Wire canvas drag/drop, docked inspector layout, validation display, export controls |
| `studio/src/renderer/src/components/FlowEditor/VisualView/VisualView.styles.ts` | Conv 3 | Switch inspector from absolute overlay to docked flex pane |
| `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` | Conv 3 | Node inspector with behavior picker popover and validation rows |
| `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` | Conv 3 | Edge inspector with condition, artifact gate, and action editing using state-keyed `transition_rules` |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts` | Conv 1, Conv 4 | Preserve last valid graph during YAML errors and expose export-ready serialization |
| `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` | Conv 4 | Harden YAML preview/edit sync and parse-error handling |
| `studio/src/renderer/src/components/Editor/index.tsx` | Conv 2 | Default to `preview` tab for skills/agents/templates; gate edit behind explicit action |
| `studio/src/renderer/src/components/Sidebar.tsx` | Conv 2 | Add draggable library rows (HTML5 drag/drop). Tree-internal FS drag/drop is out of scope. |
| `studio/src/renderer/src/hooks/useProjectFiles.ts` | Conv 2 | Already returns library metadata; no schema change unless drop handler needs more fields |
| `studio/src/renderer/src/types/index.ts` | Conv 1, Conv 2, Conv 3, Conv 4 | Extend `FlowYaml` (`storage_path`, `feedback_routing`); add `PathlyLibraryDragItem`, `FlowValidationIssue`, `FlowExportTarget` |
| `studio/src/renderer/src/services/pathlyApi.ts` | Conv 4 | Expected no-op because current `window.pathly.fs.write` creates parent directories; add helper only if this changes |

> Verify these paths exist before editing. Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Phases | Title | Stories | Status | Key files touched |
|---|---|---|---|---|---|
| 1 | 1-3 | Repair graph rendering and canonical sync | S1, S2 | TODO | `flowToGraph.ts`, `useFlowGraph.ts`, `StateNode.tsx`, `types/index.ts` |
| 2 | 4-7 | Reuse-only library + drag/drop | S3, S8 | TODO | `types/index.ts`, `Editor/index.tsx`, `Sidebar.tsx`, `VisualView/index.tsx` |
| 3 | 8-11 | Docked inspector, behavior picker, validation | S4, S5 | TODO | `VisualView.styles.ts`, `VisualView/index.tsx`, `NodePanel.tsx`, `EdgePanel.tsx`, `validateFlow.ts`, `StateNode.tsx` |
| 4 | 12-14 | YAML preview hardening and export targets | S6, S7 | TODO | `YamlView/index.tsx`, `useFlowFile.ts`, `VisualView/index.tsx`, `pathlyApi.ts` |

---

## Schema guardrails

The runtime flow schema is the source of truth. In particular, `transition_rules` is keyed by source state:

```yaml
transition_rules:
  SOURCE:
    on_artifact:
      ARTIFACT.md: TARGET
    default: TARGET
```

Do not implement or preserve the older incorrect artifact-keyed shape `{ artifact_name: { source: target } }`.

Use `src/pathly_data/core/flows/*.flow.yaml` and `src/pathly_orchestrator/fsm.py` to verify any routing semantics before editing graph conversion, inspectors, or validation.

---

## Feedback files

Live in `pathly/plans/studio-visual-flow-builder/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder | Planner |
| `DESIGN_QUESTIONS.md` | Builder | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
