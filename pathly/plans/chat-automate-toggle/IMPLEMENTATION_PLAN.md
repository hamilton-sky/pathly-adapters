# Chat/Automate Mode Toggle — Implementation Plan

## Overview

Adds an explicit `[Chat | Automate]` mode toggle to the Conductor's input footer. When Automate
is active, `handleSend()` builds an automation-specific system prompt (including `studioSchema`),
sends it to the local LLM, parses the JSON response into `{ intent, steps[] }`, populates the
`AutomationCard` via `updateLastMessage({ automationPlan })`, and calls
`automationStore.setSteps()`. Chat mode is unchanged.

## Layer Architecture

```
ChatInput (UI toggle pill)
     │  reads/writes chatStore.chatMode
     ▼
chatStore.ts  →  chatMode: 'chat' | 'automate'
     │
     ▼
ChatPanel/index.tsx  (handleSend)
     │  if chatMode === 'automate'  →  buildAutomationPrompt(studioSchema)
     │  if chatMode === 'chat'      →  existing flow (unchanged)
     ▼
Local LLM (Ollama or node-llama-cpp)
     │  streams JSON { type: "automation", intent, steps[] }
     ▼
parseAutomationResponse(fullText)
     │  success → updateLastMessage({ automationPlan }) + automationStore.setSteps()
     │  failure → updateLastMessage({ content: fullText }) (chat fallback)
     ▼
MessageList → AutomationCard → StepQueue (existing components, no changes)
```

---

## Pre-flight   ← Conversation: 1

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx`
**Done when:** Confirm `isAutomationIntent` is defined but never used in `handleSend`, and that `AutomationCard` already reads `msg.automationPlan`. Record any TypeScript baseline errors with `cd studio && npx tsc --noEmit`.
**Details:**
- Grep for `isAutomationIntent` — confirm it is on a single line (~281) with no downstream usage
- Grep for `automationPlan` in `MessageList.tsx` — confirm `AutomationCard` render condition exists
- Grep for `setSteps` in `ChatPanel/index.tsx` — confirm it is never called (zero results)
- Run `cd studio && npx tsc --noEmit` — record baseline (should be 0 errors)

---

## Phase 1: Add `chatMode` to chatStore   ← Conversation: 1

**File:** `studio/src/renderer/src/store/chatStore.ts` — MODIFY
**Done when:** `useChatStore((s) => s.chatMode)` returns `'chat'` and `useChatStore((s) => s.setChatMode)` is callable without TypeScript errors
**Delivers:** S1.2
**Depends on:** nothing
**Enables:** Phase 2 (toggle reads this field), Phase 3 (handleSend branches on it)
**Details:**
- Add to `ChatState` interface:
  ```ts
  chatMode: 'chat' | 'automate'
  setChatMode: (mode: 'chat' | 'automate') => void
  ```
- Add to initial state: `chatMode: 'chat'`
- Add action: `setChatMode: (mode) => set({ chatMode: mode })`
- Do NOT persist — mode resets to `'chat'` on reload by design
**Verify:** `cd studio && npx tsc --noEmit`

---

## Phase 2: Mode toggle pill in ChatInput footer   ← Conversation: 1

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — MODIFY
**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.module.css` — MODIFY
**Done when:** Footer row shows `[Chat] [Automate]` pill; clicking each button updates chatStore and the active button shows accent styling
**Delivers:** S1.1
**Depends on:** Phase 1
**Enables:** Phase 3 (handleSend reads chatMode)
**Details:**

`ChatInput.tsx`:
- Import `useChatStore`
- Read `chatMode` and `setChatMode` from store
- In the footer row, add a mode toggle group between `ModelSelector` and the MiniLM pill:
  ```tsx
  <div className={styles.modeToggle}>
    <button
      className={`${styles.modeBtn} ${chatMode === 'chat' ? styles.modeBtnActive : ''}`}
      onClick={() => setChatMode('chat')}
      aria-pressed={chatMode === 'chat'}
    >Chat</button>
    <button
      className={`${styles.modeBtn} ${chatMode === 'automate' ? styles.modeBtnActive : ''}`}
      onClick={() => setChatMode('automate')}
      aria-pressed={chatMode === 'automate'}
    >Automate</button>
  </div>
  ```

`ChatInput.module.css`:
```css
.modeToggle {
  display: flex;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}

.modeBtn {
  font-size: 10px;
  font-family: monospace;
  padding: 3px 8px;
  background: none;
  border: none;
  cursor: pointer;
  color: #6b7280;
  transition: background 120ms, color 120ms;
}

.modeBtn:hover {
  color: #9ca3af;
}

.modeBtnActive {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}
```
**Verify:** `cd studio && npx tsc --noEmit`

---

## Phase 3: Automation system prompt + LLM branch   ← Conversation: 2

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY
**Done when:** When `chatMode === 'automate'`, `handleSend` sends a different system prompt to the LLM and does not call `setCurrentMatch` / `setAltMatches`; when `chatMode === 'chat'` the existing flow is unchanged
**Delivers:** S2.1, S2.4
**Depends on:** Phase 1
**Enables:** Phase 4 (response parsing)
**Details:**

