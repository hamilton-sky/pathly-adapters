# UI ASCII Diagrams - studio-visual-flow-builder

This file shows the intended shape of the new Pathly Studio visual flow builder.
It is a builder-facing companion to `DESIGN.md`, not a pixel-perfect layout spec.

## Overall Studio Layout

The feature should keep Studio as a dense operational tool: library on the left,
visual authoring in the center, inspector on the right, and runtime/log surfaces
below or in Monitor.

```text
+--------------------------------------------------------------------------------+
| Top Bar                                                                        |
| [Project] [Flow: team.flow.yaml] [Target: Pathly]        [Watch] [Export]      |
+----------------------+-----------------------------------------+---------------+
| Library              | Visual Flow Canvas                      | Inspector     |
|                      |                                         |               |
| Filter...            |   +------------+      default           | Node: BUILDING|
|                      |   | STORMING   | ---------------------> |               |
| FLOWS                |   | planner    |                        | Identity      |
|   team.flow.yaml     |   +------------+                        | Behavior      |
|   debug.flow.yaml    |          |                              | Transitions   |
|                      |          | plan ready                   | Validation    |
| SKILLS               |          v                              |               |
|   review.md   ::     |   +------------+      pass              | Agent         |
|   test.md     ::     |   | BUILDING   | --------------------+  | [builder v]   |
|                      |   | builder    |                     |  |               |
| AGENTS               |   +------------+                     |  | + Add rule    |
|   planner.md  ::     |          |                            |  |               |
|   builder.md  ::     |          | needs fixes                |  +--------------+
|                      |          v                            |
| TEMPLATES            |   +------------+                      |
|   feature-flow       |   | REVIEWING  | --------------------+
|                      |   | reviewer   |
+----------------------+---+------------+----------------------------------------+
| Terminal / Monitor / Event Log                                                 |
+--------------------------------------------------------------------------------+
```

## Left Library

Library rows are reusable workflow primitives. Clicking previews the item;
dragging places or assigns it in the canvas.

```text
+----------------------+
| Filter...            |
+----------------------+
| FLOWS              + |
| > team.flow.yaml     |
|   debug.flow.yaml    |
|   explore.flow.yaml  |
|                      |
| SKILLS             + |
|   :: review.md       |
|   :: test.md         |
|   :: write-docs.md   |
|                      |
| AGENTS             + |
|   :: planner.md      |
|   :: builder.md      |
|   :: reviewer.md     |
|                      |
| TEMPLATES          + |
|   :: feature-flow    |
|   :: debug-flow      |
|                      |
| WORKSPACE            |
|   Plan               |
|   Monitor            |
|   Settings           |
+----------------------+
```

Recommended visual behavior:

- Use compact rows, not large cards.
- Use a small drag affordance such as `::` or a Lucide grip icon.
- Use section icons later: graph/path for flows, tool/module for skills,
  actor/node for agents, blueprint for templates, state sheet for plan.
- Keep advanced/internal rows collapsed until needed.

## Visual Flow Canvas

The canvas should show Pathly states as compact nodes and runtime routes as
connected edges. Boxes are appropriate here because users are editing nodes.
The critical improvement is visible connection lines between states.

```text
                     default
+------------+ -----------------> +------------+
| PLANNING   |                    | BUILDING   |
| planner    |                    | builder    |
| ! warning  |                    |            |
+------------+                    +------------+
       ^                                 |
       |                                 | REVIEW_FAILURES.md
       | retry                           v
+------------+ <----------------- +------------+
| FIXING     |                    | REVIEWING  |
| builder    |                    | reviewer   |
+------------+                    +------------+
                                      |
                                      | pass
                                      v
                                +------------+
                                | TESTING    |
                                | tester     |
                                +------------+
                                      |
                                      | pass
                                      v
                                +------------+
                                | DONE       |
                                | terminal   |
                                +------------+
```

Recommended visual behavior:

- Nodes use neutral surfaces with a small accent strip or selected border.
- Current selection uses Pathly violet.
- Live/runtime indication uses cyan/blue, not violet.
- Completed/pass edges can use green only in Monitor, not as the default canvas
  graph color.
- Edge labels come from `transition_rules`: `default`, artifact name, content
  condition, decision option, feedback key, or action label.
