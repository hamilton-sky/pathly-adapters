# CONVERSATION_PROMPTS — parallel-scout-standard

---

## Conversation 1 — Create scout-flow sub-skill

**Stories delivered:** S-1
**Phases:** 1.1

```
Read plans/parallel-scout-standard/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Create a new file: src/pathly_data/core/skills/scout-flow.md

This is an orchestrator-only sub-skill — not user-invokable, not listed in any user-facing menu.

The file must contain all of the following:

1. A header section stating scout-flow is called by other skills, not by users directly.

2. An "Input parameters" section listing:
   - NEEDS_CONTEXT (the block of research entries)
   - ROLE (parent role name, e.g. "planner", "builder", "architect", "reviewer")
   - FEATURE (feature name for context injection into spawned agents)

3. The canonical NEEDS_CONTEXT format (this file is the single source of truth for this format):
   - type: scout | scope: <files or directories> | question: <specific question>
   - type: quick | question: <specific question>
   - type: web   | query: <search query>

4. A "Behavior" section:
   a. If NEEDS_CONTEXT is `none` or empty: return `none` immediately, no spawns.
   b. Otherwise: parse all entries and spawn in parallel (max 4 total).
   c. Spawn mapping:
      - type: scout  → spawn `scout` agent with ROLE: <parent role> — read-only research, scope, question
      - type: quick  → spawn `quick` agent with ROLE: <parent role>, question
      - type: web    → spawn `web-researcher` with ROLE: <parent role>, query
   d. Each spawned agent receives the parent ROLE as context so it knows what's relevant.
   e. Compress all findings into one short summary (signal-to-noise: relevant facts only, no raw dumps).
   f. Return the compressed summary to the calling skill.

5. A "Priority rule" section:
   When there are more than 4 NEEDS_CONTEXT entries, keep only 4.
   Priority order: scout > quick > web, then by order of appearance for ties.

6. A "Rules" section:
   - Max 4 parallel spawns.
   - scout-flow is orchestrator-only — not user-invokable.
   - Sub-agents spawned by scout-flow are terminal (cannot spawn further agents).

Do NOT touch any other files in this conversation.

Verification: confirm the file exists at src/pathly_data/core/skills/scout-flow.md and manually verify
all six sections above are present. If any is missing, add it before marking done.

If verification fails and the fix requires out-of-scope changes, stop and report.

Update plans/parallel-scout-standard/PROGRESS.md: mark Conv 1 and Phase 1.1 as DONE.
```

---

## Conversation 2 — Update standalone skills

**Stories delivered:** S-2, S-3, S-4
**Phases:** 2.1, 2.2, 2.3

