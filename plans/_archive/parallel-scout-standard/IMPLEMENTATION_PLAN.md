# IMPLEMENTATION_PLAN — parallel-scout-standard

## Architecture notes

The feature is entirely within the `src/pathly_data/core/` directory — markdown files
that define Pathly's behavior. No runtime code, no tests, no migrations.

The key design principle: `scout-flow` is the single owner of the parallel spawn loop.
Skills call it; they do not re-implement it. Agent contracts describe their own
phase-split behavior and reference scout-flow.md as the canonical NEEDS_CONTEXT format source.

Layer order for edits:
1. Create scout-flow (defines the contract that skills will reference)
2. Update standalone skills to call scout-flow (consumers of the contract)
3. Update team-flow/plan (existing partial pattern, now standardized)
4. Update agent contracts (define agent-side behavior for phase: analyze and Scout Findings)

Each conversation leaves all referenced files internally consistent and cross-linked.

## Happy path

```
skill orchestrator
  └─► spawns agent with phase: analyze
        └─► agent returns NEEDS_CONTEXT block
  └─► calls scout-flow with block + ROLE + FEATURE
        └─► scout-flow spawns ≤4 scouts/quick/web in parallel
        └─► compresses findings into short summary
  └─► spawns agent with phase: [main] + ## Scout Findings
        └─► agent does its work with findings as authoritative context
```

---

## Conv 1 — Create scout-flow sub-skill   Conversation: 1

**Stories:** S-1
**Purpose:** Define the canonical sub-skill before anything references it.
**Depends on:** nothing
**Enables:** Conv 2 and Conv 3 can reference a real file

### Phase 1.1 — Write scout-flow.md

Create `src/pathly_data/core/skills/scout-flow.md` with:

- Header declaring it as an orchestrator-only sub-skill (not user-invokable)
- Input parameters section: NEEDS_CONTEXT, ROLE, FEATURE
- Canonical NEEDS_CONTEXT format block (the definition lives here):
  ```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
  - type: web   | query: <search query>
  ```
- Behavior: parse entries, spawn in parallel (max 4), compress, return summary
- Spawn mapping table: type → agent + ROLE injection
- Priority rule: scout > quick > web, then by order when > 4 entries
- Short-circuit rule: if NEEDS_CONTEXT is `none` or empty, return `none` immediately
- Terminal rule: sub-agents spawned by scout-flow cannot spawn further agents

**Verification:** `scout-flow.md` exists at the correct path and contains all required sections (manual read check).

---

## Conv 2 — Update standalone skills   Conversation: 2

**Stories:** S-2, S-3, S-4
**Purpose:** Standardize plan.md, build.md, and review.md to use the 3-phase pattern via scout-flow.
**Depends on:** Conv 1 (scout-flow.md exists)
**Enables:** standalone skills are consistent with team-flow

### Phase 2.1 — Update skills/plan.md

Replace the current inline scout/quick spawning logic (the "Planner Consultation Policy" and
"Research The Codebase" sections that individually spawn agents) with an explicit 3-phase structure:

- Phase 1: spawn planner with `phase: analyze`
- Phase 2: if NEEDS_CONTEXT != none, call scout-flow; else findings = none
- Phase 3: spawn planner with `phase: plan` + `## Scout Findings` injected

Do NOT touch the rigor logic, conversation splitting rules, or report format.

### Phase 2.2 — Update skills/build.md

The build skill already has a documented 2-phase builder pattern ("Context gathering — two-phase builder").
Replace the inline Phase 2 spawn loop with a call to scout-flow. Keep:
- The nano-task skip condition
- The continuation-conversation skip condition
- The conflicting findings protocol (spawn targeted scout / write DESIGN_QUESTIONS.md)

### Phase 2.3 — Update skills/review.md

The review skill has an inline scout spawn in "Pre-review context gathering".
Replace it with a 3-phase structure:
- Phase 1: spawn reviewer with `phase: analyze`
- Phase 2: if NEEDS_CONTEXT != none, call scout-flow
- Phase 3: spawn reviewer with final review prompt + `## Applicable Rules` injected

Keep all existing Step 1–Step 3 review logic and the report format unchanged.

