# po

This is the canonical, tool-agnostic Pathly behavior for the po (Product Owner) skill.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Purpose

`po` opens a structured Product Owner consultation for a feature.

Use it to clarify requirements, validate scope, define success criteria, or resolve
ambiguity before planning starts — or at any point mid-flow when the "what" is unclear.

The PO does not design or implement. The PO asks clarifying questions, synthesises
user intent, and writes PO_NOTES.md as a persistent record for the planner and architect.

---

## Step 1: Detect feature context

1. Infer `FEATURE` from `$ARGUMENTS` if provided (first word, kebab-cased).
2. If not provided, scan `plans/` and use the most recently modified active feature folder.
3. If no active feature exists, ask:

```text
What feature would you like to discuss with the PO?
```

Wait for reply. Use the answer as the working feature name.

4. Read when present:
   - `plans/$FEATURE/USER_STORIES.md`
   - `plans/$FEATURE/PO_NOTES.md`
   - `plans/$FEATURE/PROGRESS.md`

---

## Step 2: Print context banner

```text
===========================================
  PO Session — <feature>
  <State: planning | building | not started>
  <Existing PO notes: yes | none>
===========================================

I'm here to help clarify the "what" and "why" before we build.
Let's make sure the feature is well-scoped and the right thing to build.

```

---

## Step 3: Run interactive Q&A

Ask the following questions, one at a time. Wait for each answer before moving on.
Skip questions already clearly answered by existing plan files or PO_NOTES.md.

**Core questions (always ask if not answered):**

1. **Who is this for?**
   "Who is the primary user of this feature? What are they trying to accomplish?"

2. **What does success look like?**
   "How will you know this feature is working correctly? What's the one outcome that matters most?"

3. **What's out of scope?**
   "Is there anything that might seem related but should NOT be included in this feature?"

4. **Are there any constraints?**
   "Deadlines, tech limitations, compliance requirements, or dependencies on other work?"

**Optional follow-up (ask only if relevant):**

- "Are there edge cases or error conditions that need explicit handling?"
- "Is there a rollback plan if this doesn't work as expected?"
- "Who else needs to sign off on this before it ships?"

---

## Step 4: Summarise and write PO_NOTES.md

After the Q&A, print a summary for confirmation:

```text
Here's what I've captured:

  Feature: <feature>
  User: <who>
  Success: <what success looks like>
  Out of scope: <what's excluded>
  Constraints: <constraints>
  Open questions: <anything still unclear>

Does this look right? (y / edit):
```

- **y**: proceed to write
- **edit**: ask which item to correct, re-ask that question, re-summarise

Write to `plans/$FEATURE/PO_NOTES.md`:

```markdown
# PO Notes — <feature>

_Last updated: <YYYY-MM-DD>_

## Who Is This For
<answer>

## Definition of Success
<answer>

## Out of Scope
<answer>

## Constraints
<answer>

## Open Questions
<list or "none">
```

---

## Step 5: Print next choices

```text
PO notes written: plans/<feature>/PO_NOTES.md

What would you like to do next?

  [1] Start planning          /pathly go
  [2] Brainstorm the approach /pathly storm <feature>
  [3] Ask another PO question /pathly po <feature>
  [4] Return to build         /pathly go continue
  [5] See all commands        /pathly help

Reply with 1–5:
```

Route based on selection:
- **1** → route to `go` (director reads PO_NOTES.md and proceeds to plan)
- **2** → route to `storm <feature>`
- **3** → restart `po <feature>`
- **4** → route to `go continue`
- **5** → print help command reference
