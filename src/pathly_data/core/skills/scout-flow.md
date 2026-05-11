# scout-flow

**This sub-skill is called by other skills, not by users directly.**

scout-flow is an orchestrator-only utility. It receives a `NEEDS_CONTEXT` block from a parent skill (plan, build, review, or an agent contract), spawns the appropriate research agents in parallel, and returns a compressed summary of findings back to the calling skill.

---

## Input parameters

| Parameter | Type | Description |
|---|---|---|
| `NEEDS_CONTEXT` | block | The research entries to resolve — see canonical format below |
| `ROLE` | string | Parent role name: `planner`, `builder`, `architect`, or `reviewer` |
| `FEATURE` | string | Feature name — injected into spawned agents as context |

---

## Canonical NEEDS_CONTEXT format

This file is the single source of truth for the NEEDS_CONTEXT format.

```
- type: scout  | scope: <files or directories>  | question: <specific question>
- type: quick  | question: <specific question>
- type: web    | query: <search query>
```

- `type: scout` — cross-file investigation requiring 3+ file reads
- `type: quick` — single-file lookup answerable in ≤ 2 tool calls
- `type: web` — external search query (documentation, package info, etc.)

When NEEDS_CONTEXT is `none`, scout-flow is not called.

---

## Behavior

### a. Short-circuit on empty input

If `NEEDS_CONTEXT` is `none` or empty, return `none` immediately. Do not spawn any agents.

### b. Parse and spawn in parallel

Otherwise, parse all entries and spawn research agents in parallel. Maximum 4 spawns total (see Priority rule below if more than 4 entries exist).

### c. Spawn mapping

| Entry type | Agent spawned | Parameters passed |
|---|---|---|
| `type: scout` | `scout` | `ROLE: <parent role>`, `scope`, `question` — read-only research |
| `type: quick` | `quick` | `ROLE: <parent role>`, `question` |
| `type: web` | `web-researcher` | `ROLE: <parent role>`, `query` |

### d. Role context

Each spawned agent receives the parent `ROLE` as context so it knows what perspective is relevant when researching.

### e. Compress findings

After all spawned agents complete, compress their findings into one short summary. Signal-to-noise rule: include only relevant facts. No raw dumps, no padding.

### f. Return

Return the compressed summary to the calling skill. The calling skill injects it under `## Scout Findings` before proceeding to its main phase.

---

## Priority rule

When there are more than 4 NEEDS_CONTEXT entries, keep only 4.

Priority order: `scout` > `quick` > `web`, then by order of appearance for ties.

Example: if there are 2 scout entries, 1 quick entry, and 2 web entries, drop the last web entry and spawn the first 4.

---

## Rules

- Max 4 parallel spawns.
- scout-flow is orchestrator-only — not user-invokable and must not appear in any user-facing menu or help output.
- Sub-agents spawned by scout-flow are terminal — they cannot spawn further agents.
