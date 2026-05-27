# Chat/Automate Mode Toggle — Conversation Guide

Split into 2 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Store field + toggle pill UI (Pre-flight, Phases 1–2)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Chat/Automate Mode Toggle — Conversation 1 (Pre-flight + Phases 1–2) from
pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/chatStore.ts` — add chatMode field + setChatMode action
- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — add mode toggle pill to footer
- `studio/src/renderer/src/components/ChatPanel/ChatInput.module.css` — add toggle styles

**Pre-flight (do this first, do not skip):**
1. Grep for `isAutomationIntent` in `ChatPanel/index.tsx` — confirm it is defined but never consumed downstream in handleSend (no branches use it).
2. Grep for `automationPlan` in `ChatPanel/MessageList.tsx` — confirm AutomationCard render condition already exists.
3. Run `cd studio && npx tsc --noEmit` — record baseline error count before any changes.

**Phase 1 — chatStore.ts:**
Add `chatMode: 'chat' | 'automate'` to the `ChatState` interface and initial state (default `'chat'`).
Add `setChatMode: (mode: 'chat' | 'automate') => void` action.
Do NOT persist chatMode — it must reset to 'chat' on every app reload.

**Phase 2 — ChatInput.tsx + ChatInput.module.css:**
In the footer row, add a `[Chat] [Automate]` two-button pill between ModelSelector and the MiniLM pill.
Read chatMode and setChatMode from useChatStore.
Active button: accent green background + dark text (see IMPLEMENTATION_PLAN.md Phase 2 for exact CSS values).
Both buttons must have aria-pressed attributes.

Do NOT touch ChatPanel/index.tsx — that is Conversation 2.
Do NOT touch automationStore, MessageList, AutomationCard, or StepQueue.

Verify: `cd studio && npx tsc --noEmit` — must match baseline (0 new errors).
After done, update pathly/plans/chat-automate-toggle/PROGRESS.md Pre-flight + Phases 1–2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Footer shows `[Chat] [Automate]` pill. Clicking Automate lights it up in green. `chatStore.chatMode` changes. No regressions in TypeScript.
**Files touched:** `chatStore.ts`, `ChatInput.tsx`, `ChatInput.module.css`

---

## Conversation 2: Automation prompt + response wiring (Phases 3–4)

**Stories delivered:** S2.1, S2.2, S2.3, S2.4

**Prompt to paste:**
```
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Chat/Automate Mode Toggle — Conversation 2 (Phases 3–4) from
pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md.

Conversation 1 is complete: `chatStore.chatMode` exists, the toggle pill renders.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — automation branch in handleSend

**Phase 3 — Automation system prompt branch:**
1. Remove the unused `isAutomationIntent` const (grep first to find exact location).
2. Read `chatMode` via `useChatStore.getState().chatMode` inside handleSend (not via hook — this is async).
3. Add the `buildAutomationPrompt(schema: StudioElement[])` helper above handleSend (see IMPLEMENTATION_PLAN.md Phase 3 for exact prompt text).
4. In handleSend, after context fetch, branch on chatMode:
   - `'automate'`: skip match card (setCurrentMatch(null), setAltMatches([])), build automation system prompt, call LLM
   - `'chat'`: existing flow — do not change a single line of the chat path
5. The `StudioElement` type comes from pathlyContext — check existing imports before adding.

**Phase 4 — Parse JSON response + wire stores:**
1. Add `parseAutomationResponse(text: string)` helper (see IMPLEMENTATION_PLAN.md Phase 4 for exact implementation — handles markdown code fences, validates type/intent/steps fields).
2. In the automation LLM branch, after fullText is complete (in BOTH Ollama and node-llama-cpp paths):
   - Call parseAutomationResponse(fullText)
   - On success: call automationStore.reset(), automationStore.setSteps(parsed.steps), updateLastMessage({ content: '', automationPlan: { intent, steps }, status: 'done' })
   - On failure: updateLastMessage({ content: fullText.trim() || '_(no response)_', status: 'done' })
3. Read automationStore via `useAutomationStore.getState()` inside handleSend (not via hook).
4. Check if `useAutomationStore` is already imported at the top — grep before adding to avoid duplicates.
5. Each step must have `id: crypto.randomUUID()` assigned in parseAutomationResponse before setSteps.

Do NOT change MessageList, AutomationCard, StepQueue, or automationStore — they already work.
Do NOT touch any other file outside ChatPanel/index.tsx.

Verify: `cd studio && npx tsc --noEmit` — must be 0 errors.
After done, update pathly/plans/chat-automate-toggle/PROGRESS.md Phases 3–4 to DONE.
Write pathly/plans/chat-automate-toggle/VERIFY.md with first line `RESULT: PASS` and one-line summary of what was tested.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Switching to Automate and sending "create a checkout flow" triggers LLM with the automation prompt. Response JSON is parsed and `AutomationCard` appears in the message list. `automationStore.steps` is populated. Chat mode still works exactly as before.
**Files touched:** `ChatPanel/index.tsx`
