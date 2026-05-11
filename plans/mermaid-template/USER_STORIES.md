# mermaid-template — User Stories

## S1.1 — Mermaid diagram template exists

**As a** planner,
**I want** a `MERMAID_DIAGRAM.template.md` file in `core/templates/plan/`,
**so that** I can use it when creating flow diagrams for features that need a Mermaid-format diagram instead of ASCII.

**Acceptance criteria:**
- `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` exists
- Template uses valid Mermaid `flowchart TD` syntax
- Template mirrors the structure of `FLOW_DIAGRAM.template.md` (happy path + fallback + legend)
- Placeholder sections use `[bracket notation]` consistent with other templates

---

## S1.2 — plan.md offers Mermaid as diagram option

**As a** planner agent reading `plan.md`,
**I want** Section 4i to tell me when to offer a Mermaid diagram,
**so that** I present it as an option alongside ASCII for orchestration-heavy features.

**Acceptance criteria:**
- Section 4i in `plan.md` references `MERMAID_DIAGRAM.template.md` by name
- Section 4i distinguishes when to use ASCII vs Mermaid (e.g., orchestration-heavy → offer Mermaid)
- The update is a modification to the existing Section 4i block, not an addition of a new section
- No other sections of `plan.md` are changed
