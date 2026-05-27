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
