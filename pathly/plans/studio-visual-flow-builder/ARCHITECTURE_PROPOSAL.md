# studio-visual-flow-builder - Architecture Proposal

## Problem Statement

Pathly Studio has the right shell for a workflow IDE, but the visual flow editor is not yet the real authoring surface. Users can see nodes and edit YAML, but they need visible connections, drag/drop behavior assignment, inspector-based configuration, validation, and export.

## Proposed Solution

Use one canonical in-memory flow model based on the existing YAML schema. React Flow renders and edits that model. YAML preview serializes/deserializes the same model. Export targets consume the same serialized flow and add only target-specific file placement or wrapper behavior.

## Layer Breakdown

```
Sidebar library
  items: flows, skills, agents, templates
        |
        v
Visual flow editor
  React Flow nodes/edges + inspector
        |
        v
Canonical flow model
  states, transitions, agent_map, rules, actions
        |
        +--> YAML preview/save
        |
        +--> Export targets
             Pathly package / Claude Code / Codex
```

## Key Design Decisions

### Decision 1: Canvas-first, wizard-second

- **Options considered:** Wizard-first, YAML-first, canvas-first.
- **Chosen:** Canvas-first.
- **Rationale:** Pathly flows are graph-shaped. A wizard is useful for seeding a simple flow, but a graph editor better represents state transitions, feedback loops, and routing.

### Decision 2: Existing YAML schema remains canonical

- **Options considered:** New graph schema, React Flow state persistence, existing YAML schema.
- **Chosen:** Existing YAML schema with UI-only graph state.
- **Rationale:** Existing runtime and package files already use `states`, `transitions`, `agent_map`, `transition_rules`, and `transition_actions`.

### Decision 3: Skills and agents are library items, not mandatory concepts

- **Options considered:** Expose all internals, hide all internals, progressive disclosure.
- **Chosen:** Progressive disclosure.
- **Rationale:** Users need power, but first-run UX should not require understanding every Pathly internal directory.

### Decision 3a: Library items are reuse primitives by default

- **Options considered:** Edit-on-click (current), preview-on-click + explicit edit, hover preview only.
- **Chosen:** Preview-on-click + explicit edit.
- **Rationale:** In the visual flow editor, the dominant intent for a skill/agent/template row is "use it in a flow", not "edit its source". Edit-on-click leaks bundled internals into a user's normal authoring path. Reuse-first behavior matches the canvas-first architecture and is implementable as a one-line default on the existing `Editor` component.
- **Scope:** Applies to skills, agents, and templates only. Flows and workspace artifacts (debugs, explorations, plans) continue to open in their authoring surface on click.

### Decision 4: Tree-internal file system operations are out of scope

- **Options considered:** Add VS Code-style FS drag/drop to the sidebar, defer to a separate feature, never add it.
- **Chosen:** Defer.
- **Rationale:** The Pathly sidebar is a domain-aware library, not a generic FS tree. Bundling tree-internal FS operations into a "canvas-first authoring" feature would multiply scope and conflict with the canvas-first goal. A future `studio-file-tree-ops` feature can deliver that separately.

### Decision 5: Export is adapter-based

- **Options considered:** Separate editors per host, one graph with export adapters.
- **Chosen:** One graph with export adapters.
- **Rationale:** Pathly should stay the source of truth, while Claude Code and Codex get host-specific packaging.

## Key Components

- `flowToGraph.ts`: Converts YAML flow data to React Flow nodes and edges.
- `useFlowGraph.ts`: Owns React Flow state and writes semantic changes back to the flow model.
- `StateNode.tsx`: Displays state identity and behavior, with source/target handles.
- `Sidebar.tsx`: Supplies draggable library items while preserving file explorer behavior.
- `NodePanel.tsx`: Docked inspector for state/node configuration.
- `EdgePanel.tsx`: Docked inspector for transition configuration.
- `YamlView/index.tsx`: YAML preview/edit surface.
- `pathlyApi.ts`: Filesystem bridge for save/export operations.

## Interface Design

Use a small drag payload:

```ts
interface PathlyLibraryDragItem {
  type: 'skill' | 'agent' | 'template' | 'flow'
  name: string
  path: string
  behaviorKind?: 'skill' | 'agent'
}
```

Use validation issues as data, not only strings:

```ts
interface FlowValidationIssue {
  level: 'error' | 'warning'
  target: 'flow' | 'node' | 'edge' | 'export'
  id?: string
  message: string
}
```

Use explicit export targets and a path resolver:

```ts
type FlowExportTarget = 'pathly-package' | 'claude-code' | 'codex'

interface FlowExportContext {
  projectPath: string
  flowName: string  // e.g. "debug"
}

function resolveExportPath(target: FlowExportTarget, ctx: FlowExportContext): string {
  switch (target) {
    case 'pathly-package':
      return `${ctx.projectPath}/src/pathly_data/core/flows/${ctx.flowName}.flow.yaml`
    case 'claude-code':
      return `${ctx.projectPath}/.claude/pathly-flows/${ctx.flowName}.flow.yaml`
    case 'codex':
      return `${ctx.projectPath}/.codex/pathly-flows/${ctx.flowName}.flow.yaml`
  }
}
```

The Pathly target overwrites the source; Claude Code and Codex write side-by-side copies of the canonical YAML.

## Risks

- **Schema drift:** Mitigate by using existing flow YAML files as fixtures and not adding schema keys casually.
- **React Flow state drift:** Mitigate by resyncing on selected flow changes and keeping semantic state in `FlowYaml`.
- **Overexposed internals:** Mitigate with progressive disclosure in the library.
- **Unsafe export:** Mitigate with validation-gated target actions.
