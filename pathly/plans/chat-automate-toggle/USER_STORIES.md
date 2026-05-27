# Chat/Automate Mode Toggle — User Stories

## Context

The Conductor chat panel sends every message through the same chat flow — the LLM explains
a skill match. But Pathly also supports UI automation: the LLM generates a structured action
plan (`{ intent, steps[] }`) that Playwright executes via the step queue.

Currently `isAutomationIntent` (a regex on line ~281 of `ChatPanel/index.tsx`) is defined but
**never used** — so automation plan generation never fires. The `AutomationCard` and `StepQueue`
components exist and work, but the pipeline feeding them is missing.

This feature adds an explicit `[Chat | Automate]` mode toggle pill in the ChatInput footer.
When the user switches to Automate, the next message triggers the automation path instead of
the chat path. No more regex guessing — the user declares intent.

---

## Stories

### Story S1.1: Mode toggle pill in the footer

**As a** Pathly Studio user, **I want** a `[Chat | Automate]` toggle in the message input footer,
**so that** I can explicitly choose whether my next message should explain a skill or generate an action plan.

**Acceptance Criteria:**
- [ ] A two-button pill `[Chat]` `[Automate]` renders in the ChatInput footer row
- [ ] Active mode button is visually distinct (accent background, dark text)
- [ ] Inactive mode button is muted (surface background, muted text)
- [ ] Clicking either button sets `chatStore.chatMode` to `'chat'` or `'automate'`
- [ ] Default mode on first load is `'chat'`
- [ ] Toggle is keyboard accessible (focusable, activates on Enter/Space)

**Edge Cases:**
- Toggle while streaming: switching mode mid-response does not affect the in-flight message; takes effect on the next send
- Disabled state: toggle is not disabled during streaming — user can pre-select mode for the next message

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story S1.2: Mode lives in chatStore (session-only)

**As a** Pathly Studio user, **I want** the mode I selected to persist within my session,
**so that** I don't have to re-select Automate for each automation message.

**Acceptance Criteria:**
- [ ] `chatStore.chatMode` field exists with type `'chat' | 'automate'`
- [ ] `chatStore.setChatMode(mode)` action exists and updates the field
- [ ] Mode is NOT persisted across app restarts (session-only — intentional reset to 'chat' on reload)
- [ ] TypeScript: no new errors from the chatStore change

**Edge Cases:**
- After an automation run completes, mode stays on `'automate'` — user must manually switch back to `'chat'`

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2.1: Automate mode sends an automation-specific system prompt

**As a** Pathly Studio user in Automate mode, **I want** the AI to receive a prompt that asks
for a structured action plan, **so that** it knows to return steps instead of a chat explanation.

**Acceptance Criteria:**
- [ ] When `chatMode === 'automate'`, the system prompt instructs the LLM to return JSON `{ "type": "automation", "intent": "...", "steps": [...] }`
- [ ] System prompt includes `studioSchema` (element labels) so the LLM uses real Studio labels
- [ ] Each step in the prompt spec has `{ "description": string, "action": { "type": "click"|"fill"|"select", "label": string, "value"?: string } }`
- [ ] When `chatMode === 'chat'`, the existing system prompt and flow are used unchanged

