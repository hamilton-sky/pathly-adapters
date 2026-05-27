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

---

## Conversation 3: Named action registry (Phases 5–6)

**Stories delivered:** S3.1, S3.2

**Prompt to paste:**
```
Read pathly/plans/chat-automate-toggle/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Chat/Automate Mode Toggle — Conversation 3 (Phases 5–6) from
pathly/plans/chat-automate-toggle/IMPLEMENTATION_PLAN.md.

Conversations 1 and 2 are complete: the toggle works, LLM generates JSON steps using raw click/fill labels.
Conversation 3 replaces raw labels with a named action registry.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/automation/pathlyActionRegistry.ts` — CREATE
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — update buildAutomationPrompt + parseAutomationResponse

**Phase 5 — pathlyActionRegistry.ts (CREATE):**
Create `studio/src/renderer/src/automation/pathlyActionRegistry.ts` (create the `automation/` directory if it does not exist).
Define `PathlyActionDef` interface, `PATHLY_ACTIONS` array, `REGISTRY_PROMPT_BLOCK` string, and `expandAction(name, params)` function.
See IMPLEMENTATION_PLAN.md Phase 5 for the exact TypeScript — copy it verbatim, then confirm it compiles.
Initial registry must include these 5 actions: `pathly_plan_feature`, `pathly_run_storm`, `pathly_run_build`, `pathly_run_review`, `pathly_run_test`.
Do NOT invent Studio labels — use the labels exactly as they appear in `studioSchema.ts` (grep for it to confirm).

**Phase 6 — Update buildAutomationPrompt + parseAutomationResponse:**
1. Import `REGISTRY_PROMPT_BLOCK` and `expandAction` from `'../automation/pathlyActionRegistry'` (adjust relative path if needed).
2. Replace `buildAutomationPrompt(schema: StudioElement[])` with the zero-arg version from IMPLEMENTATION_PLAN.md Phase 6 — it injects REGISTRY_PROMPT_BLOCK and uses the new step JSON shape `{ "action": "<name>", "params": {...} }`.
3. Update the handleSend automation branch call: `buildAutomationPrompt()` (no argument).
4. Update `parseAutomationResponse` to parse the new RawStep shape and call `expandAction` per step. See IMPLEMENTATION_PLAN.md Phase 6 for exact implementation.
5. If all steps produce empty expansion (concreteSteps.length === 0), return null to trigger the chat fallback.
6. Remove the `studioSchema` parameter from the automation prompt path. The `studioSchema` variable may still exist in the file for the chat path — do not remove it from there.

Do NOT change MessageList, AutomationCard, StepQueue, automationStore, or the chat path.
Do NOT touch any other file outside the two listed above.

Verify: `cd studio && npx tsc --noEmit` — must be 0 errors.
After done, update pathly/plans/chat-automate-toggle/PROGRESS.md Phases 5–6 to DONE.
Write pathly/plans/chat-automate-toggle/VERIFY.md with first line `RESULT: PASS` and one-line summary.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Switching to Automate and sending "run storm then build" produces an AutomationCard whose steps expand from named registry actions (`pathly_run_storm`, `pathly_run_build`). Unknown action names are silently skipped. Chat mode is unchanged. TypeScript: 0 errors.
**Files touched:** `automation/pathlyActionRegistry.ts` (new), `ChatPanel/index.tsx`
