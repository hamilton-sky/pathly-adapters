# Conversation Prompts — po-planner-separation

---

## Conversation 1 — PO agent + team-flow plan pipeline

**Stories:** 1, 2
**Done when:** `po.md` documents three activation modes with a fallback table;
`plan.md` Stage 2 opens with a PO Phase that gates on `PO_NOTES.md`; Phase 3
planner prompt references `PO_NOTES.md` as authoritative source.

---

You are implementing a behavior update to two markdown agent/skill files in the
`pathly-adapters` project. You are editing documentation files only — no Python,
no tests. Do not create new files unless explicitly instructed.

### Pre-flight (before editing anything)

Read these files in full and note their current structure:
- `src/pathly_data/core/agents/po.md`
- `src/pathly_data/core/skills/team-flow/plan.md`

Record any existing section headings that are relevant to the planned additions
so you do not duplicate or overwrite them.

### Task 1 — Update po.md (Story 1)

File: `src/pathly_data/core/agents/po.md`

Make three targeted additions to the "Activation" section. Do not alter any
text outside that section.

**Addition 1 — New subsection.**

After the existing activation logic (which reads a PRD and prints the banner),
add a subsection titled:

```
### When activated from team-flow/plan (not standalone /po skill)
```

The subsection must describe what the PO does based on the state of
`plans/<feature>/STORM_SEED.md`:

- **Rich STORM_SEED.md** (contains a problem statement, named users, and defined
  scope): Read it, infer user stories and acceptance criteria, write a draft
  `PO_NOTES.md`, then pause with exactly this prompt:
  > "Here are the stories I derived — correct anything or say 'go'."

- **Thin or absent STORM_SEED.md** (missing or contains only headings without
  body text): Enter full interactive mode — one question at a time, same as the
  standalone skill, until the user says `stop notes`.

- **autoFlow active**: Write a best-guess `PO_NOTES.md` without pausing.
  Anything that cannot be resolved from available context is written as an
  `OPEN: <item>` entry in the `## Open Questions` section of `PO_NOTES.md`.

**Addition 2 — Fallback table.**

Immediately after the new subsection, insert this table:

| Condition | Mode | Pauses? |
|---|---|---|
| Rich STORM_SEED.md | Confirmation pass | Yes — once |
| Thin or absent STORM_SEED.md | Full interactive | Yes — per question |
| autoFlow active | Best-guess write | No |

**Addition 3 — Edge case note.**

Below the table, add a short paragraph:

> If STORM_SEED.md exists but contains only headings and no body text, treat it
> as thin. If autoFlow is active alongside a rich STORM_SEED.md, autoFlow wins —
> no pause. The standalone /po skill does not trigger this logic.

**Acceptance check — verify these content facts before finishing Task 1:**
- `po.md` contains the subsection heading "When activated from team-flow/plan
  (not standalone /po skill)".
- The subsection describes all three cases (rich / thin or absent / autoFlow).
- A three-row fallback table is present.
- The word `autoFlow` appears in `po.md`.
- The phrase `OPEN:` appears in `po.md` in the context of unresolved items.
- No existing text outside the Activation section has been altered.

### Task 2 — Update plan.md Stage 2 (Story 2)

File: `src/pathly_data/core/skills/team-flow/plan.md`

Make two targeted edits. Do not alter Stage 1 or any content outside the
specified locations.

**Edit 1 — Insert PO Phase at the top of Stage 2.**

Before the current "### Phase 1 — Analyze" heading in Stage 2, insert a new
section:

```
### PO Phase — Requirements

Check whether `plans/<feature>/PO_NOTES.md` already exists.
- **If yes:** Skip PO Phase entirely. Proceed to Phase 1 — Analyze.
- **If no:** Check `plans/<feature>/STORM_SEED.md` for richness.
  - Rich (problem, users, and scope present): Spawn `po` in confirmation-pass
    mode. Wait for the user to confirm or correct the derived stories. PO writes
    `PO_NOTES.md` on `go`.
  - Thin or absent: Spawn `po` in full-interactive mode. Wait for the user to
    type `stop notes`. PO writes `PO_NOTES.md` on exit.
  - Wait for `PO_NOTES.md` to exist before continuing.
- **If PO exits via `stop` (discard) without writing `PO_NOTES.md`:** Halt.
  Print to the user: "PO Phase: no PO_NOTES.md written — pipeline cannot
  continue. Re-run and complete the PO session, or manually create
  plans/<feature>/PO_NOTES.md."
- **autoFlow:** PO Phase runs non-interactively. PO writes best-guess
  `PO_NOTES.md` without pausing. Planner proceeds immediately.
```

**Edit 2 — Update the Subagents table.**

Add a row to the Subagents table:

| PO Phase — Requirements | `po` |

**Edit 3 — Update Phase 3 — Plan spawn block.**

