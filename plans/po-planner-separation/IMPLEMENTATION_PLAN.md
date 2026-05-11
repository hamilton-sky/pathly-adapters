# Implementation Plan — po-planner-separation

## Overview

Two focused conversations update four agent/skill markdown files. Conversation 1
handles the PO agent and the team-flow plan pipeline. Conversation 2 handles the
planner and tester agents. Each conversation leaves all four files runnable as
a coherent system.

## Pre-flight (before Conversation 1)

Read each target file end-to-end and note any existing section headings that
overlap with the planned additions. Record findings as a known baseline before
any edits begin. This prevents attributing pre-existing inconsistencies to this
feature.

Target files:
- `src/pathly_data/core/agents/po.md`
- `src/pathly_data/core/skills/team-flow/plan.md`
- `src/pathly_data/core/agents/planner.md`
- `src/pathly_data/core/agents/tester.md`

---

## Conversation 1 — PO agent + team-flow plan pipeline

**Stories fulfilled:** 1, 2

**Goal:** By the end of this conversation, `po.md` documents three activation
modes (rich STORM_SEED.md / thin or absent / autoFlow), and `plan.md` Stage 2
opens with a PO Phase that gates on `PO_NOTES.md` presence before invoking the
planner. All existing behavior in both files is preserved verbatim.

### Phase 1 — Pre-flight read

Read `src/pathly_data/core/agents/po.md` and
`src/pathly_data/core/skills/team-flow/plan.md` in full. Note:
- Existing section names in `po.md` (especially "Activation" and "Exit").
- The exact heading and text of Stage 2, Phase 1 — Analyze in `plan.md`.

Record any pre-existing overlaps with the planned additions before writing
anything.

**Leaves files:** unchanged.

### Phase 2 — Update po.md (Story 1)

Make three targeted edits to `src/pathly_data/core/agents/po.md`:

1. **Expand the Activation section** — After the existing activation logic
   (which reads a PRD), add a new subsection titled "When activated from
   team-flow/plan (not standalone /po skill)". It must document:
   - How to check for `plans/<feature>/STORM_SEED.md`.
   - Rich STORM_SEED.md path: infer stories, write draft `PO_NOTES.md`, pause
     once with exactly this prompt: "Here are the stories I derived — correct
     anything or say 'go'."
   - Thin or absent STORM_SEED.md path: enter full interactive mode — one
     question at a time until `stop notes`.
   - autoFlow path: write best-guess `PO_NOTES.md` without pausing; unresolved
     items written as `OPEN: <item>` entries in the `## Open Questions` section.

2. **Add fallback table** — Immediately after the new subsection, insert a
   three-row table with columns: Condition | Mode | Pauses?. Rows:
   - Rich STORM_SEED.md | Confirmation pass | Yes — once
   - Thin or absent STORM_SEED.md | Full interactive | Yes — per question
   - autoFlow active | Best-guess write | No

3. **Add edge case note** — Below the fallback table, add a note: "If
   STORM_SEED.md exists but contains only headings and no body text, treat it
   as thin. If autoFlow is active alongside a rich STORM_SEED.md, autoFlow
   wins — no pause. The standalone /po skill does not trigger this logic."

Do not alter any existing section content outside the Activation section.

Acceptance check (content facts only — no format rules):
- `po.md` contains a subsection describing the three activation cases.
- The fallback table is present with three rows.
- The word "autoFlow" appears in `po.md`.
- The phrase `OPEN:` appears in `po.md` in the context of unresolved items.

**Leaves files:** `po.md` updated; all other files unchanged.

### Phase 3 — Update plan.md Stage 2 (Story 2)

Make two targeted edits to `src/pathly_data/core/skills/team-flow/plan.md`:

1. **Insert PO Phase before Stage 2 Phase 1** — Add a new "PO Phase" section
   as the first step of Stage 2, before "Phase 1 — Analyze". It must specify:
   - Check whether `plans/<feature>/PO_NOTES.md` exists. If yes: skip PO Phase
     entirely, proceed to Phase 1 — Analyze.
   - If not: check STORM_SEED.md richness. Spawn `po` in confirmation-pass mode
     if rich, full-interactive mode if thin or absent.
   - Wait for `PO_NOTES.md` to be written before continuing.
   - If PO exits via `stop` (discard) without writing `PO_NOTES.md`: halt and
     print an error to the user — this is an unrecoverable state for the
     pipeline.
   - autoFlow: PO Phase runs non-interactively; planner proceeds immediately.
   - Add `po` to the Subagents table with action "PO Phase — Requirements".

2. **Update Phase 3 — Plan prompt** — In the existing Phase 3 spawn block,
   update the planner instructions to explicitly say: "Read
   `plans/<feature>/PO_NOTES.md` as the authoritative source of user stories.
   Decompose — do not re-author stories." The existing STORM_SEED.md and scout
   findings lines remain unchanged.

Do not alter Phase 1 — Analyze, Phase 2 — Scout, or any Stage 1 content.

Acceptance check (content facts only):
- Stage 2 contains a "PO Phase" section that precedes "Phase 1 — Analyze".
- The PO Phase documents the PO_NOTES.md existence check.
- The PO Phase documents the halt-on-discard behavior.
- The Phase 3 planner prompt references `PO_NOTES.md` as authoritative source.
- The Subagents table includes a row for `po`.

