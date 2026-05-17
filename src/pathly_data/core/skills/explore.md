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

## Scout spawning rules — MANDATORY

These rules are hard constraints, not suggestions. Violating them is always wrong.

**You MUST spawn scouts. You must NEVER read files directly during TRACING.**
Direct tool calls (Read, Grep, Glob) by the orchestrator are forbidden during the trace phase.
Scouts are the only permitted mechanism for reading codebase files.

**Wide scout rule (always required):** One scout MUST always be designated as the
**orientation scout**. Its job is to gather broad structural context — what files exist
in the relevant layer(s), how they connect, what the dependency direction is, and which
files are most relevant to the question. The orientation scout does NOT produce conclusions;
it produces a map that the other scouts use to scope their work.
The orientation scout counts toward the min/max total.

**Clustering rule (all remaining scouts):** Every scout after the orientation scout
must be clustered — assigned 2–3 related files in the same layer or the same risk area.
A clustered scout that reads everything = wrong. A clustered scout that reads one file only
= probably too narrow, reconsider the split. Target: each clustered scout covers one
coherent concern and produces cited file:line findings for that concern only.

**Scout count:**
| Scope | Min scouts | Max scouts |
|---|---|---|
| Single risk / single question | 2 | 2 |
| 2–3 related risks | 2 | 3 |
| 4–5 distinct risk areas | 3 | 4 |
| Genuinely independent risks requiring full isolation | — | 5 (hard ceiling) |

Spawning fewer than 2 scouts is always wrong — even for a narrow question.
Spawning more than 4 scouts requires explicit justification written into EXPLORE.md before spawning.
5 scouts is the absolute ceiling; it may only be used when risks are structurally independent
and cannot be clustered without losing findings.

**Parallelism rule:** All scouts for a given TRACING phase MUST be launched in a single
message (parallel tool calls). Sequential scout launches are wrong.

---

## FSM execution loop

After the question is framed and confirmed, run the FSM loop using MCP tools.

`PROJECT_ROOT` = the absolute path to the user's project directory (cwd at skill invocation).

Call FSM tool: `{{FSM_NEXT_ACTION}}(flow="explore", topic=TOPIC, project_root=PROJECT_ROOT)`

Display the contextual menu (same format as team.md — see CONTEXTUAL_MENU_UX.md for format).
Use the explore guidance table from CONTEXTUAL_MENU_UX.md for state-specific lines.

Execute the returned agent instructions. When complete, call:
`{{FSM_COMPLETE_STAGE}}(flow="explore", topic=TOPIC, project_root=PROJECT_ROOT)`

Handle blocked, decide, and feedback cases using the same protocol as team.md.
Repeat until `done=true`.

**Important:** The scout spawning rules in the section above still apply during TRACING state.
The MCP server does not enforce them — the skill must enforce the min/max scout count and
parallelism rules from the "## Scout spawning rules — MANDATORY" section.
