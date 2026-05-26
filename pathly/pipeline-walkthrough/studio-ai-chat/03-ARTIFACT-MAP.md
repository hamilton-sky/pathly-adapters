# 03 — Artifact Map: studio-ai-chat

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| REVIEW.md | Orchestrator | FSM gate | Review summary — required for REVIEWING→TESTING |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| feedback/REVIEW_FAILURES.md (×8) | Reviewer | Builder | Impl violations: layer contracts, missing exports, raw setState, dynamic imports |
| SCOPE_VIOLATION.md (×5) | Scope gate | Orchestrator (manual) | tsconfig.tsbuildinfo + undeclared source files exceeded declared scope |
| feedback/ARCH_FEEDBACK.md (×1) | Reviewer | Architect | embedRouter.ts architectural concern (Conv 5) |
| HUMAN_QUESTIONS.md (×1) | Orchestrator | User | Conv 0 review exceeded 2-retry limit; human accepted item 1, fixed item 2 |
| feedback/TEST_FAILURES.md (×1) | Tester | Builder | S9.3: selectedModelId not passed to askWebLLM |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `studio/src/main/index.ts` | S9.1–S9.4 | Added WebGPU command-line switches + experimentalFeatures |
| `studio/src/main/automation/playwrightExecutor.ts` | S7.1–S7.3 | NEW: 3-tier Playwright element cascade (label/aria → fuzzy → LLM embedding) |
| `studio/src/main/ipc/automation.ts` | S7.1–S7.3 | NEW: IPC handler for automation:executeStep with validation |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | S2.2, S3.2, S4.1, S5.2, S8.4, S9.3 | Core chat + WebLLM wiring + automation intent detection |
| `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` | S2.1, S9.1 | Header pills + ModelSelector trigger |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | S2.2, S9.4 | Input bar + model pill reads modelStore |
| `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx` | S9.1–S9.2 | NEW: model picker dropdown with cache toggle, badges, progress bar |
| `studio/src/renderer/src/components/ChatPanel/ModelSelector.module.css` | S9.1–S9.2 | NEW: CSS for ModelSelector |
| `studio/src/renderer/src/components/ChatPanel/AutomationCard.tsx` | S8.1–S8.2 | NEW: automation intent card (Run All / Step-by-Step) |
| `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx` | S8.1–S8.2 | NEW: step queue UI for staged/auto execution |
| `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` | S2.1 | Panel layout + resize styles |
| `studio/src/renderer/src/store/chatStore.ts` | S2.2, S5.2, S8.1 | Messages + match state + automation plan |
| `studio/src/renderer/src/store/automationStore.ts` | S8.1–S8.2 | NEW: step queue state with staged/auto mode |
| `studio/src/renderer/src/store/modelStore.ts` | S9.1, S9.4 | NEW: selectedModelId + cachedModelIds + downloadProgress, persisted |
| `studio/src/renderer/src/lib/embedRouter.ts` | S5.1–S5.3 | NEW: MiniLM wrapper + matchIntent + preEmbedSkills + cosineSim |
| `studio/src/renderer/src/lib/pathlyContext.ts` | S4.1–S4.2 | NEW: FSM context builder (GET /status) |
| `studio/src/renderer/src/lib/studioSchema.ts` | S6.1–S6.2 | NEW: static Studio UI schema (97 elements) |
| `studio/src/renderer/src/lib/webLLMEngine.ts` | S9.2–S9.3 | NEW: WebLLM engine singleton + streaming askWebLLM |
| `studio/src/renderer/src/lib/elementResolver.ts` | S7.3 | NEW: renderer-side semantic resolver (embed + cosine similarity) |
| `studio/src/renderer/src/data/skills.json` | S5.1–S5.2 | NEW: 14 Pathly skills with name/command/description |
| `studio/src/renderer/src/data/models.ts` | S9.1 | NEW: 4 WebLLM model definitions + RECOMMENDED_MODEL_ID |
| `studio/src/renderer/src/types/automation.ts` | S8.1–S8.2 | NEW: canonical AutomationStep + AutomationStepStatus types |
| `studio/src/renderer/src/types/global.d.ts` | S7.2 | Added window.pathly.automation namespace |
| `src/pathly_orchestrator/http_server.py` | S1.1, S8.4 | Added GET /status + POST /chat routes |
| `src/pathly_orchestrator/chat_agent.py` | S8.4 | NEW: heuristic chat handler + automation intent detection |
| `studio/package.json` | S9.2 | Added @mlc-ai/web-llm ^0.2.83 |

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
REVIEW.md                ←── reviewer PASS summary (FSM gate artifact)
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/studio-ai-chat/  ←── metrics record → this folder
```
