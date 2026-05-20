# Artifact Map — studio-sidebar-tree

_Date: 2026-05-20_

## Plan artifacts

| File | Purpose |
|---|---|
| `pathly/plans/studio-sidebar-tree/FEATURE_INDEX.md` | Entry point — touchpoints + conv map |
| `pathly/plans/studio-sidebar-tree/USER_STORIES.md` | 5 stories with acceptance criteria |
| `pathly/plans/studio-sidebar-tree/IMPLEMENTATION_PLAN.md` | Phases across 5 convs |
| `pathly/plans/studio-sidebar-tree/CONVERSATION_PROMPTS.md` | Builder prompts per conv |
| `pathly/plans/studio-sidebar-tree/DESIGN.md` | Visual and interaction spec |
| `pathly/plans/studio-sidebar-tree/ARCHITECTURE_PROPOSAL.md` | Component structure and data model |
| `pathly/plans/studio-sidebar-tree/FLOW_DIAGRAM.md` | FSM / interaction flow diagram |
| `pathly/plans/studio-sidebar-tree/HAPPY_FLOW.md` | Happy path walkthrough |
| `pathly/plans/studio-sidebar-tree/EDGE_CASES.md` | Edge case catalogue |
| `pathly/plans/studio-sidebar-tree/PROGRESS.md` | Tracking (all DONE) |
| `pathly/plans/studio-sidebar-tree/RETRO.md` | Retrospective |

## Source files changed

_Based on `git diff --name-only master` at RETRO time. Only plan/state files were tracked; sidebar source files were built and reviewed within builder conversations on the working tree._

| File | Change |
|---|---|
| `pathly/plans/studio-sidebar-tree/EVENTS.jsonl` | Pipeline event log |
| `pathly/plans/studio-sidebar-tree/STATE.json` | FSM state (DONE) |

Note: Studio source files (sidebar components, context menu, drag-and-drop, lock logic) were modified during builder conversations. Run `git diff master -- studio/` for the full source diff once changes are committed.

## Feedback artifacts (archived)

| File | Round | Outcome |
|---|---|---|
| `pipeline-walkthrough/studio-sidebar-tree/artifacts/REVIEW_FAILURES_conv1_attempt1.md` | Conv 1 review | Fixed by builder — system lock icon and menu guard |
