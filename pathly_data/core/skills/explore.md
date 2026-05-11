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

Do NOT use when you already have acceptance criteria — use `team-flow` instead.
Do NOT use to debug a known bug — use `debug` instead.

---

## File structure

```
explorations/<topic>/
  EXPLORE.md          ← session log: question, findings, file:line refs, open threads
  TRACE.md            ← scout output: code path traced, files visited
  CONCLUSIONS.md      ← what was learned; recommendation (build/don't build/investigate more)
  feedback/
    HUMAN_QUESTIONS.md  ← same protocol as team-flow; blocks when scout needs a decision
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

## Step 2 — Trace (scout)

Spawn the **scout** agent:

```
Read explorations/<topic>/EXPLORE.md.
Explore the codebase to answer the question in EXPLORE.md.

Rules:
- Follow visible code paths. Do not invent interactions.
- Return a TRACE.md-ready list of every file you read:
  Format: [file:line] — [what you found there] — [relevance to the question]
- Return findings for the skill to append under `## Findings` in EXPLORE.md
- If you need a human decision to continue (ambiguity, missing context),
  return the exact human question and stop; the skill writes `explorations/<topic>/feedback/HUMAN_QUESTIONS.md`.
- Do NOT write to any production code file.
- Do NOT build anything. Do NOT suggest fixes. Observe and report only.

Stop when you can answer the question in EXPLORE.md, or when you've exhausted
visible paths and must report what you found.
```

If `HUMAN_QUESTIONS.md` is created: pause, show user the question, wait for answer (delete file), then resume the scout.

---

## Step 3 — Draw conclusions

After the scout finishes and the skill writes `TRACE.md`, spawn the **quick** agent:

```
Read explorations/<topic>/EXPLORE.md and explorations/<topic>/TRACE.md.
Write explorations/<topic>/CONCLUSIONS.md:

## Answer
[direct answer to the question in EXPLORE.md — yes/no/it depends + one paragraph]

## Evidence
[3–5 bullet points, each with file:line reference, supporting the answer]

## Risks / open questions
[anything that needs more investigation before acting on the conclusion]

## Recommendation
[ONE of these three:]
  BUILD: This exploration justifies a feature. Suggested scope: [1-3 sentences]
  SKIP: Not worth building. Reason: [one sentence]
  INVESTIGATE MORE: [what specific question to explore next]
```

---

## Step 4 — Present and offer graduation

Print the contents of `CONCLUSIONS.md` to the user.

Then ask:

```
Exploration complete. What next?

[1] Graduate to feature pipeline   -> team-flow <topic> --from-exploration <topic>
[2] Explore a follow-up question   -> explore <follow-up>
[3] Done — keep as reference only
[4] Archive this exploration

Reply with 1, 2, 3, or 4:
```

**On '1' — Graduate:**
- Run `team-flow <name>` with `CONCLUSIONS.md` injected as context for the storm stage.
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

- **Scout only** — no builder, no reviewer, no tester, no planner.
- **Read-only on production code.** The only files written are inside `explorations/<topic>/`.
- **HUMAN_QUESTIONS.md is the only feedback file.** No REVIEW_FAILURES, no TEST_FAILURES.
- **No PROGRESS.md, no EVENTS.jsonl, no STATE.json.** Explorations are not FSM-tracked.
- **Graduation is opt-in.** The exploration never automatically starts `team-flow`.
- **An exploration can end with "don't build."** That is a valid and valuable outcome.
