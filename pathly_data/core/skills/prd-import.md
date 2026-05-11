# prd-import

This is the canonical, tool-agnostic Pathly behavior for the prd-import workflow.
This skill handles all PRD formats — generic hand-written PRDs, AI-generated PRDs,
and BMAD-structured PRDs. The `bmad-import` route is an alias; both resolve here.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes:** Any PRD file — generic, AI-generated, or BMAD-structured (path provided as second argument)
**Produces:** `plans/$FEATURE/` — 4 files in lite, all 8 plan files in standard/strict, pre-populated from the PRD
**Consumed by:** `build` skill reads `CONVERSATION_PROMPTS.md` and `PROGRESS.md`

---

## Step 0: Parse Arguments

Split `$ARGUMENTS` on the first space:
- `FEATURE` = first token (the feature name, e.g., `hotel-search`)
- `PRD_PATH` = remaining tokens (the file path, e.g., `docs/hotel-search-prd.md`)
- If the final token is `lite`, `standard`, or `strict`, remove it from `PRD_PATH` and set `rigor` accordingly.
- Default: `rigor = standard`

If either is missing, stop and tell the user:
```
Route: `prd-import <feature-name> <path/to/PRD.md>`
Example route: `prd-import hotel-search docs/hotel-search-prd.md`
```

Check that `PRD_PATH` exists. If not, stop and report the missing file.
Check that `plans/$FEATURE/` does NOT already exist. If it does, stop and ask the user whether to overwrite.

---

## Step 1: Read the PRD

Read the full PRD file at `PRD_PATH`.

Extract these sections (they may use different headings — use best-match):
- **Feature name / title**
- **User Stories** — each story with: title, persona, goal, benefit
- **Acceptance Criteria** — per story (list items, checkboxes, or numbered)
- **Edge Cases** — per story or global
- **Out of Scope** — explicit exclusions
- **Tech stack / constraints** — any mentioned technologies, URLs, environments
- **Overview / context** — problem statement or background

If the PRD uses different section names (e.g., "Non-functional requirements", "Constraints"), map them to the closest category above.

---

## Step 2: Read Project Conventions

1. Read the project's guidance files — layer structure, run commands, project architecture
2. Read project rule files if present — architectural contracts, dependency rules, naming conventions
3. Identify the project's layer structure from the available guidance (e.g., what layers exist, what belongs where)
4. Find similar existing components in the codebase — use as reference patterns for naming and structure

---

## Step 3: Plan the Conversation Split

Determine how many conversations are needed (max 4 per folder):

**Rules for splitting:**
- **Conversation 1** always covers: the foundation layer — data models, base classes, core interfaces
- **Conversation 2** covers: service/integration layer — logic that uses the foundation
- **Conversation 3** (if needed): additional stories that depend on Conv 1 foundation
- **Conversation 4** (if needed): integration tests, entry point wiring, or end-to-end flows

If complexity is LOW (1-2 stories, ≤4 ACs): 2 conversations
If complexity is MEDIUM (3-4 stories, 5-8 ACs): 3 conversations
If complexity is HIGH (5+ stories or 9+ ACs): consider splitting into two plan folders: `plans/$FEATURE-part-1/` and `plans/$FEATURE-part-2/`

---

## Step 4: Translate ACs to Verify Commands

This is the core translation step. For each acceptance criterion, determine which layer it tests and generate the appropriate verify command:

**General approach — use the project's own test/run conventions from project guidance:**

| AC type | Verify method |
|---|---|
| Structure exists (class, file, interface) | `grep` or file existence check |
| Logic executes correctly | unit test or integration test command from project guidance |
| End-to-end behavior | full run command from project guidance |
| Error/edge state handled | targeted test for the edge case |

**Verify command format:**
```
Verify:
  <command>
  # expected: <what success looks like>
```

Always include at least one verify command per conversation that proves the deliverable is runnable, not just syntactically correct.

---

## Step 5: Map Edge Cases to Conversations

Each edge case from the PRD becomes either:

1. **A test scenario** — if it requires exercising a failure path or boundary condition
   → Add to the conversation that implements the relevant component

2. **A Do NOT item** — if it's a scope boundary ("do not implement payment flow")
   → Add to every conversation's `Do NOT` list

3. **A model/method** — if it's a state the component must handle (e.g., "returns empty list when no results")
   → Add to the foundation conversation scope

---

## Step 6: Generate Plan Files

Create `plans/$FEATURE/`.

If `rigor = lite`, write only:
- USER_STORIES.md
- IMPLEMENTATION_PLAN.md
- PROGRESS.md
- CONVERSATION_PROMPTS.md

Merge happy flow, edge cases, architecture notes, and flow notes into those four files.

If `rigor = standard` or `strict`, write all 8 files.

If `rigor = strict`, add explicit risk, rollback, verification mapping, and approval notes.

### FILE 1: USER_STORIES.md
Read `core/templates/plan/USER_STORIES.template.md` for structure.

### FILE 2: IMPLEMENTATION_PLAN.md
Read `core/templates/plan/IMPLEMENTATION_PLAN.template.md` for structure.

### FILE 3: PROGRESS.md
Read `core/templates/plan/PROGRESS.template.md` for structure.

### FILE 4: CONVERSATION_PROMPTS.md
Read `core/templates/plan/CONVERSATION_PROMPTS.template.md` for structure.

Each conversation prompt must be self-contained, scoped to specific files and layers, include the relevant architectural boundary rules from project guidance, Do NOT list, verify command, and end with:
`After done, update plans/$FEATURE/PROGRESS.md phase X to DONE.`

### FILE 5: HAPPY_FLOW.md
Standard/strict only. Skip in lite.
Read `core/templates/plan/HAPPY_FLOW.template.md` for structure.

### FILE 6: EDGE_CASES.md
Standard/strict only. Skip in lite.
Read `core/templates/plan/EDGE_CASES.template.md` for structure.

### FILE 7: ARCHITECTURE_PROPOSAL.md
Standard/strict only. Skip in lite; merge short architecture notes into IMPLEMENTATION_PLAN.md.
Read `core/templates/plan/ARCHITECTURE_PROPOSAL.template.md` for structure.

### FILE 8: FLOW_DIAGRAM.md
Standard/strict only. Skip in lite unless the flow is unclear without a diagram.
Read `core/templates/plan/FLOW_DIAGRAM.template.md` for structure.
ASCII only. Max ~70 chars wide.

---

## Step 7: Verify Output

After writing files, confirm the selected rigor's required files exist in `plans/$FEATURE/`.

Then report:
```
PRD import complete. Created plans/$FEATURE/.

Rigor: [lite / standard / strict]

Stories imported: [count] ([story IDs])
Conversations planned: [count]
Edge case workflows: [count]

Next step: Review the plan, then run:
  continue $FEATURE        <- implement Conversation 1
  team-flow $FEATURE       <- run the full pipeline
```

If a section was missing from the PRD, note it and leave the relevant section minimal rather than inventing content.
