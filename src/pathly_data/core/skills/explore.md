# explore

This is the canonical, tool-agnostic Pathly behavior for the explore workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use route `explore <topic>` when you have a question, not a task:
- "How does X affect Y?"
- "Is it safe to change Z?"
- "What is the data flow for feature A?"
- "Should we migrate from B to C?"

Do NOT use when you already have acceptance criteria — use `team` instead.
Do NOT use to debug a known bug — use `debug` instead.

---

## File structure

```
explorations/<topic>/
  EXPLORE.md          ← session log: question, findings, file:line refs, open threads
  TRACE.md            ← scout output: code path traced, files visited
  CONCLUSIONS.md      ← what was learned; recommendation (build/don't build/investigate more)
  feedback/
    HUMAN_QUESTIONS.md  ← same protocol as team; blocks when scout needs a decision
```

No `plans/`, no `PROGRESS.md`, no `STORM_SEED.md`, no `EVENTS.jsonl`.

---

## Step 1 — Frame the question

If `$ARGUMENTS` is blank: ask "What do you want to explore? (used as folder name)"

Create `explorations/<topic>/` if it doesn't exist.

Write `explorations/<topic>/EXPLORE.md`:

```markdown
# Exploration — <topic>

## Question
[the specific question this exploration will answer]

## Scope
[what files, layers, or components are in scope]

## Out of scope
[what to skip — keep the exploration focused]

## Success criterion
[how we'll know the exploration is complete: "we can answer yes/no to the question above"]
```

Ask the user to confirm or adjust the framing before running the scout.

---

## Step 2 — Analyze (explorer phase: analyze)

Spawn the **explorer** agent with `phase: analyze`:

```
phase: analyze
Read explorations/<topic>/EXPLORE.md.
Identify what research is needed to answer the question.
```

Parse the `## NEEDS_CONTEXT` block it returns.

---

## Step 3 — Scout (if NEEDS_CONTEXT has entries)

If the block is not `none`, call **scout-path** with:
- `NEEDS_CONTEXT`: the block from Step 2
- `ROLE: explorer`
- `FEATURE: <topic>`

Use the returned compressed summary as `## Scout Findings`.

If the block is `none`, set Scout Findings to `none` and skip this step.

---

## Step 4 — Trace (explorer phase: explore)

Spawn the **explorer** agent with `phase: explore`:

```
phase: explore
explorations/<topic>/EXPLORE.md

## Scout Findings
[compressed summary from Step 3, or "none"]
```

The explorer writes `explorations/<topic>/TRACE.md`.

If the explorer returns a human question (rather than "TRACE written"):
- Write that question to `explorations/<topic>/feedback/HUMAN_QUESTIONS.md`
- Pause, show the user the question, wait for answer
- Delete `HUMAN_QUESTIONS.md`, then re-spawn the explorer with the answer appended

---

## Step 5 — Conclude (explorer phase: conclude)

Spawn the **explorer** agent with `phase: conclude`:

```
phase: conclude
explorations/<topic>/EXPLORE.md
explorations/<topic>/TRACE.md
```

The explorer writes `explorations/<topic>/CONCLUSIONS.md`.

---

## Step 6 — Present and offer graduation

Print the contents of `CONCLUSIONS.md` to the user.

Then ask:

```
Exploration complete. What next?

[1] Graduate to feature pipeline   -> team <topic> --from-exploration <topic>
[2] Explore a follow-up question   -> explore <follow-up>
[3] Done — keep as reference only
[4] Archive this exploration

Reply with 1, 2, 3, or 4:
```

**On '1' — Graduate:**
- Run `team <name>` with `CONCLUSIONS.md` injected as context for the storm stage.
  Tell the orchestrator: "Context from exploration: [paste CONCLUSIONS.md summary]."
- The storm agent starts with the exploration's answer as input, not from scratch.

**On '2' — Follow-up:**
- Ask "New question?" -> route to `explore <new-topic>`

**On '3' — Done:**
- Print: `Exploration saved: explorations/<topic>/CONCLUSIONS.md`
- No further action.

**On '4' — Archive:**
- Move `explorations/<topic>/` to `explorations/.archive/<topic>/`
- Print: `Archived: explorations/.archive/<topic>/`

---

## Rules

- **Explorer + scout-path only** — no builder, no reviewer, no tester, no planner.
- **Read-only on production code.** The only files written are inside `explorations/<topic>/`.
- **HUMAN_QUESTIONS.md is the only feedback file.** No REVIEW_FAILURES, no TEST_FAILURES.
- **No PROGRESS.md, no EVENTS.jsonl, no STATE.json.** Explorations are not FSM-tracked.
- **Graduation is opt-in.** The exploration never automatically starts `team`.
- **An exploration can end with "don't build."** That is a valid and valuable outcome.