- Invalid nodes show a small warning badge, not a full-width error banner.

## Canvas Toolbar

The canvas toolbar should expose authoring controls without turning the screen
into a wizard.

```text
+----------------------------------------------------------------------------+
| [Visual] [YAML]                         [Fit] [Lock] [Validate] [Export v] |
+----------------------------------------------------------------------------+
|                                                                            |
|                         React Flow canvas                                  |
|                                                                            |
+----------------------------------------------------------------------------+
```

Recommended visual behavior:

- `Visual` and `YAML` remain tabs or segmented controls.
- `Fit`, `Lock`, and validation should use icon buttons with tooltips.
- Export target selection stays near the export button.
- Save/export actions should be disabled when validation has blocking errors.

## Node Inspector

Clicking a state node opens a docked inspector. This should replace the current
overlay panel.

```text
+------------------------------+
| BUILDING                  [x] |
+------------------------------+
| Identity                     |
| State ID     BUILDING        |
| Label        Building        |
|                              |
| Assigned Behavior            |
| Agent/Skill   [builder   v]  |
| Source        agents/builder |
|                              |
| Outgoing Transitions          |
| -> REVIEWING    default      |
| -> BUILDING     retry/fix    |
|                              |
| Required Artifacts            |
| [ ] IMPLEMENTATION.md         |
| [ ] NOTES.md                  |
|                              |
| Validation                    |
| ok Agent exists               |
| ok Has outgoing transition    |
+------------------------------+
```

Recommended visual behavior:

- State ID is read-only in this feature. Rename remains YAML-only for now.
- Assigned behavior picker is a popover, not a modal.
- Missing agents/skills remain visible and selectable, with a warning badge.
- Validation messages stay local to the relevant field or section.

## Behavior Picker

The behavior picker appears from the node inspector.

```text
+--------------------------------+
| Assigned behavior              |
| [builder                     v] |
+--------------------------------+
| Search...                       |
| [all] [skills] [agents]         |
|                                |
| agent   builder      agents/... |
| agent   reviewer     agents/... |
| skill   test         skills/... |
| skill   write-docs   skills/... |
+--------------------------------+
```

Recommended visual behavior:

- Keyboard navigation: up/down, Enter, Esc.
- Selecting an item writes `agent_map[stateId]`.
- Empty state is compact: `No matches. Drop a file into Skills or Agents.`

## Edge Inspector

Clicking an edge opens transition configuration.

```text
+--------------------------------+
| BUILDING -> REVIEWING      [x] |
+--------------------------------+
| Transition                     |
| Label        default           |
| Condition     [default     v]  |
|                                |
| Artifact Gate                  |
| File         REVIEW.md         |
| Rule         exists            |
|                                |
| Transition Actions             |
| + skill: write-review-summary  |
| + message: handoff to reviewer |
|                                |
| Validation                     |
| ok Target exists               |
| ok Rule matches runtime schema |
+--------------------------------+
```

Recommended visual behavior:

- Edit the state-keyed `transition_rules[source]` schema only.
- Do not revive the old artifact-keyed shape.
- Ensure the target is listed in `transitions[source]`.
- Show edge-level errors both on the edge and in this inspector.

## Validation UX

Validation should be continuous, but quiet. Errors attach to the affected
node, edge, field, or export control.

```text
+------------+       missing target       +------------+
| BUILDING ! | -------------------------> | DEPLOYING? |
| builder    |                            | missing    |
+------------+                            +------------+

Inspector validation
+------------------------------+
| Validation                    |
| ! Target state DEPLOYING missing |
| ! Behavior deploy not in library |
+------------------------------+
```

Recommended visual behavior:

- No global warning wall unless export/save is blocked.
- Node badges use amber for warnings, red for errors.
- Export remains disabled while errors exist.
- Warnings require explicit acknowledgement before export.

## YAML Preview

YAML is the inspectable source view. It should not destroy the last valid graph
when the user has a parse error.

