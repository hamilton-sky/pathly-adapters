# UX_DIAGRAMS.md — pathly-studio

ASCII mockups for every section of the app. Builder should match these layouts.

---

## 1. Full app layout

```
┌─ Pathly Studio ──────────────────────────────────────────────────────────────┐
│  Pathly Studio          user-auth-refactor ▼        ● MCP live  [↑ Publish] │
├────────────────┬─────────────────────────────────────────────────────────────┤
│ ▼ Flows        │                                                              │
│   team.yaml    │                                                              │
│   debug.yaml   │                                                              │
│   explore.yaml │                                                              │
│   [+ new flow] │              < select an item from the sidebar >             │
│                │                                                              │
│ ▶ Skills       │                                                              │
│ ▶ Agents       │                                                              │
│ ▶ Templates    │                                                              │
│ ─────────────  │                                                              │
│ ● Monitor      │                                                              │
│ ─────────────  │                                                              │
│ ⚙ Settings     │                                                              │
│           [◄]  │                                                              │
└────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 2. Sidebar — expanded with Skills open

```
┌────────────────┐
│ ▼ Flows        │
│   team.yaml    │
│   debug.yaml   │
│   explore.yaml │
│   [+ new flow] │
│                │
│ ▼ Skills       │
│   go         ● │  ← unsaved dot
│   pause        │
│   status       │
│   fix          │
│   end          │
│   start        │
│   meet         │
│   [+ new]      │
│                │
│ ▶ Agents       │
│ ▶ Templates    │
│ ─────────────  │
│ ● Monitor      │
│ ─────────────  │
│ ⚙ Settings     │
│           [◄]  │
└────────────────┘
```

---

## 3. Sidebar — collapsed

```
┌──┐
│[►]
│   │
│   │
│   │
│   │
│   │
│   │
└──┘
```

Clicking `[►]` restores the sidebar to full width.

---

## 4. Editor — Edit tab

```
┌─ Skills / go.md ───────────────────────────────────────────────────────────┐
│  [ Edit ]  [ Preview ]                                  [⊟ Split]  [Save]  │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Configuration ──────────────────────────────────────────────────────┐  │
│  │  Name          go                                                    │  │
│  │  Description   Continue active pipeline feature                      │  │
│  │  Adapters      [✓] claude    [✓] codex    [✓] copilot               │  │
│  │  Tools         Bash, Read, Glob, Grep, TodoWrite, Agent              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ Content ──────────────────────────────────────────────── line 1/84 ─┐  │
│  │  # Go                                                                 │  │
│  │                                                                       │  │
│  │  ## Step 1 — Detect active feature                                   │  │
│  │  Call `next_action` with no arguments. If no active                  │  │
│  │  topic is found, print "No active feature."                          │  │
│  │                                                                       │  │
│  │  ## Step 2 — Show contextual state panel                             │  │
│  │  ┌─────────────────────────────────────────────────┐                 │  │
│  │  │ Flow: team | Topic: {topic} | State: {state}    │                 │  │
│  │  └─────────────────────────────────────────────────┘                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Editor — Preview tab

```
┌─ Skills / go.md ───────────────────────────────────────────────────────────┐
│  [ Edit ]  [ Preview ]                                  [⊟ Split]  [Save]  │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Configuration ──────────────────────────────────────────────────────┐  │
│  │  Name  go    Adapters  [✓] claude  [✓] codex  [✓] copilot           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ Preview ────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  Go                                                                   │  │
│  │  ════════════════════════════════════════                             │  │
│  │                                                                       │  │
│  │  Step 1 — Detect active feature                                       │  │
│  │  ──────────────────────────────                                       │  │
│  │  Call next_action with no arguments. If no active topic               │  │
│  │  is found, print "No active feature."                                 │  │
│  │                                                                       │  │
│  │  Step 2 — Show contextual state panel                                 │  │
│  │  ──────────────────────────────────                                   │  │
│  │  Render the panel using the state returned by next_action...         │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Editor — Split pane (Edit + Preview side by side)

```
┌─ Skills / go.md ───────────────────────────────────────────────────────────┐
│  [ Edit ]  [ Preview ]                                  [⊟ Split]  [Save]  │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Configuration ──────────────────────────────────────────────────────┐  │
│  │  Name  go    Adapters  [✓] claude  [✓] codex  [✓] copilot           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌─ Edit ─────────────────────────┬─ Preview ──────────────────────────┐  │
│  │  # Go                          │                                     │  │
│  │                                │  Go                                 │  │
│  │  ## Step 1 — Detect active     │  ═══════════════════════           │  │
│  │  Call `next_action` with no    │                                     │  │
│  │  arguments...                  │  Step 1 — Detect active feature     │  │
│  │                                │  ──────────────────────────         │  │
│  │  ## Step 2 — Show panel        │  Call next_action with no           │  │
│  │  ┌──────────────────────┐      │  arguments...                       │  │
│  │  │ Flow: team | ...     │      │                                     │  │
│  │  └──────────────────────┘      │  Step 2 — Show panel                │  │
│  │                                │  ──────────────────                 │  │
│  └────────────────────────────────┴─────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Flow editor — Visual tab