```
Read plans/parallel-scout-standard/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

This conversation updates three standalone skills to use scout-flow for their Phase 2 context gathering.
scout-flow.md was created in Conv 1 — read it before editing to understand the calling convention.

Do NOT touch team-flow/plan.md or any agent contracts in this conversation.

--- skills/plan.md ---

The current file has inline logic to spawn quick/scout individually (Planner Consultation Policy,
Research The Codebase). Replace this with an explicit 3-phase structure:

Phase 1 — Analyze:
  Spawn planner with phase: analyze. Pass the feature name and rigor.
  Parse the returned NEEDS_CONTEXT block.

Phase 2 — Scout:
  If NEEDS_CONTEXT != none: call scout-flow with the block, ROLE: planner, FEATURE: [feature name].
  If NEEDS_CONTEXT == none: findings = none. Skip scout-flow.

Phase 3 — Plan:
  Spawn planner with phase: plan. Inject:
    ## Scout Findings
    [compressed summary from Phase 2, or "none" if skipped]
  Plus all the existing context (rigor, STORM_SEED if exists, PO_NOTES if exists).

Keep intact: rigor logic (Step 0), lessons (Step 1), interview (Step 2), plan file creation
(Steps 3-6), conversation splitting rules, team-safe prompt rules, and the report format.
Remove: the Planner Consultation Policy section and the Research The Codebase section
(their purpose is now covered by the analyze phase and scout-flow).

--- skills/build.md ---

The file already has a "Context gathering — two-phase builder" section. Update it:
- Rename the section to reflect 3-phase structure.
- Keep Phase 1 (Analyze) and Phase 3 (Implement) exactly as they are.
- Replace Phase 2's inline spawn loop with: "Call scout-flow with the NEEDS_CONTEXT block,
  ROLE: builder, FEATURE: [plan folder name]. Use the returned summary as Scout Findings."
- Keep the nano-task skip condition, continuation skip condition, and conflicting-findings protocol unchanged.

--- skills/review.md ---

The file currently has an inline "Pre-review context gathering" section that spawns a scout directly.
Replace it with a 3-phase structure:

Phase 1 — Analyze:
  Spawn reviewer with phase: analyze. Pass the diff target ($ARGUMENTS).
  Parse the returned NEEDS_CONTEXT block.

Phase 2 — Scout:
  If NEEDS_CONTEXT != none: call scout-flow with the block, ROLE: reviewer, FEATURE: [changed area].
  If NEEDS_CONTEXT == none: findings = none.

Phase 3 — Review:
  Spawn reviewer with the full review prompt. Inject:
    ## Applicable Rules
    [compressed summary from Phase 2, or "none" if skipped]
  Keep Steps 1-3 and the report format inside the reviewer's spawn prompt.

Remove: the old "Pre-review context gathering" inline scout spawn block.

Verification: read all three updated files and confirm:
  1. Each references scout-flow as the Phase 2 mechanism.
  2. No inline "Spawn all NEEDS_CONTEXT entries in parallel" loop remains in any of the three files.
  3. The existing non-scout logic in each file is untouched.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.

Update plans/parallel-scout-standard/PROGRESS.md: mark Conv 2 and Phases 2.1, 2.2, 2.3 as DONE.
```

---

## Conversation 3 — Update team-flow/plan

**Stories delivered:** S-5
**Phases:** 3.1, 3.2, 3.3

```
Read plans/parallel-scout-standard/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

This conversation updates src/pathly_data/core/skills/team-flow/plan.md only.
Do NOT touch any other files.

Read the current team-flow/plan.md carefully before editing.

The file has two inline Phase 2 scout loops — one in Stage 1 (Storm) and one in Stage 2 (Plan).
Both read:
  "Spawn all NEEDS_CONTEXT entries in parallel (max 4 total): type: quick → ... type: scout → ... type: web → ..."

Replace each loop with a call to scout-flow:

Stage 1 — Storm, Phase 2:
  Replace the inline loop with:
  "Call scout-flow with: NEEDS_CONTEXT block from Phase 1, ROLE: architect, FEATURE: [feature name].
   Use the returned compressed summary as Research Findings for Phase 3."

Stage 2 — Plan, Phase 2:
  Replace the inline loop with:
  "Call scout-flow with: NEEDS_CONTEXT block from Phase 1, ROLE: planner, FEATURE: [feature name].
   Use the returned compressed summary as Scout Findings for Phase 3."

Also update the Subagents table at the top of the file:
  Storm Phase 2 row: change agent column to "scout-flow (ROLE: architect)"
  Plan Phase 2 row: change agent column to "scout-flow (ROLE: planner)"

Keep completely unchanged: FSM operations, pause/continue logic, rigor escalator,
Stage 1 Phases 1 and 3, Stage 2 Phases 1 and 3, and the transition logic at the end.

Verification:
  1. Grep team-flow/plan.md for "Spawn all NEEDS_CONTEXT entries in parallel" — must return no matches.
  2. Grep team-flow/plan.md for "scout-flow" — must appear in both Stage 1 Phase 2 and Stage 2 Phase 2.
  3. Read the Subagents table — both Phase 2 rows must reference scout-flow.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.

Update plans/parallel-scout-standard/PROGRESS.md: mark Conv 3 and Phases 3.1, 3.2, 3.3 as DONE.
```

