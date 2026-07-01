# mermaid-template — Implementation Plan

## Overview
Adds a Mermaid diagram template to the plan templates directory and wires it into the plan skill so planners know when to offer it. Two-file change: one new template, one skill update. No cross-layer dependencies.

## Layer Architecture

```
plan.md skill  →  MERMAID_DIAGRAM.template.md
     ↓                       ↓
Section 4i rules        template content
(when to offer)         (what to fill in)
```

## Phases

### Phase 1: Create MERMAID_DIAGRAM.template.md   ← Conversation: 1
**File:** `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` — CREATE
**Done when:** The file exists at the stated path, contains a valid `flowchart TD` Mermaid block, a fallback flow block, and a component legend section — all using `[bracket placeholder]` notation.
**Delivers stories:** S1.1
**Depends on:** nothing
**Enables:** Phase 2 (plan.md can reference the template by name)
**Details:**
- Mirror structure of `FLOW_DIAGRAM.template.md`: happy path section, fallback/error section, component legend table
- Use `flowchart TD` as the diagram type
- Wrap each diagram in a fenced ` ```mermaid ``` ` block
- Use `[bracket notation]` for all placeholders, consistent with other templates
- Keep it short — a skeleton the planner fills in, not a worked example

---

### Phase 2: Update plan.md Section 4i   ← Conversation: 2
**File:** `src/pathly_data/core/skills/plan.md` — MODIFY: Section 4i only
**Done when:** Section 4i tells the planner to read `MERMAID_DIAGRAM.template.md` when the feature is orchestration-heavy, alongside the existing ASCII path, and both template names are present in the section.
**Delivers stories:** S1.2
**Depends on:** Phase 1 (template must exist before skill references it)
**Enables:** planners to offer Mermaid diagrams in plan output
**Details:**
- Locate the existing `### 4i. FLOW_DIAGRAM.md` section in plan.md
- Add a sentence (or short bullet) that says: for orchestration-heavy features, also read `core/templates/plan/MERMAID_DIAGRAM.template.md` and offer Mermaid as the diagram format
- Keep ASCII as the default; Mermaid is an opt-in for features where the calling structure benefits from Mermaid rendering
- Do NOT touch any other section of plan.md

## Prerequisites
- `src/pathly_data/core/templates/plan/FLOW_DIAGRAM.template.md` exists (reference for structure)
- `src/pathly_data/core/skills/plan.md` exists and Section 4i is present

## Key Decisions
- Mermaid as opt-in alongside ASCII, not a replacement — preserves backward compatibility with ASCII-only hosts
- Orchestration-heavy trigger (new inter-agent calling conventions, sub-skill flows) matches the retro lesson that fired this feature
