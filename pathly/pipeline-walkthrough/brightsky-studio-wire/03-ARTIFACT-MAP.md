# 03 — Artifact Map: brightsky-studio-wire

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
| REVIEW_FAILURES.md | Reviewer (conv 1) | Builder | Conv 1 architectural violations fixed |
| SCOPE_VIOLATION.md | Scope gate (conv 1) | Builder (4 cycles) | Out-of-scope file changes trimmed |
| TEST_FAILURES.md | Tester | Builder (fix cycle) | 5 failing criteria: dataLabel mismatch, navigate missing 'chat'/'terminal', stale S-03/S-08 criteria |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/lib/pathlyContextCollector.ts` | S-02 | New — collects FSM + plan context for every outbound message |
| `studio/src/renderer/src/lib/brightskyClient.ts` | S-01 S-02 S-03 S-04 S-06 | typing_metadata handler, capability handshake, context forwarding, reconnect backoff, tool_call round-trip |
| `studio/src/renderer/src/lib/studioAnalyzer.ts` | S-06 S-07 | New — tool registry: get_fsm_state, get_feature_plan, get_studio_schema, automation:executeStep |
| `studio/src/renderer/src/store/brightskyStore.ts` | S-01 S-06 | Added thinkingLabel, activeToolCall, setThinkingLabel, setActiveToolCall |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | S-01 S-06 | Thinking indicator bar, tool call status bar |
| `studio/src/renderer/src/components/ChatPanel/index.module.css` | S-01 S-06 | thinkingBar, toolCallBar styles |
| `studio/src/renderer/src/App.tsx` | S-10 | Registered __pathlyNavigate; supports 'monitor', 'chat', 'terminal' |
| `studio/src/main/automation/playwrightExecutor.ts` | S-09 S-10 | React-compatible fill (native setter), navigate action |
| `studio/src/renderer/src/types/global.d.ts` | S-10 | __pathlyNavigate type declaration |
| `studio/src/renderer/src/components/sidebar/shared/InlineCreateInput.tsx` | S-07 S-08 | dataLabel prop override; data-label="New Plan Name" for plan-folder case |
| `studio/src/renderer/src/components/sidebar/shared/InlineFolderInput.tsx` | S-08 | data-label="New Folder Name" |
| `studio/src/renderer/src/components/sidebar/shared/RenameInput.tsx` | S-08 | data-label="Rename Input" |
| `studio/src/renderer/src/components/sidebar/items/PlanSection.tsx` | S-07 S-08 | dataLabel="New Plan Name" on plan-folder InlineCreateInput; data-label="New Plan Folder" on button |
| `studio/src/renderer/src/components/ChatPanel/ChatInput/ChatInput.tsx` | S-08 | data-label on textarea and send button |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | S-08 | data-label on name, description, adapter toggles |
| `studio/src/renderer/src/components/FlowWizard/Step1Name/Step1Name.tsx` | S-08 | data-label on flow name and description inputs |
| `studio/src/renderer/src/components/FlowWizard/WizardFooter/WizardFooter.tsx` | S-08 | data-label="Create Flow" on save button |
| `studio/src/renderer/src/components/NewItemDialog.tsx` | S-08 | data-label on name, description, subdirectory, confirm button |
| `studio/src/renderer/src/components/topbar/PanelNav.tsx` | S-08 | data-label="Monitor" |
| `studio/src/renderer/src/components/topbar/index.tsx` | S-08 | data-label="Chat" on chat toggle |
| `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` | S-08 | data-label="Terminal" |
| `studio/src/renderer/src/components/ui/Button.tsx` | S-08 | data-label prop; type="button" |
| `studio/src/renderer/src/components/ui/IconButton.tsx` | S-08 | data-label prop |
| `backend/src/pathly/pathly.module.ts` | S-05 | New NestJS module |
| `backend/src/pathly/pathly-context-builder.service.ts` | S-05 | Builds plan-aware system prompt |
| `backend/src/pathly/pathly-router.service.ts` | S-05 S-06 | Routes pathly-studio messages to ChatAgent with tools |
| `backend/src/pathly/pathly-session.service.ts` | S-05 | In-memory capabilities store |
| `backend/src/pathly/types.ts` | S-05 | Shared types: AppContext, ClientCapabilities, BrightskyClientMessage |
| `backend/src/mcp/studio-bridge-tool.ts` | S-06 | New — StudioBridgeTool base + 3 concrete tool classes |
| `backend/src/mcp/mcp.module.ts` | S-06 | Registered 3 StudioBridgeTool instances |
| `backend/src/mcp/tool-registry.ts` | S-06 | Registered studio.* tools |
| `backend/src/chat/gateways/core/unified-chat.gateway.ts` | S-03 S-05 | client_capabilities handler; pathly-studio routing branch |
| `backend/src/app.module.ts` | S-05 | PathlyModule import |
| `.gitignore` | — | Added studio/tsconfig.node.tsbuildinfo |

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
pipeline-walkthrough/brightsky-studio-wire/  ←── metrics record → this folder
```
