# studio-ui-fixes — Flow Diagram

## Data flow: Monitor pipeline rendering (after fix)

```
activeTopic selected
       │
       ▼
Monitor/index.tsx  useEffect
       │
       ├──► readFile(STATE.json)
       │          │
       │          ▼
       │    setFsmState({state, flow, ...})
       │          │
       │          ▼
       │    readFile(flows/{flow}.flow.yaml)
       │          │
       │          ▼
       │    regex parse states: [...]
       │          │
       │          ▼
       │    setPipelineStates(states[])   ──► projectStore.pipelineStates
       │
       ├──► readFile(EVENTS.jsonl)
       │          │
       │          ▼
       │    parse all lines (no .slice(-50))
       │          │
       │          ▼
       │    setEvents(FsmEvent[])         ──► projectStore.events
       │
       ▼
FsmView reads pipelineStates from store
       │
       ▼
renders: ✓ STORMING  ✓ PLANNING  ● BUILDING  reviewing  testing  done

EventLog reads events from store
       │
       ▼
per event: formatTime(ev.ts?) | ev.type | eventDetail(ev)
                                               │
                              from+to ─────────┤
                              reason ──────────┤
                              detail ──────────┘
```

## Data flow: Sidebar PLAN section (after fix)

```
activeTopic selected
       │
       ▼
usePlanConversations
       │
       ▼
readFile(PROGRESS.md)
       │
       ▼
parseProgressMd — scope to ## Conversation Breakdown section only
       │
       ▼
[{num:1, title:"1–2", status:"TODO"}, {num:2, title:"3–4", status:"TODO"}]
       │
       ▼
Sidebar PLAN section renders clean rows (no Phase Detail rows, no Verify commands)
```

## Sidebar sections (after fix)

```
Sidebar
  ▼ PLAN [topic]
    ○ Conv 1 — 1–2  TODO
    ○ Conv 2 — 3–4  TODO
  ─────────────────────
  ▶ FLOWS
  ▶ SKILLS
  ▶ AGENTS
  ▼ TEMPLATES
      plan/
        PROGRESS.template.md
  ─────────────────────
  ▼ DEBUGS
    ▶ missing-inputs-in-meta-schema/
    ▶ claude-hooks-not-registered/
  ▼ EXPLORATIONS
    ▶ architecture-risk-assessment/
    ▶ pathly-system-health/
  ─────────────────────
  ● Monitor
  ⚙ Settings
```
