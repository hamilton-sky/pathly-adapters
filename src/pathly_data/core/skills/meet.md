# meet

This is the canonical, tool-agnostic Pathly behavior for the meet workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Purpose

`meet` is an advanced, read-only consultation workflow.

Use it when the user wants to ask one named role a bounded question during an
existing feature flow without editing code or silently changing pipeline state.

The consulted role gives advice only. It does not resolve feedback files, does
not update source code, and does not change workflow state on its own.

## Step 1: Detect context

1. Infer `FEATURE` from `$ARGUMENTS` if provided.
2. If `$ARGUMENTS` does not name a feature, scan `plans/` and use the most
   recently modified active feature folder.
3. Read these files when present:
   - `plans/$FEATURE/PROGRESS.md`
   - `plans/$FEATURE/feedback/`
   - `plans/$FEATURE/STATE.json`
   - `plans/$FEATURE/EVENTS.jsonl`
4. Infer the current workflow state in plain language:
   - planning
   - building
   - review feedback open
   - architecture feedback open
   - testing
   - done / retro complete

If no active feature exists, say:

```text
meet requires an active feature plan. Start a feature first, then run meet again.
```

Stop there.

## Step 2: List relevant roles

Print a context-aware menu based on the inferred workflow state.
Only show roles that are useful at this point in the pipeline.

### Role descriptions (use in all menus)

```
po             -> requirements, scope, success criteria, user value
planner        -> stories, acceptance criteria, task breakdown, ordering
architect      -> design, layers, contracts, migrations, rollback plans
reviewer       -> likely violations, diff quality, contract risks (advisory only)
tester         -> verification strategy, acceptance coverage, likely gaps
web-researcher -> external patterns, library docs, domain knowledge (cite sources)
```

### Menu by state

Print exactly one of the menus below based on the inferred state.

**storming / not started:**
```text
===========================================
  meet — <feature>
  State: storming / not started
===========================================

  Pick a role to consult:

  [1] po             -> is this the right thing to build?
  [2] architect      -> how might we approach this technically?
  [3] web-researcher -> what patterns exist externally?
  [4] See all commands

Reply with 1–4:
```

**planning:**
```text
===========================================
  meet — <feature>
  State: planning
===========================================

  Pick a role to consult:

  [1] po             -> scope, success criteria, what's out of scope
  [2] planner        -> story breakdown, ordering, rigor level
  [3] architect      -> design decisions, layer contracts, high-risk areas
  [4] web-researcher -> external patterns or library options
  [5] See all commands

Reply with 1–5:
```

**building:**
```text
===========================================
  meet — <feature>
  State: building
===========================================

  Pick a role to consult:

  [1] po             -> confirm scope or success criteria mid-build
  [2] planner        -> story clarification, acceptance criteria, task reordering
  [3] architect      -> design question, layer contract, integration shape
  [4] reviewer       -> early review — likely violations before I write the code
  [5] web-researcher -> external reference for a specific implementation question
  [6] See all commands

Reply with 1–6:
```

**review feedback open:**
```text
===========================================
  meet — <feature>
  State: review feedback open
===========================================

  Pick a role to consult:

  [1] reviewer       -> clarify what the feedback is asking for
  [2] architect      -> is the reviewer's concern architecturally valid?
  [3] planner        -> does fixing this require a scope change?
  [4] See all commands

Reply with 1–4:
```

**architecture feedback open:**
```text
===========================================
  meet — <feature>
  State: architecture feedback open
===========================================

  Pick a role to consult:

  [1] architect      -> what is the correct design resolution?
  [2] planner        -> does the redesign change stories or ordering?
  [3] reviewer       -> will the proposed resolution satisfy review gates?
  [4] See all commands

Reply with 1–4:
```

**testing:**
```text
===========================================
  meet — <feature>
  State: testing
===========================================

  Pick a role to consult:

  [1] tester         -> what's being tested, what's missing, likely gaps
  [2] planner        -> does this test failure imply a scope change?
  [3] architect      -> is the failure a design issue or an implementation issue?
  [4] reviewer       -> would this failure have been caught in review?
  [5] See all commands

Reply with 1–5:
```

**done / retro complete:**
```text
===========================================
  meet — <feature>
  State: done / retro complete
===========================================

  Pick a role to consult:

  [1] reviewer       -> was there anything in the diff worth noting for next time?
  [2] tester         -> were all acceptance criteria genuinely covered?
  [3] planner        -> should any stories be carried into the next feature?
  [4] See all commands

Reply with 1–4:
```

### Rules (apply to all states)

- Do NOT offer `builder` — implementation owner, not advisory.
- Do NOT offer `director` — routes workflows, not a consultant.
- Do NOT offer `orchestrator`, `quick`, or `scout` as named options.
  Scout may be spawned internally by another role during consultation if needed.
- Offer `po` only in states where scope, intent, or success criteria are live questions
  (storming, planning, building). Not in review/test/done.
- Offer `web-researcher` only in storming/planning/building — and only when the question
  clearly benefits from external sources.

## Step 3: Collect one bounded question

After the user picks a role, ask:

```text
What is the one question you want to ask <role>?
```

Rules:

- Keep the consultation to one bounded question.
- If the user asks multiple unrelated questions, ask them to choose one first.
- If the question implies code changes, redirect the role to advice only.

## Step 4: Run the consultation

Invoke the selected role in read-only mode.

Consultation rules for every role:

- Read project files as needed.
- May spawn only read-only subagents allowed by that role.
- Must not edit code.
- Must not edit plan files.
- Must not delete feedback files.
- Must not claim the workflow has advanced.
- Must answer the user's question directly and concretely.

Write the consultation note to:

`plans/$FEATURE/consults/YYYYMMDD-HHMMSS-<role>.md`

Use this structure:

```markdown
# Meet Note - <role> - <feature>

## Question
+[the bounded user question]

## Answer
+[direct answer]

## Evidence
- [files read, patterns found, or external sources if web-researcher was used]

## Recommendation
+[what the user should do next]

## Promotion Target
- none
- planner
- architect
```

Promotion target rules:

- `planner` if the answer should change stories, acceptance criteria, ordering,
  or decomposition.
- `architect` if the answer should change design, contracts, layers, rollback,
  or integration shape.
- `none` if the answer is advisory only.

## Step 5: Print next choices

After writing the consult note, print:

```text
Meet note written: plans/<feature>/consults/<timestamp>-<role>.md

What do you want to do next?

[1] Return to build
[2] Promote to planner update
[3] Promote to architecture update
[4] Ask another meet question
[5] See all commands

Reply with 1-5:
```

Interpret the choices as:

- **Return to build** -> route back to `team-flow <feature> build`
- **Promote to planner update** -> planner reads the consult note and updates
  plan files if warranted
- **Promote to architecture update** -> architect reads the consult note and
  updates architecture docs if warranted
- **Ask another meet question** -> restart `meet <feature>`
- **See all commands** -> print the help command reference

If the current state is not building, adapt the first option label to the most
natural return route, such as `Return to test` or `Return to review resolution`.

## Step 6: Promotion behavior

If the user chooses planner or architect promotion:

- Read the consult note.
- Update only the plan or architecture files that are directly affected.
- Report exactly what changed.
- Do not change source code.
- After the update, offer the same return options again.