```
┌─ Flows / team.flow.yaml ───────────────────────────────────────────────────┐
│  [ Visual ]  [ YAML ]                                             [Save]   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐            │
│  │ STORMING │───►│ PLANNING │───►│ BUILDING │───►│ REVIEWING │            │
│  │ discover │    │  planner │    │  builder │    │  reviewer │            │
│  └──────────┘    └──────────┘    └──────────┘    └─────┬─────┘            │
│                                       ▲   REVIEW_       │ default          │
│                                       │   FAILURES       ▼                 │
│                                       └──────────── ┌──────────┐           │
│                                                     │ TESTING  │           │
│                                                     │  tester  │           │
│                                                     └────┬─────┘           │
│                                                          │ default          │
│                                                          ▼                  │
│                                                     ┌──────────┐           │
│                                                     │   DONE   │           │
│                                                     │    —     │           │
│                                                     └──────────┘           │
│                                                                             │
│  [+ Add State]    [+ Add Transition]    [Validate YAML]                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Flow editor — Visual tab with node selected

```
┌─ Flows / team.flow.yaml ───────────────────────────────────────────────────┐
│  [ Visual ]  [ YAML ]                                             [Save]   │
├──────────────────────────────────────────────┬─────────────────────────────┤
│                                              │ ▌ Node: BUILDING            │
│  ┌──────────┐    ┌──────────┐ ┌──────────┐  │                             │
│  │ STORMING │───►│ PLANNING │►│ BUILDING │  │  Agent                      │
│  │ discover │    │  planner │ │ builder  │◄─┤  [ builder               ]  │
│  └──────────┘    └──────────┘ └──────────┘  │                             │
│                                    │         │  Transition rules            │
│                                    ▼         │  REVIEW_FAILURES            │
│                               ┌──────────┐   │  → REVIEWING           [×] │
│                               │REVIEWING │   │  [+ Add rule]               │
│                               │ reviewer │   │                             │
│                               └──────────┘   │  Transition actions          │
│                                              │  BUILDING→REVIEWING:        │
│                                              │    commit  [×]              │
│                                              │  [+ Add action]             │
│                                              │                             │
│                                              │  [Delete state]             │
└──────────────────────────────────────────────┴─────────────────────────────┘
```

---

## 9. Flow editor — YAML tab

```
┌─ Flows / team.flow.yaml ───────────────────────────────────────────────────┐
│  [ Visual ]  [ YAML ]                                             [Save]   │
├────────────────────────────────────────────────────────────────────────────┤
│   1  version: 1                                                             │
│   2  flow: team                                                             │
│   3  storage_path: "pathly/plans/{topic}/"                                 │
│   4                                                                         │
│   5  states:                                                                │
│   6    - STORMING                                                           │
│   7    - PLANNING                                                           │
│   8    - BUILDING                                                           │
│   9    - REVIEWING                                                          │
│  10    - TESTING                                                            │
│  11    - DONE                                                               │
│  12                                                                         │
│  13  agent_map:                                                             │
│  14    STORMING: team/discover                                              │
│  15    PLANNING: team/plan                                                  │
│  16    BUILDING: team/build                                                 │
│  17    REVIEWING: team/review                                               │
│  18    TESTING: team/test                                                   │
│  19                                                                         │
│  20  transitions:                                                           │
│  21    STORMING:                                                            │
│  22      - PLANNING                                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Flow editor — YAML tab with parse error