```text
+----------------------------------------------------------------------------+
| [Visual] [YAML]                                                    [Save]   |
+----------------------------------------------------------------------------+
| states:                                                                    |
|   - PLANNING                                                               |
|   - BUILDING                                                               |
|   - REVIEWING                                                              |
|                                                                            |
| transitions:                                                               |
|   BUILDING: [REVIEWING]                                                    |
|                                                                            |
| transition_rules:                                                          |
|   BUILDING:                                                               |
|     default: REVIEWING                                                     |
+----------------------------------------------------------------------------+
| Parse status: valid                                                        |
+----------------------------------------------------------------------------+
```

Invalid YAML state:

```text
+----------------------------------------------------------------------------+
| [Visual] [YAML]                                                    [Save]   |
+----------------------------------------------------------------------------+
| states:                                                                    |
|   - PLANNING                                                               |
|   - BUILDING                                                               |
| transition_rules:                                                          |
|   BUILDING:                                                               |
|     default REVIEWING   <-- parse error                                    |
+----------------------------------------------------------------------------+
| Warning: YAML parse failed. Visual view is keeping the last valid graph.    |
+----------------------------------------------------------------------------+
```

## Export Controls

Export writes one canonical flow model to explicit host targets.

```text
+------------------------------------------------------+
| Export target                                        |
| ( ) Pathly package                                   |
| ( ) Claude Code                                      |
| ( ) Codex                                            |
|                                                      |
| Validation                                           |
| ok No blocking errors                                |
| ! Codex export path will be created                  |
|                                                      |
|                         [Cancel] [Export]            |
+------------------------------------------------------+
```

Recommended visual behavior:

- Export button is disabled for errors.
- Warnings show before export and require acknowledgement.
- Success toast includes target path and a copy-path action.

## Monitor State Rail

The Monitor should not use isolated stage pills as the primary metaphor. Runtime
progress is better represented as a connected state rail. Pills can remain as
small labels, but the rail should show flow continuity.

```text
Pipeline
   done          done           active          next           next
    o-------------o--------------*---------------o--------------o
 STORMING     PLANNING       BUILDING       REVIEWING       TESTING
                                |
                                | running: builder #3
                                | waiting for: IMPLEMENTATION.md

Current
State: BUILDING      Agent: builder      Conv: 3      Source: SSE live
```

Loop/rework state:

```text
   done          active         blocked/rework
    o-------------*----------------x
 PLANNING     BUILDING        REVIEWING
                  ^              |
                  | needs fixes  |
                  +--------------+
```

Recommended visual behavior:

- Completed states: muted green connected history.
- Current state: cyan/blue waypoint.
- Future states: muted neutral.
- Rework loops: small return edge, not another full diagram.
- Event log remains below or beside the rail.

## Event Log

The event log should stay dense, but it can become easier to scan with grouping
and subtle color roles.

```text
+----------------------------------------------------------------------------+
| Event Log                                                                  |
+----------------------------------------------------------------------------+
| 22:45:23  TRANSITION      STORMING  -> PLANNING                            |
| 22:51:55  TRANSITION      PLANNING  -> BUILDING                            |
|                                                                            |
| builder #1                                                                 |
| 00:10:00  AGENT_DONE      DONE       13.2k in  2.1k out  $0.0312           |
| 00:11:00  TRANSITION      BUILDING  -> REVIEWING                           |
|                                                                            |
| reviewer #1                                                                |
| 00:12:00  AGENT_DONE      PASS                                             |
+----------------------------------------------------------------------------+
```

Recommended visual behavior:

- Keep monospace for log rows.
- Use color for event type, not every word.
- Group by agent/conversation when possible.
- Keep totals visible but low-emphasis.

## Empty Canvas

Empty states should be useful but not decorative.

```text
+----------------------------------------------------------------------------+
|                                                                            |
|                                                                            |
|                 Drag a skill or agent from the library,                    |
|                    or click + to add a state.                              |
|                                                                            |
|                                                                            |
+----------------------------------------------------------------------------+
```

Recommended visual behavior:

- No large illustration.
- No marketing copy.
- Include one obvious add-state affordance.

## Color Use Summary

```text
Pathly identity / selected object:   violet
Runtime live activity:               cyan / blue
Current graph edge:                  blue
Completed/pass:                      green
Waiting/review/warning:              amber
Blocked/error/destructive:           red
Surfaces and structure:              graphite / neutral
```

