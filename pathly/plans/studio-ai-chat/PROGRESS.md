# Studio AI Chat — Progress

## Status: DONE

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S0.1 | Terminal dock is compact and IDE-style | Conv 0 | DONE |
| S0.2 | Sessions and launchers have clear visual hierarchy | Conv 0 | DONE |
| S0.3 | ALLOWED_SHELLS accepts claude and codex | Conv 0 | DONE |
| S1.1 | GET /status endpoint returns FSM state | Conv 1 | DONE |
| S1.2 | System prompt includes active Pathly context | Conv 1 | DONE |
| S2.1 | Collapsible + resizable Conductor panel | Conv 2 | DONE |
| S2.2 | Chat streams responses via POST /chat (SSE) | Conv 2 | DONE |
| S2.3 | Skills panel shows all 14 skills as chips | Conv 2 | DONE |
| S2.4 | Empty state guides user to start a new flow | Conv 2 | DONE |
| S3.1 | MatchCard shows matched skill + confidence | Conv 3 | DONE |
| S3.2 | Run writes skill command to terminal tab | Conv 3 | DONE |
| S4.1 | Context includes FSM stage + screen state | Conv 4 | DONE |
| S4.2 | Skills list always in context | Conv 4 | DONE |
| S5.1 | MiniLM loads at startup | Conv 5 | DONE |
| S5.2 | Embedding matches intent to Pathly skill | Conv 5 | DONE |
| S5.3 | Low-confidence state guides user to correct skill | Conv 5 | DONE |
| S6.1 | AI receives static schema of Studio UI elements | Conv 6 | DONE |
| S6.2 | AI system prompt includes Studio UI context | Conv 6 | DONE |
| S7.1 | Playwright executor connects to Electron window | Conv 7 | DONE |
| S7.2 | AI can click, fill, or select any Studio element by label | Conv 7 | DONE |
| S7.3 | Step execution is reliable across UI changes | Conv 7 | DONE |
| S8.1 | Staged mode with per-step approval | Conv 8 | DONE |
| S8.2 | Auto mode executes full plan | Conv 8 | DONE |
| S8.3 | Auto mode blocked on low confidence | Conv 8 | DONE |
| S8.4 | Full flow creation from plain-English description | Conv 8 | DONE |
| S9.1 | Model selector shows all models with specs | Conv 9 | DONE |
| S9.2 | Model download and cache via toggle | Conv 9 | DONE |
| S9.3 | Selected model used for all AI responses | Conv 9 | DONE |
| S9.4 | Model selection persists across restarts | Conv 9 | DONE |

## Conversation Breakdown

