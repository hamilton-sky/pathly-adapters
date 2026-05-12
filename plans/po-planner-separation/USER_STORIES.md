# User Stories — po-planner-separation

## Context

The Pathly pipeline currently merges PO (requirements authorship) and planner
(decomposition) responsibilities in a single agent. This creates two problems:
the planner re-authors stories that should come from the PO, and there is no
structured path for either the planner or tester to escalate architectural
questions back to the right agent.

This feature formalises the handoff: PO writes `PO_NOTES.md`, planner reads it.
Each file touched is one story.

---

## Story 1 — PO reads STORM_SEED.md and scales interaction depth

**Delivered by:** Conversation 1

As a developer running the team-flow pipeline with a rich STORM_SEED.md,
I want the PO agent to read that document and infer stories automatically
rather than asking me questions I have already answered,
so that requirements discovery is proportional to what is already known and I do
not repeat myself between the storm and plan stages.

### Acceptance criteria

- [x] `po.md` contains an "Activation" section or equivalent that documents three
  cases: rich STORM_SEED.md, thin/absent STORM_SEED.md, and autoFlow mode.
- [x] When the feature's `plans/<feature>/STORM_SEED.md` is present and rich
  (contains problem statement, users, and scope), PO infers stories and writes a
  draft `PO_NOTES.md`, then pauses with exactly one confirmation prompt: "Here
  are the stories I derived — correct anything or say 'go'."
- [x] When STORM_SEED.md is absent or thin, PO enters the existing full
  interactive mode (one question at a time until `stop notes`).
- [x] When `autoFlow` is active, PO writes its best-guess `PO_NOTES.md` without
  pausing. Unresolved items are written as `OPEN: <item>` entries in the
  `## Open Questions` section of `PO_NOTES.md`.
- [x] A fallback table in `po.md` summarises all three cases in a scannable
  format (rich seed / thin or absent seed / autoFlow).

### Edge cases

- STORM_SEED.md exists but contains only headings and no body text — treated as
  thin, full interactive mode applies.
- autoFlow flag arrives with a rich STORM_SEED.md — autoFlow wins, no pause.
- PO is invoked via the standalone `/po` skill rather than team-flow — the
  STORM_SEED.md richness logic is not triggered; existing skill behavior is
  unchanged.

---

## Story 2 — PO Phase inserted into team-flow/plan Stage 2

**Delivered by:** Conversation 1

As a developer running `team-flow plan`,
I want the pipeline to automatically invoke the PO agent before the planner runs,
so that `PO_NOTES.md` exists and is authoritative by the time the planner begins
decomposition.

### Acceptance criteria

- [x] `plan.md` Stage 2 contains a new "PO Phase" that executes before the
  current "Phase 1 — Analyze".
- [x] The PO Phase first checks whether `plans/<feature>/PO_NOTES.md` already
  exists. If yes, the PO Phase is skipped entirely and planning proceeds.
- [x] If `PO_NOTES.md` does not exist, the PO Phase checks for STORM_SEED.md
  richness and spawns `po` in the appropriate mode (confirmation pass if rich,
  full interactive if thin/absent).
- [x] The PO Phase waits for `PO_NOTES.md` to be written before continuing.
- [x] The planner Phase 3 prompt explicitly instructs the planner to read
  `PO_NOTES.md` as the authoritative source of user stories and to decompose
  rather than re-author.
- [x] Existing planner phases (Analyze, Scout, Plan) are otherwise unchanged in
  content and order.

### Edge cases

- `PO_NOTES.md` is present from a previous run — pipeline skips PO Phase,
  no duplicate notes are written.
- PO exits via `stop` (discard) rather than `stop notes` — PO_NOTES.md is not
  written; pipeline should surface this as an unrecoverable state and halt,
  printing a clear error to the user.
- autoFlow mode: PO Phase runs non-interactively; planner proceeds immediately
  after PO writes its best-guess notes.

---

## Story 3 — Planner consults PO for ambiguous stories and escalates architecture

**Delivered by:** Conversation 2

As a planner decomposing user stories into conversations,
I want a defined protocol for what to do when a story is ambiguous or requires
architectural judgment,
so that I never silently guess and never block indefinitely on a question I
cannot resolve alone.

### Acceptance criteria

- [x] `planner.md` contains a rule stating: if a story from `PO_NOTES.md` is
  ambiguous or missing acceptance criteria that cannot be inferred from context,
  the planner spawns PO in advisory mode (one bounded question, read-only, no
  state change) and uses the answer to continue.
- [x] `planner.md` states that if PO cannot answer from available context, the
  planner writes the unresolved item as an `OPEN: <item>` block and halts for
  the user.
- [x] `planner.md` contains a rule stating: when the planner encounters something
  requiring architectural judgment, it writes `ARCH_QUESTION: <question>` in an
  `OPEN:` block and directs the user to `/meet architect`. It must NOT attempt
  to resolve the architectural question.
- [x] The existing "do not make technical architecture decisions" rule in
  `planner.md` is preserved and the new ARCH_QUESTION rule is explicitly
  positioned as a strengthening of it.
- [x] The three escalation paths are distinct and readable as a unit
  (PO advisory spawn / OPEN halt / ARCH_QUESTION).

### Edge cases

- PO advisory spawn returns a contradictory answer — planner treats this as
  unable to resolve and writes an OPEN block.
- Architectural question arises in the middle of decomposing a conversation's
  phases — planner completes all non-architectural phases and writes the
  ARCH_QUESTION block at the end, so no phase is half-authored.
- Planner cannot determine whether a question is product or architecture — it
  errs toward PO advisory first, then escalates to ARCH_QUESTION if PO defers.

---

## Story 4 — Tester escalates architectural questions via ARCH_QUESTION

**Delivered by:** Conversation 2

As a tester encountering a test failure that implies a design issue,
I want a defined protocol for surfacing architectural problems without attempting
to resolve them,
so that the right people (architect, planner) are routed to the right place and
the tester's role remains purely verification.

### Acceptance criteria

- [x] `tester.md` "What NOT to do" section contains a rule: do not attempt to
  resolve architectural or design questions.
- [x] The rule specifies the exact format for escalation: report the issue as
  `ARCH_QUESTION: <description>` and direct the user to `/meet architect` or
  `/meet planner`.
- [x] The new rule is phrased as an escalation protocol, not just a prohibition —
  it tells the tester what to do, not only what not to do.
- [x] Existing "What NOT to do" items are preserved verbatim.

### Edge cases

- Test failure is ambiguous — could be a bug or a design issue. Tester reports
  both possibilities: one as a normal bug report, one as an ARCH_QUESTION, and
  leaves resolution to the human.
- Multiple test failures share the same root architectural cause — tester writes
  one ARCH_QUESTION covering all related failures rather than one per test.