**Edge Cases:**
- No schema available: if `studioSchema` returns an empty array, prompt omits the schema section (doesn't crash)

**Delivered by:** Phase 3 → Conversation 2

---

### Story S2.2: LLM JSON response parsed into AutomationCard

**As a** Pathly Studio user, **I want** the AI's JSON response to appear as an AutomationCard
with step count and intent, **so that** I can choose to run all steps or step through them.

**Acceptance Criteria:**
- [ ] After LLM responds in Automate mode, the response JSON is parsed for `{ type: "automation", intent, steps }`
- [ ] On successful parse: `updateLastMessage({ automationPlan: { intent, steps }, content: '', status: 'done' })` is called
- [ ] `AutomationCard` renders in the message list (it already reads `msg.automationPlan`)
- [ ] On parse failure (LLM returned plain text instead of JSON): the response is shown as a normal chat message — no crash

**Edge Cases:**
- Partial JSON (LLM truncated): `JSON.parse` throws → treat as chat message, log warning
- Steps array is empty: AutomationCard still renders, shows 0 steps, `[▶ Run All]` is disabled

**Delivered by:** Phase 4 → Conversation 2

---

### Story S2.3: Parsed steps wired to automationStore

**As a** Pathly Studio user, **I want** the step queue to be populated when the automation plan arrives,
**so that** clicking Approve or Run All immediately executes steps.

**Acceptance Criteria:**
- [ ] `automationStore.setSteps(steps)` is called with the parsed `AutomationStep[]` when the plan arrives
- [ ] Each step is given a unique `id` (crypto.randomUUID()) before being passed to `setSteps`
- [ ] `automationStore.reset()` is called at the start of each new automation message (before `setSteps`)

**Delivered by:** Phase 4 → Conversation 2

---

### Story S2.4: Chat mode is unaffected (no regression)

**As a** Pathly Studio user in Chat mode, **I want** all existing chat behavior to work exactly
as before, **so that** this feature adds capability without breaking anything.

**Acceptance Criteria:**
- [ ] Chat mode: existing Ollama / node-llama-cpp streaming path is unchanged
- [ ] Chat mode: MatchCard, skill embedding, context injection all work as before
- [ ] The unused `isAutomationIntent` regex in `ChatPanel/index.tsx` is removed
- [ ] TypeScript: no new errors

**Delivered by:** Phase 3–4 → Conversation 2

---

### Story S3.1: Named action registry

**As a** Pathly developer, **I want** a `pathlyActionRegistry.ts` that maps stable action names to
concrete Playwright steps, **so that** the LLM prompt vocabulary stays consistent even when Studio
UI labels change.

**Acceptance Criteria:**
- [ ] `pathlyActionRegistry.ts` exports `PATHLY_ACTIONS: PathlyActionDef[]` with at least 5 named actions: `pathly_plan_feature`, `pathly_run_storm`, `pathly_run_build`, `pathly_run_review`, `pathly_run_test`
- [ ] `expandAction(name, params)` returns the concrete step array for a known name; returns `null` for unknown names
- [ ] `{{paramName}}` placeholders in step `value` fields are replaced by `expandAction` using the provided params object
- [ ] `REGISTRY_PROMPT_BLOCK` is a formatted string listing all action names, param signatures, and descriptions
- [ ] TypeScript: no new errors

**Delivered by:** Phase 5 → Conversation 3

---

### Story S3.2: LLM prompt uses registry vocabulary; steps expand before execution

**As a** Pathly Studio user in Automate mode, **I want** the AI to generate steps using named
Pathly actions (not raw click/fill labels), **so that** my workflows keep working even if Studio
UI labels are renamed.

**Acceptance Criteria:**
- [ ] `buildAutomationPrompt()` takes no arguments and injects `REGISTRY_PROMPT_BLOCK` into the system prompt
- [ ] The LLM JSON schema uses `{ "action": "<registry name>", "params": { ... } }` per step (not `{ "type": "click", "label": "..." }`)
- [ ] `parseAutomationResponse` calls `expandAction` per raw step; unknown actions are silently skipped
- [ ] If all steps expand to an empty array, `parseAutomationResponse` returns `null` (falls back to chat display)
- [ ] Conv 2 behavior (raw label steps) is replaced — `studioSchema` is no longer injected into the automation prompt
- [ ] TypeScript: no new errors

**Edge Cases:**
- LLM invents an action name not in the registry: `expandAction` returns null, step is skipped; if no steps expand, chat fallback fires
- LLM omits `params` for a parameterized action: `expandAction` substitutes empty string for missing params (no crash)

**Delivered by:** Phase 6 → Conversation 3
