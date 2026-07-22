# Exploration — unified-cli-composition

## Question

DESIGN.md declares P0 as "BUILT and merged to master" (compose endpoint, skillCompose.ts,
fragments, transform skills, file-based capture for Summary/Analyze/Split, pollForFile ERROR
contract, no_defaults opt-out). Is P0 fully implemented as designed, and what concrete
gaps remain before P1 work (board-start-context, task-dag-post, Decompose conversion,
drain-dag board-I/O, profiles refactor) can begin?

## Scope

Verify these P0 claims against actual code on disk:

1. `POST /skills/compose` endpoint exists in `blueprints/skills/editor_render.py`,
   calls `compose_skill` + `load_effective_manifest` + `_inject_prompt_vars` + `_strip_leading_frontmatter`,
   returns `{ prompt, skill, composed }`, falls back with `composed: false` for unknown skills.
2. `services/skillCompose.ts` exists with `composeClientSkill(skill, adapter, transform)`,
   returns `string | null`, wraps in try/catch, logs warning on failure.
3. `summarizeArtifact.ts` calls `composeClientSkill` and uses file-based capture (`.summary` poll),
   NOT the old `result.text` stdout-tail path.
4. `useEditorAgentActions.ts` calls `composeClientSkill` for Analyze and Split, falls back to bare builders on `null`.
5. `pollForFile` detects `ERROR:` prefix → pill-error + error toast (not silent success).
6. Fragment files exist: `fragments/client-file-output.md` and `fragments/artifact-transform.md`.
7. Skill bodies exist: `core/skills/development/{summarize,analyze,split}.md`.
8. `composition.yaml` entries for the three transform skills each declare `[client-file-output, artifact-transform]` and `no_defaults: true`.
9. `.summary` files are `.gitignore`d and deleted after read.

Also note any deviations from the DESIGN.md contract that would affect P1 planning.

## Out of scope

- P1/P2/P3 fragments (board-start-context, task-dag-post, profiles refactor, drain-dag loop body).
- Existing FSM/server path (evaluate, board-run, team-execute) — they use AGENT_DONE, not file capture.
- UX / ActionPill conformance beyond what the pollForFile ERROR contract requires.

## Success criterion

A list of: (a) which P0 acceptance criteria are fully met, (b) which are partially met or
deviate from the design, and (c) what must still be done before P1 can start — with specific
file:line references for each finding.