1. Remove the unused `isAutomationIntent` const (~line 281 — grep to confirm exact location before deleting).

2. Read `chatMode` from chatStore at the top of `handleSend`:
   ```ts
   const chatMode = useChatStore.getState().chatMode
   ```

3. Add `buildAutomationPrompt` helper above `handleSend`:
   ```ts
   function buildAutomationPrompt(schema: StudioElement[]): string {
     const schemaBlock = schema.length > 0
       ? `\n\n## Studio UI Elements (use ONLY these labels in steps)\n${
           schema.slice(0, 30).map((el) => `- ${el.screen}: ${el.label} (${el.type})`).join('\n')
         }`
       : ''
     return `You are a UI automation assistant for Pathly Studio.
   The user will describe a task. Return ONLY valid JSON (no markdown, no explanation):
   {
     "type": "automation",
     "intent": "<one-line description of what you will do>",
     "steps": [
       { "description": "<human-readable label>", "action": { "type": "click"|"fill"|"select", "label": "<Studio element label>", "value": "<only for fill/select>" } }
     ]
   }
   Use only element labels listed below. Do not invent labels.${schemaBlock}`
   }
   ```

4. In `handleSend`, after embedding + context fetch, branch on `chatMode`:
   ```ts
   if (chatMode === 'automate') {
     // skip match card entirely
     setCurrentMatch(null)
     setAltMatches([])
     const systemPrompt = buildAutomationPrompt(context.studioSchema ?? [])
     // ... LLM call (Phase 4 adds the response handler)
   } else {
     // existing chat flow — untouched
   }
   ```

5. The `StudioElement` type is already imported via `pathlyContext` — confirm import path before adding.
**Verify:** `cd studio && npx tsc --noEmit`

---

## Phase 4: Parse JSON response + wire stores   ← Conversation: 2

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY (continues Phase 3)
**Done when:** A message sent in Automate mode produces an `AutomationCard` in the message list and `automationStore.steps` is populated
**Delivers:** S2.2, S2.3, S2.4
**Depends on:** Phase 3
**Enables:** existing `StepQueue` + `AutomationCard` components (no changes needed there)
**Details:**

Add `parseAutomationResponse` helper:
```ts
function parseAutomationResponse(text: string): { intent: string; steps: AutomationStep[] } | null {
  try {
    // strip possible markdown code fences
    const clean = text.replace(/^```[a-z]*\n?/m, '').replace(/```$/m, '').trim()
    const obj = JSON.parse(clean) as { type?: string; intent?: string; steps?: unknown[] }
    if (obj.type !== 'automation' || !obj.intent || !Array.isArray(obj.steps)) return null
    const steps = obj.steps.map((s: unknown) => {
      const step = s as { description?: string; action?: { type?: string; label?: string; value?: string } }
      return {
        id: crypto.randomUUID(),
        description: step.description ?? '',
        action: step.action ?? { type: 'click', label: '' },
        status: 'pending' as const,
      }
    })
    return { intent: obj.intent, steps }
  } catch {
    return null
  }
}
```

In the automation LLM branch (both Ollama and node-llama-cpp paths), after streaming completes:
```ts
const parsed = parseAutomationResponse(fullText)
if (parsed) {
  automationStore.reset()
  automationStore.setSteps(parsed.steps)
  updateLastMessage({
    content: '',
    automationPlan: { intent: parsed.intent, steps: parsed.steps },
    status: 'done',
  })
} else {
  // LLM returned plain text — show as chat message
  updateLastMessage({ content: fullText.trim() || '_(no response)_', status: 'done' })
}
```

Import `useAutomationStore` at the top of the file (it may already be imported — grep before adding).
Read `automationStore` via `useAutomationStore.getState()` inside `handleSend` (not via hook, since this is inside an async function).
**Verify:** `cd studio && npx tsc --noEmit`

---

## Prerequisites
- `studio/src/renderer/src/store/automationStore.ts` exists with `setSteps`, `reset` actions (confirmed)
- `AutomationCard` already renders when `msg.automationPlan` is set (confirmed)
- `buildPathlyContext()` already returns `studioSchema` (confirmed)
- Baseline TypeScript: 0 errors (`cd studio && npx tsc --noEmit`)

## Key Decisions
- **Explicit toggle over regex detection:** The previous `isAutomationIntent` regex fires on ambiguous phrases ("create a new step" in a planning conversation). Explicit user intent eliminates false positives entirely.
- **No mode persistence:** Mode resets to `'chat'` on reload. Automation is a deliberate act — defaulting to it on restart could surprise users.
- **JSON fallback to chat:** If the LLM returns plain text in Automate mode, we show it as a chat message. This is safer than crashing or showing a broken AutomationCard.
- **Automation prompt streams but only parses on done:** We don't try to parse partial JSON during streaming. The `content` field streams for user feedback; `parseAutomationResponse` runs only on the final `fullText`.
