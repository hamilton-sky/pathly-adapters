# Agents

Claude Code agent files are adapter packaging around the canonical role
contracts in `core/agents/`. The behavioral source of truth belongs in core;
this directory adds Claude-specific frontmatter such as `model`, `tools`, and
`skills`.

When changing how an agent thinks, edit the matching `core/agents/<agent>.md`
first, then sync this adapter file. Do not let the Claude copy become an
independent fork of the role contract.

Agents are architectural roles with behavioral contracts. A role defines how the
agent thinks. The `tools:` frontmatter is the runtime-enforced capability set for
that role.

## Role Map

| Agent | Role | Model | Enforced tools | Invoke when |
|---|---|---|---|---|
| `director` | director | sonnet | Read, Glob, Grep, Agent | Natural-language entry point; chooses workflow, rigor, and entry stage |
| `architect` | architect | opus | Read, Glob, Grep, Write, Edit, Agent | Technical design, layer decisions, trade-offs, system design |
| `po` | po | opus | Read, Write | Interactive requirements discussion; probes scope, challenges assumptions, validates PRDs |
| `planner` | product-owner | sonnet | Read, Glob, Grep, Write, Edit, Agent | Requirements, user stories, conversation decomposition, plans/ folder |
| `builder` | executor | sonnet | Read, Glob, Grep, Edit, Write, Bash, Agent, TodoWrite | Coding, verification, staying in scope |
| `tester` | tester | sonnet | Read, Glob, Grep, Bash, Write, Agent | Verifying acceptance criteria, test plans, coverage gaps |
| `reviewer` | reviewer | sonnet | Read, Glob, Grep, Write, Agent | Adversarial review, feedback files, scout delegation |
| `quick` | analyst | haiku | Read, Glob, Grep | Fast lookups, short summaries, focused tasks (<=2 tool calls) |
| `orchestrator` | orchestrator | haiku | Read, Glob, Grep, Write, Edit, Bash, Agent | Recovering FSM state and running the full pipeline |
| `scout` | analyst | haiku | Read, Glob, Grep | Read-only codebase investigation; spawned by builder/reviewer/tester/architect |
| `web-researcher` | analyst | haiku | WebSearch, WebFetch | Web-only research; spawned by architect/planner for external docs and patterns |

## Enforcement Summary

The `tools:` list is not just documentation. The runtime blocks tools outside the
declared list:

| Agent | Enforced boundary |
|---|---|
| `scout` | Cannot write, spawn agents, browse, or touch external resources |
| `web-researcher` | Cannot write or read local files; web search/fetch only |
| `quick` | Cannot write or spawn agents; limited to small local lookups |
| `reviewer` | Can write feedback files and spawn scouts; cannot edit source or run Bash |
| `tester` | Can run Bash and write test feedback; cannot edit source |
| `builder` | Full implementation access except web tools |
| `architect` | Can write and edit design docs; cannot run Bash |
| `planner` | Can write and edit plan files; cannot run Bash or web tools directly |
| `director` | Can read and route; cannot write |
| `po` | Can read PRDs and write `PO_NOTES.md`; no codebase glob/grep/edit/bash |
| `orchestrator` | Can manage FSM state and spawn agents; no web tools |

## Architecture

```text
User request
  -> director
       decides intent, risk, rigor, and entry point
       invokes /go, /team-flow, /review, /build, or /retro
  -> orchestrator
       recovers filesystem FSM state
       routes one next action
  -> architect / planner / builder / reviewer / tester / quick
```

Director sits above the orchestrator. Director makes product/process decisions:
whether the task is `nano`, `lite`, `standard`, or `strict`; whether to storm,
probe, plan, build, test, review, or stop for clarification.

Orchestrator stays deterministic. It owns filesystem state recovery, event logs,
feedback routing, retry limits, and stage transitions.

## Handoff Contract

```text
director
  -> chooses workflow and invokes /team-flow

orchestrator
  -> runs the filesystem FSM

storm (architect)
  -> STORM_SEED.md

plan (planner)
  -> plans/<feature>/
       USER_STORIES.md
       IMPLEMENTATION_PLAN.md
       CONVERSATION_PROMPTS.md
       PROGRESS.md
       optional rigor-specific extras

build (builder) x N
  -> implementation changes
  -> PROGRESS.md updates

review (reviewer)
  -> PASS or feedback files

test (tester)
  -> acceptance criteria verification

retro (quick)
  -> RETRO.md
```

## Entry Point

Prefer the natural-language front door:

```text
/go <what you want>
```

Direct pipeline entry is still available:

```text
/team-flow <feature-name>
/team-flow <feature-name> fast
/team-flow <feature-name> nano
/team-flow <feature-name> lite
/team-flow <feature-name> standard
/team-flow <feature-name> strict
```

## For Teams

Each role is a clear ownership boundary:

- **director** owns what workflow should run for the user's request.
- **architect** owns how things should be built technically.
- **planner** owns what should be built and for whom.
- **builder** owns building what was planned.
- **tester** owns verifying what was built matches what was planned.
- **analyst** owns learning and reporting fast.
- **reviewer** owns finding what is wrong before it ships.
- **orchestrator** owns deterministic workflow state and feedback routing.


# Core Agents

Tool-agnostic behavioral contracts for Pathly roles belong here.

Each agent file should describe:

- role
- responsibility boundaries
- inputs it reads
- files it may write
- handoff rules
- failure and escalation behavior

Do not include Claude Code frontmatter, Codex plugin fields, or tool-specific
model names in these core files. Adapters add that metadata.
