# REVIEW_FAILURES — parallel-scout-standard Conv 4

## Violations

- [IMPL] `src/pathly_data/core/agents/builder.md:21` — heading rule — Section heading is `## Phase 1 — Analyze (when spawned with \`phase: analyze\`)` instead of `## Phase: analyze` used by all other agent contracts (planner, reviewer, architect). Must use consistent heading.

- [IMPL] `src/pathly_data/core/agents/builder.md:40-44` — analyze section completeness — The Scout Findings authoritative note ("treat as authoritative context before touching any file") lives in `## Phase 2 — Implement`, not inside the analyze section. The `## Phase: analyze` section must contain the authoritative note for when `## Scout Findings` is injected into the prompt, consistent with planner.md, reviewer.md, and architect.md.

## Warnings (non-blocking — fix if possible)

- `src/pathly_data/core/agents/builder.md:28-33` — The NEEDS_CONTEXT format is duplicated inline (code block) in addition to the `scout-flow.md` reference. Other three agent contracts reference scout-flow.md only. Creates maintenance risk if canonical format changes.

## Fix instructions

In `src/pathly_data/core/agents/builder.md`:

1. Rename `## Phase 1 — Analyze (when spawned with \`phase: analyze\`)` to `## Phase: analyze`.
2. Add an authoritative note inside the `## Phase: analyze` section:
   ```
   When `## Scout Findings` is present in the prompt: treat it as authoritative codebase context before touching any file. Do not re-research what the findings already cover.
   ```
3. (Optional but recommended) Remove the inline NEEDS_CONTEXT format code block and keep only the scout-flow.md reference line.
4. Rename the implement section `## Phase 2 — Implement (normal spawn, or \`phase: implement\`)` — leave it as-is or adjust as needed, but do NOT remove the existing authoritative note from Phase 2 if removing it from there.

Do not change any other file. Delete this file when all violations are fixed.