In the existing Phase 3 spawn block (the one that spawns `planner` with
`phase: plan`), add this line to the planner instructions — place it immediately
after the STORM_SEED.md line:

```
Read plans/[feature]/PO_NOTES.md as the authoritative source of user stories.
Decompose — do not re-author stories.
```

Do not remove or reorder any existing lines in the spawn block.

**Acceptance check — verify these content facts before finishing Task 2:**
- Stage 2 contains a "PO Phase — Requirements" section that precedes
  "Phase 1 — Analyze".
- The PO Phase section documents the PO_NOTES.md existence check (skip if
  present).
- The PO Phase section documents the halt-on-discard behavior with the exact
  error message.
- The PO Phase section documents autoFlow behavior.
- The Subagents table includes a row for `po`.
- The Phase 3 planner spawn block references `PO_NOTES.md` as authoritative
  source.
- Stage 1 content is unchanged.
- Phase 1 — Analyze, Phase 2 — Scout headings and content are unchanged.

---

## Conversation 2 — Planner + tester escalation protocols

**Stories:** 3, 4
**Done when:** `planner.md` contains an "Escalation protocols during
decomposition" section with three distinct paths; `tester.md` "What NOT to do"
contains the ARCH_QUESTION escalation bullet; all existing content in both
files is preserved verbatim.

---

You are implementing a behavior update to two markdown agent files in the
`pathly-adapters` project. You are editing documentation files only — no Python,
no tests. Do not create new files unless explicitly instructed.

### Pre-flight (before editing anything)

Read these files in full and record verbatim:
- The exact text of the existing "do not make technical architecture decisions"
  bullet in `src/pathly_data/core/agents/planner.md`.
- All four existing bullets in the "What NOT to do" section of
  `src/pathly_data/core/agents/tester.md`.

You will need these exact strings to verify nothing was accidentally altered.

### Task 1 — Update planner.md (Story 3)

File: `src/pathly_data/core/agents/planner.md`

Add a new section titled "Escalation protocols during decomposition". Place it
after the "When planning conversations" section and before the "Story → Phase →
Conversation traceability" section.

The section content:

```markdown
## Escalation protocols during decomposition

When decomposing stories from `PO_NOTES.md`, three situations require a defined
response. Handle them in this order:

1. **PO advisory spawn** — If a story is ambiguous or missing acceptance
   criteria that cannot be inferred from `PO_NOTES.md` or surrounding context:
   spawn PO in advisory mode. The spawn is bounded to one question and is
   read-only — PO does not update any state or files. Use PO's answer to
   continue decomposition. If PO cannot answer from available context, fall
   through to path 2.

2. **OPEN halt** — Write the unresolved item as an `OPEN: <item>` block in the
   relevant plan file and halt for the user. Do not guess. Do not continue past
   an unresolved product question.

3. **ARCH_QUESTION escalation** — When the planner encounters something
   requiring architectural judgment, write `ARCH_QUESTION: <question>` in an
   `OPEN:` block and direct the user to `/meet architect`. Do not attempt to
   resolve the architectural question. Complete all non-architectural phases
   first — never leave a phase half-authored before writing the ARCH_QUESTION
   block.

This section strengthens the existing rule in "What NOT to do" below — the
ARCH_QUESTION path is the specific mechanism for applying it.
```

Do not alter the existing "do not make technical architecture decisions" bullet
in "What NOT to do" — it remains in place, and the new section references it.

**Acceptance check — verify these content facts before finishing Task 1:**
- `planner.md` contains a section titled "Escalation protocols during
  decomposition".
- The section lists all three paths as numbered items.
- The phrase `ARCH_QUESTION` appears in `planner.md`.
- The phrase `OPEN:` appears in `planner.md` in the context of halting.
- The phrase "PO advisory" appears in `planner.md`.
- The existing "do not make technical architecture decisions" bullet text is
  byte-for-byte identical to what you recorded in the pre-flight step.
- No other existing section has been altered.

### Task 2 — Update tester.md (Story 4)

File: `src/pathly_data/core/agents/tester.md`

Add one bullet as the last item in the "What NOT to do" section:

```
- Do not attempt to resolve architectural or design questions. If a test failure
  implies a design issue, report it as `ARCH_QUESTION: <description>` and direct
  the user to `/meet architect` or `/meet planner`. If a failure is ambiguous
  (bug or design issue?), report both: one normal bug report and one
  ARCH_QUESTION. Multiple failures sharing the same root architectural cause
  produce one ARCH_QUESTION covering all related failures — not one per test.
```

Do not alter, reorder, or reword any of the four existing "What NOT to do"
bullets.

**Acceptance check — verify these content facts before finishing Task 2:**
- `tester.md` "What NOT to do" now contains five bullets.
- The fifth bullet contains the phrase `ARCH_QUESTION`.
- The fifth bullet references `/meet architect` or `/meet planner`.
- The text of all four original bullets is byte-for-byte identical to what you
  recorded in the pre-flight step.
