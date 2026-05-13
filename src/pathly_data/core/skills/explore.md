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
pathly/explorations/<topic>/
  EXPLORE.md          ← session log: question, findings, file:line refs, open threads
  TRACE.md            ← scout output: code path traced, files visited
  CONCLUSIONS.md      ← what was learned; recommendation (build/don't build/investigate more)
  feedback/
    HUMAN_QUESTIONS.md  ← same protocol as team; blocks when scout needs a decision
```

---

## Step 1 — Frame the question

If `$ARGUMENTS` is blank: ask "What do you want to explore? (used as folder name)"

Store the topic as `TOPIC`.

Write `pathly/explorations/<topic>/EXPLORE.md`:

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

Ask the user to confirm or adjust the framing before continuing.

---

## Spawn orchestrator

Spawn the **orchestrator** agent with:
- flow_config: src/pathly_data/core/flows/explore.flow.yaml
- topic: [TOPIC]
- rigor: lite
- autoFlow: [autoFlow]

The orchestrator drives the full explore pipeline (frame → analyze → trace → conclude)
using the FSM defined in `explore.flow.yaml`. It handles all state tracking, agent spawning,
and feedback routing. Do not perform these actions in explore.md.
