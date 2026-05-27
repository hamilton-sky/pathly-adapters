# Chat/Automate Mode Toggle — Edge Cases

## Category 1: LLM JSON Failures

### EC-1.1: LLM returns plain text instead of JSON
- **Trigger**: Model ignores the JSON system prompt and responds conversationally
- **Current behavior**: `JSON.parse` throws; without a guard this would crash or leave AutomationCard broken
- **Expected behavior**: `parseAutomationResponse` returns `null` → message shown as plain chat text
- **Handled in**: Phase 4 — `parseAutomationResponse` wraps JSON.parse in try/catch; null path calls `updateLastMessage({ content: fullText })`

### EC-1.2: LLM wraps JSON in markdown code fences
- **Trigger**: Model outputs ```json\n{...}\n``` — common with instruction-tuned models
- **Expected behavior**: Code fence stripped before parsing (`text.replace(/^```[a-z]*\n?/m, '')`)
- **Handled in**: Phase 4 — `parseAutomationResponse` strips fences before `JSON.parse`

### EC-1.3: LLM returns valid JSON but wrong shape (missing `type` or `steps`)
- **Trigger**: Model returns `{ "answer": "..." }` instead of automation schema
- **Expected behavior**: `parseAutomationResponse` returns `null` → fallback to chat display
- **Handled in**: Phase 4 — explicit check `obj.type !== 'automation' || !obj.intent || !Array.isArray(obj.steps)`

### EC-1.4: Steps array is empty
- **Trigger**: LLM returns `{ type: "automation", intent: "...", steps: [] }`
- **Expected behavior**: `AutomationCard` renders with 0 steps; `[▶ Run All]` is disabled (existing behavior in AutomationCard)
- **Handled in**: Phase 4 — `parseAutomationResponse` returns `{ intent, steps: [] }`; no special case needed

---

## Category 2: Mode Switching Timing

### EC-2.1: User switches mode while LLM is streaming
- **Trigger**: User clicks `[Chat]` while an automation message is streaming
- **Expected behavior**: The in-flight message continues to completion as automation; the NEW mode takes effect on the next send
- **Handled in**: Phase 3 — `chatMode` is read once via `useChatStore.getState().chatMode` at the start of `handleSend`, not reactively during streaming

### EC-2.2: User sends multiple messages quickly in Automate mode
- **Trigger**: Fast double-send in Automate mode
- **Expected behavior**: `automationStore.reset()` is called at the start of each automation path — second plan overwrites the first
- **Handled in**: Phase 4 — `reset()` called before `setSteps()` every time

---

## Category 3: Schema Issues

### EC-3.1: `studioSchema` returns an empty array
- **Trigger**: `buildPathlyContext()` fails or schema is not yet loaded
- **Expected behavior**: Automation prompt omits the `## Studio UI Elements` section; LLM still generates steps (may use invented labels — user sees this in step descriptions and can correct)
- **Handled in**: Phase 3 — `buildAutomationPrompt` checks `schema.length > 0` before adding schema block

### EC-3.2: LLM uses a label not in studioSchema
- **Trigger**: LLM invents an element label ("Submit Order") that doesn't exist in Studio
- **Expected behavior**: Playwright executor returns `{ ok: false, error: 'element not found: Submit Order' }` — existing behavior in `playwrightExecutor.ts`
- **Handled in**: Out of scope for this plan — handled by the existing Playwright executor

---

---

## Category 4: Registry Resolution Failures (Conv 3+)

### EC-4.1: LLM invents an action name not in the registry
- **Trigger**: LLM outputs `{ "action": "pathly_deploy_to_prod" }` — not in `PATHLY_ACTIONS`
- **Expected behavior**: `expandAction` returns `null`; step is silently skipped
- **If all steps are unknown**: `concreteSteps.length === 0` → `parseAutomationResponse` returns `null` → chat fallback fires
- **Handled in**: Phase 6 — `expandAction` returns null for unknown names; length-zero guard returns null

### EC-4.2: LLM omits params for a parameterized action
- **Trigger**: `{ "action": "pathly_plan_feature" }` with no `params` key
- **Expected behavior**: `expandAction` receives `{}` as params; `{{featureName}}` resolves to empty string; step still runs (fills empty string into the input)
- **Handled in**: Phase 6 — `expandAction` defaults `params` to `{}` when undefined; `replace` returns empty string for missing keys

### EC-4.3: Registry has no entry for a requested workflow
- **Trigger**: User asks "deploy this to production" — no `pathly_deploy` action exists
- **Expected behavior**: All steps unknown → chat fallback shows LLM response text; user sees what the LLM said and can follow up
- **Mitigation path**: Add `pathly_deploy` to `PATHLY_ACTIONS` (one entry, no other changes needed)

### EC-4.4: Studio label referenced in registry doesn't exist in the live UI
- **Trigger**: Registry step has `{ label: "Run Storm" }` but the button was renamed
- **Expected behavior**: Playwright executor returns `{ ok: false, error: 'element not found: Run Storm' }` — existing executor error handling
- **Mitigation**: Registry is the single source of truth for labels. Fixing a broken label = update registry once (not every past conversation).

---

## Known Limitations

- Streaming JSON is not parsed incrementally — the user sees raw JSON streaming in the message bubble during Automate mode until the response completes and the card appears. This is acceptable for v1; a future improvement could hide the raw JSON stream and show a spinner instead.
- Mode is session-only and not labeled in the message history — if a user scrolls back, they cannot tell which messages were sent in Automate vs Chat mode. Out of scope for this plan.
- Registry coverage is manual — new Pathly workflows require a developer to add an entry to `pathlyActionRegistry.ts`. This is intentional (developer controls the vocabulary) but means new flows aren't available until the registry is updated.