**Leaves files:** `plan.md` updated; all other files unchanged.

---

## Conversation 2 — Planner + tester escalation protocols

**Stories fulfilled:** 3, 4

**Goal:** By the end of this conversation, `planner.md` documents three
escalation paths (PO advisory spawn / OPEN halt / ARCH_QUESTION) and `tester.md`
"What NOT to do" contains the ARCH_QUESTION escalation rule. All existing
content in both files is preserved verbatim.

### Phase 1 — Pre-flight read

Read `src/pathly_data/core/agents/planner.md` and
`src/pathly_data/core/agents/tester.md` in full. Note:
- The exact text of the existing "do not make technical architecture decisions"
  rule in `planner.md`.
- All existing bullet items in `tester.md` "What NOT to do".

Record these verbatim so edits do not accidentally alter them.

**Leaves files:** unchanged.

### Phase 2 — Update planner.md (Story 3)

Add a new section to `src/pathly_data/core/agents/planner.md` titled
"Escalation protocols during decomposition". Place it after "When planning
conversations" and before "Story → Phase → Conversation traceability".

The section must document three distinct escalation paths as a numbered list:

1. **PO advisory spawn** — If a story from `PO_NOTES.md` is ambiguous or
   missing acceptance criteria that cannot be inferred from context: spawn PO
   in advisory mode (one bounded question, read-only, no state change). Use the
   answer to continue decomposition. If PO cannot answer from available context,
   fall through to path 2.

2. **OPEN halt** — Write the unresolved item as an `OPEN: <item>` block in the
   relevant plan file and halt for the user. Do not guess. Do not continue past
   an unresolved product question.

3. **ARCH_QUESTION escalation** — When the planner encounters something
   requiring architectural judgment, write `ARCH_QUESTION: <question>` in an
   `OPEN:` block and direct the user to `/meet architect`. Do not attempt to
   resolve the architectural question. Complete all non-architectural phases
   before writing the ARCH_QUESTION block — never leave a phase half-authored.

Immediately after the three paths, add a transition sentence: "This section
strengthens the existing rule below — the ARCH_QUESTION path is the specific
mechanism for applying it." Then preserve the existing "do not make technical
architecture decisions" bullet verbatim in its current location in "What NOT
to do".

Acceptance check (content facts only):
- `planner.md` contains a section titled "Escalation protocols during
  decomposition".
- The section lists all three escalation paths.
- The phrase `ARCH_QUESTION` appears in `planner.md`.
- The phrase `OPEN:` appears in `planner.md` in context of halting.
- The phrase "PO advisory" appears in `planner.md`.
- The existing "do not make technical architecture decisions" text is preserved
  verbatim in "What NOT to do".

**Leaves files:** `planner.md` updated; all other files unchanged.

### Phase 3 — Update tester.md (Story 4)

Add one bullet to the "What NOT to do" section of
`src/pathly_data/core/agents/tester.md`. Place it as the last bullet in that
section.

The bullet must:
- State the prohibition: do not attempt to resolve architectural or design
  questions.
- State the escalation action: if a test failure implies a design issue, report
  it as `ARCH_QUESTION: <description>` and direct the user to `/meet architect`
  or `/meet planner`.
- Treat ambiguous failures (bug or design issue?) as both: report one normal
  bug report and one ARCH_QUESTION, leave resolution to the human.
- State that multiple failures sharing a root architectural cause produce one
  ARCH_QUESTION covering all related failures.

Do not alter any existing "What NOT to do" bullets.

Acceptance check (content facts only):
- `tester.md` "What NOT to do" contains a bullet about architectural questions.
- The phrase `ARCH_QUESTION` appears in `tester.md`.
- The bullet references `/meet architect` or `/meet planner`.
- All four existing "What NOT to do" bullets are preserved verbatim.

**Leaves files:** `tester.md` updated.

---

## Cross-reference

| Story | Phase(s) | Conversation |
|---|---|---|
| 1 — PO reads STORM_SEED.md and scales interaction depth | Conv 1 Phase 2 | 1 |
| 2 — PO Phase inserted into team-flow/plan Stage 2 | Conv 1 Phase 3 | 1 |
| 3 — Planner consults PO for ambiguous stories and escalates architecture | Conv 2 Phase 2 | 2 |
| 4 — Tester escalates architectural questions via ARCH_QUESTION | Conv 2 Phase 3 | 2 |

---

## Files expected to change

**Conversation 1:**
- `src/pathly_data/core/agents/po.md` — Activation section expanded, fallback table added
- `src/pathly_data/core/skills/team-flow/plan.md` — PO Phase inserted, Phase 3 prompt updated, Subagents table updated

**Conversation 2:**
- `src/pathly_data/core/agents/planner.md` — Escalation protocols section added
- `src/pathly_data/core/agents/tester.md` — ARCH_QUESTION bullet added to "What NOT to do"

## Out of scope

- Changing the `/po` standalone skill behavior
- Adding new plan file formats or rigor levels
- Changing how STORM_SEED.md is written (architect's domain)
- Retroactively updating existing plan files