| Conv | Phases | Track | Stories | Status | Verify |
|------|--------|-------|---------|--------|--------|
| 0 | 0a–0c | Core | S0.1, S0.2, S0.3 | DONE | `cd studio && npm run typecheck` + visual check in Studio |
| 1 | 1 | Core | S1.1, S1.2 | DONE | `curl http://127.0.0.1:8765/status` |
| 2 | 4–8 | Core | S2.1, S2.2, S2.3, S2.4 | DONE | `cd studio && npm run typecheck` |
| 3 | 9–11 | Core | S3.1, S3.2 | DONE | `cd studio && npm run typecheck` |
| 4 | 12–14 | Core | S4.1, S4.2 | DONE | `cd studio && npm run typecheck` |
| 5 | 15–18 | Core | S5.1, S5.2, S5.3 | DONE | `cd studio && npm run typecheck` |
| 6 | 19–20 | Track A | S6.1, S6.2 | DONE | `cd studio && npm run typecheck` + inspect POST /chat body includes studioSchema |
| 7 | 21–22 | Track A | S7.1, S7.2, S7.3 | DONE | `cd studio && npm run typecheck` + devtools: `window.electronAPI.executeAutomationStep({ type: 'click', label: 'New Flow' })` |
| 8 | 24–26 | Track A | S8.1, S8.2, S8.3, S8.4 | DONE | E2E: type "create a test flow" → approve steps → flow appears in Studio |
| 9 | 27–29 | Track B | S9.1, S9.2, S9.3, S9.4 | DONE | Select Phi-4 Mini → download → send message → response streams from WebLLM |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 0 | 0a | `studio/src/main/ipc/terminal.ts` | Add claude+codex to ALLOWED_SHELLS | Terminal tabs launch without "Shell not allowed" | DONE |
| 0 | 0b | `Terminal/index.tsx` + CSS | Compact dock: 180px default, 72px empty, inline launchers | No blank dead zone, launch buttons visible | DONE |
| 0 | 0c | `Terminal/PaneTabBar.tsx` + CSS | Sessions vs launchers hierarchy, active tab styling | Clear visual separation, active tab legible | DONE |
| 1 | 1 | `src/pathly_orchestrator/http_server.py` | Add GET /status (read-only FSM state, no side effects) | curl returns { current_state, feature, project_root } | DONE |
| 1 | ~~2~~ | ~~chat_agent.py~~ | **REMOVED** — WebLLM pivot | — | REMOVED |
| 1 | ~~3~~ | ~~chat_tools.py~~ | **REMOVED** — WebLLM pivot | — | REMOVED |
| 2 | 4 | `store/chatStore.ts` | Zustand store — messages + match state | No TS errors | DONE |
| 2 | 5 | `store/uiStore.ts` | Add chatOpen, skillsPanelOpen | State persists across remounts | DONE |
| 2 | 6 | `ChatPanel/ConductorHeader.tsx` | Header + CLI pills + Clear Chat button | Pills show active/idle; clear works | DONE |
| 2 | 7 | `ChatPanel/SkillsPanel.tsx` | Skill chips grid + collapse (max-height: 100px) | All 14 chips render, chip click works | DONE |
| 2 | 8 | `MessageList.tsx` + `ChatInput.tsx` + `ChatPanel/index.tsx` | Messages + input bar + resize hook | Streaming works; panel draggable 260–720px | DONE |
| — | — | `ChatPanel/useChatResize.ts` | Left-edge drag handle (260–720px, persisted in localStorage) | Width persists across reloads | DONE |
| 3 | 9 | `ChatPanel/MatchCard.tsx` | Match result card | Green/amber states, Run/Not this work | DONE |
| 3 | 10 | `ChatPanel/OutputSnippet.tsx` | Live PTY output reader | Shows last 5 lines in real-time | DONE |
| 3 | 11 | `lib/launchTerminal.ts` + `chatStore.targetKind` | Terminal write + auto-spawn (uses \r for Windows PTY) | Run executes cmd; auto-spawns + opens dock | DONE |
| 4 | 12 | `lib/pathlyContext.ts` | Context builder with studioSchema | Returns { fsmStage, featureName, skills, studioSchema } | DONE |
| 4 | ~~13~~ | ~~PageAnalyzer copy~~ | **REMOVED** — superseded by static schema (Conv 6) | — | REMOVED |
| 4 | 14 | `ChatPanel/index.tsx` | Inject context into every message | AI references FSM stage | DONE |
| 5 | 15 | `data/skills.json` | 14 skills with name+command+description | File valid JSON, all skills present | DONE |
| 5 | 16 | `lib/skillsManifest.ts` | Typed loader for skills.json | No TS errors | DONE |
| 5 | 17 | `lib/embedRouter.ts` | MiniLM wrapper + matchIntent() + embed() exported | Returns top-3 matches with scores | DONE |
| 5 | 18 | `ChatPanel/index.tsx` + `chatStore.ts` | Wire embedding into send flow; /pathly commands route silently | MatchCard renders < 50ms; no YOU message for /pathly | DONE |
| 6 | 19 | `lib/studioSchema.ts` + `types/studio.ts` | Static Studio UI schema (lib canonical; data/ is re-export shim) | No TS errors, schema covers all key elements | DONE |
| 6 | 20 | `lib/pathlyContext.ts` | Inject schema into AI context | POST /chat body includes studioSchema | DONE |
| 7 | 21 | `main/automation/playwrightExecutor.ts` | Playwright executor — 3-tier cascade + self-healing | executeStep click/fill/select works | DONE |
| 7 | 21.5 | `lib/elementResolver.ts` | Renderer-side semantic+LLM resolution (uses embed+cosineSim from embedRouter) | IPC listeners registered at startup | DONE |
| 7 | 22 | `main/ipc/automation.ts` | IPC handler + round-trip for Tier 2/3 | ipcRenderer.invoke executes step via Playwright | DONE |
| 8 | 24 | `store/automationStore.ts` | Step queue state | No TS errors | DONE |
| 8 | 25 | `ChatPanel/StepQueue.tsx` + `AutomationCard.tsx` | Staged/auto UI components | Staged approve/skip works visually | DONE |
| 8 | 26 | `ChatPanel/index.tsx` + `chat_agent.py` | Wire AI → action plan → execution | Full flow creation E2E works | DONE |
| 9 | 27 | `data/models.ts` | Model definitions (Ollama + node-llama-cpp GGUF) | Models list correct, recommended set | DONE |
| 9 | 28 | `store/modelStore.ts` + `ChatPanel/ModelSelector.tsx` | Model selector UI | Download, cache, selection all work | DONE |
| 9 | 29 | `ChatPanel/index.tsx` | Wire Ollama/node-llama-cpp into chat flow | Responses stream from local model | DONE |