```
┌─ Flows / team.flow.yaml ───────────────────────────────────────────────────┐
│  [ Visual ]  [ YAML ]                                          [Save ✗]   │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌─ ⚠ YAML error ──────────────────────────────────────────────────────┐  │
│  │  unexpected token at line 8: expected mapping value                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│   1  version: 1                                                             │
│   2  flow: team                                                             │
│   3                                                                         │
│   4  states:                                                                │
│   5    - STORMING                                                           │
│   6    - PLANNING                                                           │
│   7    - BUILDING                                                           │
│   8    - REVIEWING:                                    ← error here         │
│   9    - TESTING                                                            │
│  10    - DONE                                                               │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Monitor — running state

```
┌─ Monitor ──────────────────────────────────────────────────────────────────┐
│  Source: ● MCP live                                                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STORMING ✓   PLANNING ✓   [ BUILDING ]   reviewing   testing   done      │
│                                  ↑ active                                   │
│                                                                             │
│  Agent: builder     Conv 4       ● RUNNING                                  │
│                                                                             │
│  ┌─ Events ────────────────────────────────────────────────────────────┐   │
│  │  14:23:01  STATE_TRANSITION    PLANNING → BUILDING                  │   │
│  │  14:23:01  AGENT_SPAWN         builder                              │   │
│  │  14:31:44  COMPLETE_STAGE      called, decision=None                │   │
│  │  14:31:44  L1_CHECK            CONVERSATION_PROMPTS.md found        │   │
│  │  14:31:45  STATE_TRANSITION    BUILDING → REVIEWING          ◄ new  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  No feedback blocking.                                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Monitor — blocked state

```
┌─ Monitor ──────────────────────────────────────────────────────────────────┐
│  Source: ○ File watch                                                       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STORMING ✓   PLANNING ✓   BUILDING ✓   [ REVIEWING ]   testing   done   │
│                                                ↑                            │
│                                          ⚠ BLOCKED                         │
│                                                                             │
│  ┌─ Blocking feedback ─────────────────────────────────────────────────┐   │
│  │  REVIEW_FAILURES.md    routed to: builder                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─ Events ────────────────────────────────────────────────────────────┐   │
│  │  15:02:11  STATE_TRANSITION    BUILDING → REVIEWING                 │   │
│  │  15:02:12  FEEDBACK_WRITTEN    REVIEW_FAILURES.md                   │   │
│  │  15:02:12  BLOCKED             waiting for builder           ◄ new  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Monitor — no topic selected

```
┌─ Monitor ──────────────────────────────────────────────────────────────────┐
│  Source: ○ detecting...                                                     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│          Select a topic in the top bar to start monitoring.                 │
│                                                                             │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Publish — in progress

```
┌─ Pathly Studio ────────────────────── user-auth-refactor ▼  ● MCP live  [↑…]─┐
├────────────────┬──────────────────────────────────────────────────────────────┤
│                │                                                               │
│  (sidebar)     │          (main panel — editor or monitor)                    │
│                │                                                               │
├────────────────┴──────────────────────────────────────────────────────────────┤
│  ▲ Publishing ─────────────────────────────────────────────────────────────── │
│  Processing triggers for pathly-adapters...                                   │
│  Building wheels for collected packages: pathly-adapters                      │
│  Successfully built pathly-adapters                                           │
│  Installing collected packages: pathly-adapters                               │
│  ▌                                                           (streaming...)   │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Publish — success

```
┌─ Pathly Studio ────────────────────── user-auth-refactor ▼  ● MCP live  [↑ Publish]─┐
├────────────────┬─────────────────────────────────────────────────────────────────────┤
│                │                                                                      │
│  (sidebar)     │  ┌─ ✓ Published successfully ──────────────────────────────────┐   │
│                │  │  pathly-adapters 0.9.0 installed — changes live in Claude   │   │
│                │  └────────────────────────────────────────────────────────────┘   │
│                │                                                                      │
│                │          (main panel continues below)                               │
└────────────────┴─────────────────────────────────────────────────────────────────────┘
```

---

## 16. Settings panel

```
┌─ Settings ─────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Project path                                                               │
│  [ C:\Users\Yafit\pathly-adapters                                    ] [✓] │
│                                                                             │
│  Routing engine default                                                     │
│  ( ) Python FSM — deterministic, MCP-driven                                │
│  (●) LLM driven — orchestrator reads YAML                                  │
│                                                                             │
│  MCP server command                                                         │
│  [ pathly-mcp-server                                                 ]      │
│                                                                             │
│  Theme                                                                      │
│  [●] Dark   ( ) Light   ( ) System                                         │
│                                                                             │
│                                               [Save settings]               │
└────────────────────────────────────────────────────────────────────────────┘
```
