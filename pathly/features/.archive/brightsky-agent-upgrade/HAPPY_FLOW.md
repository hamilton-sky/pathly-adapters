---
name: Happy Flow
---
# BrightSky Agent Upgrade — Happy Flow

## Overview

A Pathly Studio user is stuck in BUILD conv 2. They open the HQ chat panel and ask BrightSky "what should I work on next?" The BrightSky agent queries Studio state, reads the failure files, reasons visibly in the Reasoning box, and responds with a concrete next step — all without the user leaving the chat.

---

## Step-by-Step Happy Flow

### Step 1: User asks a question
- **User does**: Types "what should I work on next?" in HQ chat, sends message
- **System does**: `brightskyClient.ts` assembles the message envelope with `messageType: 'pathly_chat'`, `fsmStage: 'BUILD'`, `activeConversation: 2`, `nextUncompletedStory: '...'`, sends via WebSocket
- **State after**: Backend receives Pathly-routed message; `PathlyRouterService` triggers with enriched system prompt

### Step 2: BrightSky agent calls list_plans
- **User does**: Nothing — agent is running
- **System does**: Backend sends `{ type: 'tool_call', toolName: 'studio.list_plans', callId: 'abc' }`; Studio receives it, calls `executeStudioTool('studio.list_plans', {})`, which calls `window.pathly.fs.listDirs(plansDir)`, returns `{ plans: [{ name: 'payment-api', fsmStage: 'BUILD', status: 'active' }] }`; Studio responds `{ type: 'tool_response', callId: 'abc', payload: { result, success: true } }`
- **State after**: Agent knows which features are active

### Step 3: BrightSky agent calls get_failures
- **User does**: Nothing
- **System does**: Backend sends `{ type: 'tool_call', toolName: 'studio.get_failures', parameters: { feature: 'payment-api', type: 'all' } }`; Studio reads `feedback/REVIEW_FAILURES.md` (finds content) and `feedback/TEST_FAILURES.md` (empty); returns both
- **State after**: Agent has full failure context

### Step 4: Extended thinking runs
- **User does**: Sees the thinking indicator in HQ (ThinkingBlock shows "Reasoning" collapsed, auto-collapses after response)
- **System does**: Claude API call fires with `thinking: { type: 'enabled', budget_tokens: 8000 }`; thinking content block arrives — `"User is in BUILD stage conv 2/4. Review failures mention missing error handler..."` — streamed as `<think>...</think>` stream_chunk before visible text; `brightskyClient.ts` receives it, `stream_end` calls `splitThinkingContent()`, populates `msg.thinking`
- **State after**: ThinkingBlock has real reasoning content; user can expand it

### Step 5: Response appears
- **User does**: Reads response: "You're in BUILD conv 2. The review failure is about missing error handling in `webhookService.ts`. Address that first — add a try/catch around the Stripe event handler and return 400 on parse failures."
- **System does**: Visible response streams word-by-word via stream_chunk; ThinkingBlock collapses 800ms after stream_end
- **State after**: User has a concrete action. No context switching.

### Step 6 (optional): Agent navigates Studio
- **User does**: Says "show me the monitor"
- **System does**: Backend sends `{ type: 'tool_call', toolName: 'studio.navigate_to', parameters: { panel: 'monitor' } }`; Studio calls `window.__pathlyNavigate('monitor')`; Monitor panel opens
- **State after**: User is on the Monitor panel, can see the current run

---

## End State

The user has a specific next action derived from real plan + failure context, saw real reasoning in the Reasoning box (same as Conductor), and can optionally have Studio navigated for them — all without leaving chat.

## Success Indicators
- [ ] `studio.list_plans` returns active features in < 500ms
- [ ] `studio.get_failures` returns non-empty content when failures exist
- [ ] ThinkingBlock shows real thinking text (not "Thinking…" spinner only)
- [ ] Visible response does NOT contain raw `<think>` tags
- [ ] `studio.navigate_to` opens the correct panel