## Post-Pipeline Additions

| Addition | Files | Description | Status |
|----------|-------|-------------|--------|
| Reasoning/ThinkingBlock | `lib/thinkingParser.ts`, `ChatPanel/ThinkingBlock.tsx`, `ChatPanel/ThinkingBlock.module.css` | Inline collapsible `<think>` block; parses DeepSeek-R1 / Qwen3 reasoning tokens from stream | DONE |
| `thinking` field on Message | `store/chatStore.ts` | `thinking?: string` added to Message type | DONE |
| Stream parser wired to both LLM paths | `ChatPanel/index.tsx` | `splitThinkingContent()` called on every chunk for Ollama + node-llama-cpp | DONE |
| Model lineup updated | `data/models.ts`, `main/ipc/llm.ts` | llama-3.2-3b replaced with deepseek-r1-1.5b; qwen3-4b is now recommended; `thinking` field added to Model interface | DONE |
| phi-4-mini GGUF URI corrected | `main/ipc/llm.ts` | Removed erroneous `microsoft_` prefix from bartowski repo path | DONE |

## Hotfixes Applied (post-pipeline)

| Fix | File | Issue | Status |
|-----|------|-------|--------|
| /pathly commands appeared as YOU messages | `ChatPanel/index.tsx` | `addMessage` called before /pathly check | FIXED |
| Windows PTY not executing commands | `lib/launchTerminal.ts` | `\n` → `\r` for Windows PTY Enter | FIXED |
| ChatInput hidden by SkillsPanel | `ChatPanel/SkillsPanel.module.css` | Added `max-height: 100px; overflow-y: auto` to `.chips` | FIXED |
| Doubled /pathly prefix in terminal | `lib/launchTerminal.ts` | Removed prepend — skills.json commands already include it | FIXED |
| ModelSelector moved inline to footer | `ChatPanel/index.tsx` | Placed beside MiniLM status pill in input footer row | FIXED |

## Prerequisites
- [x] FSM server running (port 8765) — Conv 1 done
- [x] MiniLM auto-downloads on first launch (~22MB, transformers.js) — Conv 5 done
- [x] @playwright/test — added to studio/package.json in Conv 7
- [ ] WebLLM models download on first cache (Phi-4 Mini ~2GB) — Conv 9