---

## Conversation 4 — Update agent contracts

**Stories delivered:** S-6
**Phases:** 4.1, 4.2, 4.3, 4.4

```
Read plans/parallel-scout-standard/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

This conversation updates four agent contract files. Read each file before editing.
Read src/pathly_data/core/skills/scout-flow.md to get the canonical NEEDS_CONTEXT format
before touching any agent file.

Do NOT touch any skill files in this conversation.

--- agents/planner.md ---

Add a section titled "## Phase: analyze" (insert it after the "Information gathering" section):

  When spawned with `phase: analyze`:
  - Read the feature name, rigor, and any seed files named in the prompt.
  - Output a `## NEEDS_CONTEXT` block only — do not write stories or plan files yet.
  - NEEDS_CONTEXT format: see scout-flow.md (canonical definition).
  - Cap at 4 entries. Output `none` if no research is needed.

Add a note (can be inside the main phase section or as a sub-section):
  When `## Scout Findings` is present in the prompt:
  - Treat it as authoritative codebase context before writing any plan files.
  - Do not re-research what the findings already cover.

Preserve all existing content exactly.

--- agents/builder.md ---

The file already has "## Phase 1 — Analyze (when spawned with phase: analyze)".
Update only the NEEDS_CONTEXT format block inside that section:

Current format (indented YAML style):
  - type: quick | scout
    scope: [...]
    question: [...]
    reason: [...]

Normalize to the canonical pipe-separated format from scout-flow.md:
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
  - type: web   | query: <search query>

Also add: "NEEDS_CONTEXT format: see scout-flow.md (canonical definition)."
Keep the type guidance (quick vs scout), cap at 4, and `none` output rule.
Remove the `reason` field from the format (it is not part of the canonical format).
Keep all other content in the file exactly as-is.

--- agents/reviewer.md ---

Add a section titled "## Phase: analyze" (insert it before or after "Information gathering"):

  When spawned with `phase: analyze`:
  - Read the diff target or file paths named in the prompt.
  - Output a `## NEEDS_CONTEXT` block only — do not check for violations yet.
  - NEEDS_CONTEXT format: see scout-flow.md (canonical definition).
  - Cap at 4 entries. Output `none` if no research is needed.

Add a note:
  When `## Applicable Rules` or `## Scout Findings` is present in the prompt:
  - Treat it as authoritative architectural context before checking violations.
  - Do not re-spawn scouts for information already covered.

Preserve all existing content exactly.

--- agents/architect.md ---

Add a section titled "## Phase: analyze" (insert it before "What to explore per topic"):

  When spawned with `phase: analyze`:
  - Read the feature description and any seed files named in the prompt.
  - Output a `## NEEDS_CONTEXT` block only — do not storm or design yet.
  - NEEDS_CONTEXT format: see scout-flow.md (canonical definition).
  - Cap at 4 entries. Output `none` if no research is needed.

Add a note:
  When `## Research Findings` or `## Scout Findings` is present in the prompt:
  - Treat it as authoritative before designing. Do not re-research covered ground.

Preserve all existing content exactly.

Verification:
  For each of the four files, confirm:
  1. A `phase: analyze` section exists describing the NEEDS_CONTEXT-only output.
  2. A reference to scout-flow.md as the canonical format source exists.
  3. A note about treating the injected findings section as authoritative exists.
  4. All pre-existing content is intact (spot-check 2-3 sections per file).

  For builder.md specifically: confirm the NEEDS_CONTEXT format block uses pipe-separated
  style and does not include the `reason` field.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.

Update plans/parallel-scout-standard/PROGRESS.md: mark Conv 4 and Phases 4.1, 4.2, 4.3, 4.4 as DONE.
If all conversations are now DONE, also change Status to COMPLETE.
```
