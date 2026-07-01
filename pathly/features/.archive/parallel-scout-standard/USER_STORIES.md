# USER_STORIES — parallel-scout-standard

## S-1 — scout-flow sub-skill exists and is callable

**As** a skill orchestrator (plan, build, review, team-flow/plan),
**I want** a single reusable `scout-flow` sub-skill that accepts a NEEDS_CONTEXT block and parent role,
**so that** I don't duplicate parallel scout logic in every skill file.

**Delivered by:** Conv 1

### Acceptance criteria

- `src/pathly_data/core/skills/scout-flow.md` exists.
- The file defines the three accepted input parameters: `NEEDS_CONTEXT`, `ROLE`, `FEATURE`.
- The canonical NEEDS_CONTEXT format (type: scout | quick | web) is documented inside the file.
- The file specifies the max-4 parallel spawn rule.
- The file specifies the priority order when more than 4 entries: scout > quick > web, then by order.
- The file specifies that when NEEDS_CONTEXT is `none` or empty, return `none` immediately with no spawns.
- The file states scout-flow is orchestrator-only — not user-invokable, not listed in user menus.
- The file states sub-agents spawned by scout-flow are terminal.

### Edge cases

- NEEDS_CONTEXT has exactly 4 entries: all 4 are spawned in parallel, no truncation.
- NEEDS_CONTEXT has 5 entries: the 5th is dropped; the file must document which 4 survive (scout first, then quick, then web, then order).
- NEEDS_CONTEXT is the literal string `none`: skill returns `none` immediately.
- All entries are `type: web` and there are 3: all 3 spawned, each with parent ROLE injected.

---

## S-2 — standalone plan skill uses 3-phase structure via scout-flow

**As** a planner running the standalone `plan` skill,
**I want** the skill to run analyze → scout-flow → plan in sequence,
**so that** the planner gets relevant codebase context before writing stories and phases.

**Delivered by:** Conv 2

### Acceptance criteria

- `skills/plan.md` spawns planner with `phase: analyze` first.
- If the returned NEEDS_CONTEXT is not `none`, the skill calls `scout-flow` with that block.
- The planner's final spawn includes a `## Scout Findings` section (with the compressed summary, or `none`).
- Any pre-existing inline scout spawning logic that duplicates this is removed.

### Edge cases

- Planner returns `none` in analyze phase: scout-flow is not called; plan phase proceeds with `## Scout Findings\nnone`.
- Scout-flow is called but all scouts return empty findings: the summary is `none` and plan phase proceeds normally.

---

## S-3 — standalone build skill uses 3-phase structure via scout-flow

**As** a builder running the standalone `build` skill,
**I want** the skill to run analyze → scout-flow → implement in sequence,
**so that** the builder gets relevant context before touching any files.

**Delivered by:** Conv 2

### Acceptance criteria

- `skills/build.md` spawns builder with `phase: analyze` before implementation.
- If NEEDS_CONTEXT is not `none`, the skill calls `scout-flow`.
- The builder's implement spawn includes a `## Scout Findings` section.
- The existing nano-task / continuation skip condition is preserved (Phase 1 can be skipped for trivial work).

### Edge cases

- Nano task: skill skips Phase 1 and spawns builder directly with `## Scout Findings\nnone`.
- Continuation conversation where prior findings are still valid: skill skips Phase 1 per existing skip rule.

---

## S-4 — standalone review skill uses 3-phase structure via scout-flow

**As** a reviewer running the standalone `review` skill,
**I want** the skill to run analyze → scout-flow → review in sequence,
**so that** the reviewer receives architectural context before checking violations.

**Delivered by:** Conv 2

### Acceptance criteria

- `skills/review.md` spawns reviewer with `phase: analyze` first.
- If NEEDS_CONTEXT is not `none`, the skill calls `scout-flow`.
- The reviewer's final spawn includes a `## Scout Findings` / `## Applicable Rules` section.
- The existing inline scout spawn (current `Pre-review context gathering` section) is replaced, not kept alongside the new 3-phase structure.

### Edge cases

- Reviewer returns `none` in analyze: no scout-flow call; review proceeds with `## Applicable Rules\nnone`.

---

## S-5 — team-flow/plan uses scout-flow for both storm and plan phases

**As** the team-flow orchestrator,
**I want** both the storm phase (architect) and the plan phase (planner) in `team-flow/plan.md`
to delegate their parallel scout work to scout-flow,
**so that** the inline spawn-loop logic is not duplicated across team-flow and standalone skills.

**Delivered by:** Conv 3

### Acceptance criteria

- `skills/team-flow/plan.md` references `scout-flow` as the mechanism for Phase 2 of both Stage 1 (storm) and Stage 2 (plan).
- The inline `Spawn all NEEDS_CONTEXT entries in parallel` loop is removed from both stages and replaced with a `call scout-flow` instruction.
- The Subagents table in team-flow/plan.md is updated to list `scout-flow` instead of individual scout/quick/web spawns for Phase 2.
- All other existing behavior (FSM transitions, pause/continue logic, rigor escalator) is unchanged.

### Edge cases

- NEEDS_CONTEXT from architect is `none`: scout-flow is not called; storm phase proceeds with findings = none.
- NEEDS_CONTEXT from planner is `none`: same skip behavior applies.

---

## S-6 — agent contracts document phase: analyze and Scout Findings injection

**As** a skill that spawns agents in multi-phase mode,
**I want** each agent contract (planner, builder, reviewer, architect) to define what to do
when invoked with `phase: analyze` and what to do with `## Scout Findings` when injected,
**so that** any adapter or skill can rely on these contracts without guessing.

**Delivered by:** Conv 4

### Acceptance criteria

- `agents/planner.md` has a `phase: analyze` section: output NEEDS_CONTEXT block only, no planning.
- `agents/planner.md` has a note that when `## Scout Findings` is present in the prompt, treat it as authoritative before writing stories.
- `agents/builder.md` NEEDS_CONTEXT format matches the canonical format in scout-flow.md (type: scout | quick | web with pipe-separated fields; the existing format uses a different layout — normalize it).
- `agents/reviewer.md` has a `phase: analyze` section: output NEEDS_CONTEXT block only, no reviewing.
- `agents/reviewer.md` has a note that `## Scout Findings` / `## Applicable Rules` is treated as authoritative context.
- `agents/architect.md` has a `phase: analyze` section: output NEEDS_CONTEXT block only, no storming/designing.
- `agents/architect.md` has a note that `## Scout Findings` / `## Research Findings` is treated as authoritative.
- References to scout-flow.md as the canonical source of the NEEDS_CONTEXT format are present in each agent contract.

### Edge cases

- Agent receives both `phase: analyze` and a `## Scout Findings` block: `phase: analyze` takes precedence — output NEEDS_CONTEXT only, ignore the findings block.
- Agent is invoked without any `phase:` prefix: existing behavior is unchanged (backward-compatible).
