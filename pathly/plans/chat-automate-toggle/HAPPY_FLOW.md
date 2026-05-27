# Chat/Automate Mode Toggle — Happy Flow

## Overview

A Pathly Studio user wants to create a new checkout flow with HTTP and condition steps.
Instead of navigating menus manually, they switch the Conductor to Automate mode, describe
what they want, and let the AI generate and execute the action plan.

## Step-by-Step Happy Flow

### Step 1: User switches to Automate mode
- **User does**: Clicks the `[Automate]` button in the ChatInput footer
- **System does**: `chatStore.setChatMode('automate')` — the Automate pill turns green
- **State after**: `chatMode === 'automate'`, Chat pill is muted

### Step 2: User describes the task
- **User does**: Types "create a checkout flow with an HTTP step to Stripe and a condition step" and presses Enter
- **System does**: `handleSend` reads `chatMode === 'automate'`, builds `buildAutomationPrompt(studioSchema)`, sends to LLM; assistant message appears with streaming dots
- **State after**: LLM is generating JSON response; streaming indicator visible

### Step 3: LLM streams the action plan
- **User does**: Waits
- **System does**: LLM streams JSON `{ type: "automation", intent: "Create checkout flow...", steps: [...] }`; content streams in message bubble
- **State after**: Full JSON text accumulated in `fullText`

### Step 4: Response parsed → AutomationCard appears
- **User does**: Observes
- **System does**: `parseAutomationResponse(fullText)` succeeds → `automationStore.reset()` → `automationStore.setSteps(steps)` → `updateLastMessage({ content: '', automationPlan: { intent, steps }, status: 'done' })`
- **State after**: `AutomationCard` renders in the message list showing intent + step count; `StepQueue` is ready

### Step 5: User approves steps or runs all
- **User does**: Clicks `[▶ Run All]` or `[Step by Step]`
- **System does**: Existing `StepQueue` / Playwright execution flow (unchanged)
- **State after**: Studio UI elements are clicked/filled by Playwright

## End State

The checkout flow exists in Studio. The user never navigated any menus. They described what
they wanted, reviewed the plan, and approved execution — all from the chat panel.

## Success Indicators
- [ ] `[Chat | Automate]` toggle visible and responsive in footer
- [ ] Switching to Automate and sending a message shows AutomationCard (not a chat bubble)
- [ ] Switching back to Chat and sending a message shows normal skill match + explanation
- [ ] `automationStore.steps` is populated after an automation message

---

## Extended Happy Flow (Conv 3 — named action registry)

The user asks for a multi-phase Pathly workflow by name. The AI maps it to registered actions.

### Step 1: User switches to Automate mode
- Same as above — clicks `[Automate]`, pill turns green

### Step 2: User describes a multi-step Pathly workflow
- **User does**: Types "plan a feature called auth-v2, then run storm and build" and presses Enter
- **System does**: `buildAutomationPrompt()` injects `REGISTRY_PROMPT_BLOCK` into the system prompt, sends to LLM

### Step 3: LLM streams named-action JSON
- **System does**: LLM streams:
  ```json
  { "type": "automation", "intent": "Plan auth-v2 then storm and build",
    "steps": [
      { "description": "Create feature plan", "action": "pathly_plan_feature", "params": { "featureName": "auth-v2" } },
      { "description": "Run storm phase",     "action": "pathly_run_storm",    "params": {} },
      { "description": "Run build phase",     "action": "pathly_run_build",    "params": {} }
    ] }
  ```

### Step 4: expandAction resolves each step
- **System does**: `expandAction("pathly_plan_feature", { featureName: "auth-v2" })` returns 3 concrete Playwright steps. `expandAction("pathly_run_storm")` and `expandAction("pathly_run_build")` return 1 step each. Total: 5 concrete `AutomationStep[]` passed to `automationStore.setSteps()`.

### Step 5: AutomationCard appears, user approves
- Same as base flow — card shows intent + step count, user clicks Run All

## Extended End State

The Studio executes: New Feature → fill "auth-v2" → Create Plan → click Storm → click Build.
The user described a workflow in natural language; the registry translated it to stable, resilient steps.
