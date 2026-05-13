# parallel-scout-standard — Retrospective

## Plan Quality

**Conversation sizing:** Too big — conversations needed to be smaller, with tighter scope per task. Conv 2 (3 skill files) and Conv 4 (4 agent files) each touched multiple files that could have been split into individual conversations for better reliability.

**Surprises:** Nothing broke unexpectedly. Review caught one heading inconsistency in builder.md (`## Phase 1 — Analyze` vs the expected `## Phase: analyze`) and tests caught one missing edge case (phase: analyze precedence over Scout Findings). Both resolved cleanly in one fix cycle.

**Missing from plan:** The plan skill should more actively offer the flow diagram template during planning. Also surfaced a gap: there is no Mermaid diagram template — only ASCII flow diagrams are currently supported.

## What Worked

- 3-phase analyze → scout-flow → act pattern landed cleanly across all 4 conversations
- scout-flow as a single canonical owner of parallel spawn logic eliminated duplication across 5 files
- NEEDS_CONTEXT contract normalization (pipe-separated format) produced consistent agent behavior
- Review caught the heading inconsistency before it became a runtime ambiguity
- Test suite (45 criteria) caught the missing precedence rule edge case that review missed

## What to Improve Next Time

- **Split multi-file conversations:** Conv 2 and Conv 4 each touched 3–4 files. Each file should be its own conversation — faster to verify, easier to rollback, lower cognitive load for the builder
- **Offer flow diagram template proactively:** The plan skill should prompt for a flow diagram when the feature involves a new calling convention or orchestration pattern (like this one)
- **Add Mermaid diagram template:** An ASCII-only constraint limits expressiveness for flows with branching. A `MERMAID_DIAGRAM.md` template alongside the existing ASCII `FLOW_DIAGRAM.md` would cover this gap

## Seed for Next Storm

> parallel-scout-standard introduced scout-flow as a shared orchestration sub-skill that standardizes the analyze → scout → act pattern. The key lesson: conversations that touch multiple files in the same category (skills, agents) should each be scoped to one file. The Mermaid diagram template gap is a concrete follow-up worth planning.