**Verification:** All three skill files exist and each references `scout-flow` as the Phase 2 mechanism. Manual read of each file confirms no duplicate inline spawn loops remain.

---

## Conv 3 — Update team-flow/plan   Conversation: 3

**Stories:** S-5
**Purpose:** Replace the two inline Phase 2 scout loops in team-flow/plan.md with scout-flow calls.
**Depends on:** Conv 1 (scout-flow.md exists)
**Enables:** team-flow and standalone skills are fully consistent

### Phase 3.1 — Replace Storm Phase 2 inline loop

In `skills/team-flow/plan.md`, Stage 1 (Storm), Phase 2 currently reads:
> "Spawn all NEEDS_CONTEXT entries in parallel (max 4 total): type: quick → ... type: scout → ... type: web → ..."

Replace with:
> "Call scout-flow with: NEEDS_CONTEXT block from Phase 1, ROLE: architect, FEATURE: [feature name]. Use the returned summary as research findings for Phase 3."

### Phase 3.2 — Replace Plan Phase 2 inline loop

Same replacement for Stage 2 (Plan), Phase 2. The inline spawn loop is replaced with:
> "Call scout-flow with: NEEDS_CONTEXT block from Phase 1, ROLE: planner, FEATURE: [feature name]. Use the returned summary as scout findings for Phase 3."

### Phase 3.3 — Update Subagents table

Update the Subagents table at the top of team-flow/plan.md:
- Storm Phase 2 row: change "scout, quick, or web-researcher with ROLE: architect (parallel, max 4)" → "scout-flow (ROLE: architect)"
- Plan Phase 2 row: change "scout or quick with ROLE: planner (parallel, max 4)" → "scout-flow (ROLE: planner)"

**Verification:** `team-flow/plan.md` contains no inline `Spawn all NEEDS_CONTEXT entries in parallel` loops. The file references scout-flow in both stage Phase 2 sections. All other content (FSM transitions, rigor escalator, pause logic) is unchanged.

---

## Conv 4 — Update agent contracts   Conversation: 4

**Stories:** S-6
**Purpose:** Add phase: analyze behavior and Scout Findings protocol to each agent contract.
**Depends on:** Conv 1 (so agents can reference scout-flow.md as the canonical format source)
**Enables:** any adapter or skill can rely on agent contracts without guessing phase behavior

### Phase 4.1 — Update agents/planner.md

Add a `## Phase: analyze` section (or integrate into existing structure):
- When spawned with `phase: analyze`: output NEEDS_CONTEXT block only — no planning yet.
- NEEDS_CONTEXT format: reference scout-flow.md as the canonical definition.
- Cap at 4 entries. Output `none` if no research is needed.
- When `## Scout Findings` is present in the prompt (main phase): treat as authoritative context before writing stories/plans.

### Phase 4.2 — Update agents/builder.md

The builder already has a Phase 1 (Analyze) section. Normalize:
- The NEEDS_CONTEXT format to match the canonical pipe-separated format from scout-flow.md.
  Current format uses indented YAML style; canonical format uses `type: X | scope: Y | question: Z`.
- Add a reference to scout-flow.md as the canonical format source.
- Keep all other existing behavior (blocking rules, artifact archiving, reporting).

### Phase 4.3 — Update agents/reviewer.md

Add a `## Phase: analyze` section:
- When spawned with `phase: analyze`: read the diff/files stated in the prompt, then output NEEDS_CONTEXT block only — no reviewing yet.
- NEEDS_CONTEXT format: reference scout-flow.md.
- When `## Applicable Rules` or `## Scout Findings` is present: treat as authoritative architectural context before checking violations.

### Phase 4.4 — Update agents/architect.md

Add a `## Phase: analyze` section:
- When spawned with `phase: analyze`: read feature description and any seed files, then output NEEDS_CONTEXT block only — no storming or designing yet.
- NEEDS_CONTEXT format: reference scout-flow.md.
- When `## Research Findings` or `## Scout Findings` is present: treat as authoritative before designing.

**Verification:** Each of the four agent files contains a `phase: analyze` section and a `## Scout Findings` (or equivalent) injection note. Each references scout-flow.md for the NEEDS_CONTEXT format. Manual read of each file confirms backward compatibility: no `phase:` prefix = existing behavior unchanged.
