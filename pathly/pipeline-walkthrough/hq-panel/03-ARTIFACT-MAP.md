# 03 — Artifact Map: hq-panel

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| REVIEW_FAILURES.md (Conv 1, round 1) | Reviewer | Builder | 9 violations: inline CSS var props, retryEnabled wrong state, no subtitle DOM element, aria-disabled spread pattern missing |
| TEST_FAILURES.md | Tester | Builder | 5 failures: S1.2 no subtitle, S1.7 retryEnabled wrong state, S1.7 startEnabled too broad, S1.8 inline style, S2.3 no optimistic clear |
| HUMAN_QUESTIONS.md | FSM gate | User (manual) | Gate blocked REVIEWING→TESTING: REVIEW.md artifact was missing from plan folder |

Preserved copies in: `pathly/pipeline-walkthrough/hq-panel/artifacts/`

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/store/runnerStore.ts` | S1.3, S1.4 | New Zustand store: status, stage, adapter, cost, session, decisionMenu, topic, projectRoot |
| `studio/src/renderer/src/components/HQ/index.tsx` | S1 | ChatPanel renamed to HQ; FlowControlBar + StageStatusStrip wired in |
| `studio/src/renderer/src/components/HQ/useHQ.tsx` | S2.1, S2.2 | SSE client for /events/runner (6 event types); /status fetch on mount |
| `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx` | S1.7 | 7 runner buttons (icons-only) with correct disabled logic; proper JSON bodies; noTopicWarning |
| `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css` | S1.7 | Icon-only btn sizing, primary/decision/abort variants, disabled opacity, separator |
| `studio/src/renderer/src/components/HQ/FlowControlBar/RunnerBtn.tsx` | S1.7 | New helper: Tooltip + button wrapper (extracted from FlowControlBar) |
| `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.tsx` | S1.7 | Sends `{ topic }` in abort POST body |
| `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.tsx` | S1.7 | Sends `{ topic, adapter }` in reroute POST body; CSS var via ref callback |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | S1.8, S2.9 | CSS custom property set via useEffect+setProperty (not inline style); live cost/session selectors |
| `studio/src/renderer/src/components/HQ/ChatHeader/ChatHeader.tsx` | S1.2 | Added always-visible subtitle span ("Pipeline Control") |
| `studio/src/renderer/src/components/HQ/ChatHeader/ChatHeader.module.css` | S1.2 | .subtitle style (11px, muted, 0.7 opacity) |
| `studio/src/renderer/src/components/HQ/PathlyMenuCard/PathlyMenuCard.tsx` | S2.3 | Decision mode: renders decision items when decisionMenu non-null; passes onRevert snapshot |
| `studio/src/renderer/src/components/HQ/PathlyMenuCard/DecisionButton.tsx` | S2.3 | Optimistic clear (onDone immediate); field name `decision` not `choice`; topic in POST body |
| `studio/src/renderer/src/components/HQ/PathlyMenuCard/PathlyMenuCard.module.css` | S2.3 | Decision item styles |
| `studio/src/renderer/src/lib/terminalOptions.tsx` | S1 | Single source of truth for TERMINAL_OPTIONS |
| `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` | S1 | Tab label updated to "HQ" |
| `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` | S1 | Import site updated for HQ rename |
| `studio/src/renderer/src/components/HQ/AutomationCard/AutomationCard.tsx` | S1 | Moved with folder rename |
| `studio/src/renderer/src/components/HQ/ChatInput/ChatInput.tsx` | S1 | Moved with folder rename |
| `.claude/settings.json` | — | Added PATHLY_PROJECT_ROOT env var to pathly-fsm MCP server config |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/hq-panel/  ←── metrics record → this folder
```
