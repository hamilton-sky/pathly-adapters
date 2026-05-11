# mermaid-template — Conversation Prompts

## Conversation 1 — Create Mermaid diagram template

Read plans/mermaid-template/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Before making any edits, verify the following paths exist in the live repo:
- `src/pathly_data/core/templates/plan/FLOW_DIAGRAM.template.md` (reference for structure)

**Task:** Create `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md`.

**File:** `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` — CREATE
**Done when:** The file exists, contains a `flowchart TD` block in a fenced ` ```mermaid ``` ` code block, a fallback/error flow block, and a component legend table — all using `[bracket placeholder]` notation.

**Structure to follow:**
- Mirror `FLOW_DIAGRAM.template.md` section-for-section (happy path, fallback, legend)
- Use `flowchart TD` as the diagram type
- All placeholders in `[bracket notation]`
- Keep it short — a skeleton, not a worked example

Do NOT touch `plan.md` or any other file yet.

**Verify:** Confirm the file exists at the stated path and contains a `flowchart` keyword.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.

---

## Conversation 2 — Wire template into plan.md

Read plans/mermaid-template/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Before making any edits, verify the following paths exist in the live repo:
- `src/pathly_data/core/templates/plan/MERMAID_DIAGRAM.template.md` (must exist from Conv 1)
- `src/pathly_data/core/skills/plan.md` (file to modify)

**Task:** Update Section 4i of `src/pathly_data/core/skills/plan.md` to offer Mermaid as a diagram option.

**File:** `src/pathly_data/core/skills/plan.md` — MODIFY: Section 4i only
**Done when:** Section 4i references `MERMAID_DIAGRAM.template.md` by name and tells the planner to offer Mermaid for orchestration-heavy features (new calling conventions, sub-skills, orchestration patterns).

**What to change:**
- Locate `### 4i. FLOW_DIAGRAM.md` in plan.md
- Keep the existing ASCII content
- Add: for orchestration-heavy features, read `core/templates/plan/MERMAID_DIAGRAM.template.md` and offer Mermaid as the diagram format
- ASCII remains the default; Mermaid is opt-in

Do NOT touch any other section of plan.md.

**Verify:** `grep -n "MERMAID_DIAGRAM" src/pathly_data/core/skills/plan.md` — should return at least one match in Section 4i.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
