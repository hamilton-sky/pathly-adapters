# Chat/Automate Mode Toggle — Flow Diagram

## Primary Flow: handleSend with mode branch

```
User presses Send
        |
        v
handleSend() reads chatMode
        |
        +-- chatMode === 'chat' -----------------------------------------------+
        |                                                                       |
        |   matchIntent(text) + buildPathlyContext()                            |
        |        |                                                              |
        |        v                                                              |
        |   setCurrentMatch / setAltMatches                                    |
        |        |                                                              |
        |        v                                                              |
        |   buildSystemPrompt(context, topMatch)                               |
        |        |                                                              |
        |        v                                                              |
        |   LLM call (Ollama / node-llama-cpp)                                |
        |        |  streams tokens                                              |
        |        v                                                              |
        |   splitThinkingContent(fullText)                                     |
        |        |                                                              |
        |        v                                                              |
        |   updateLastMessage({ content, thinking, status:'done' })            |
        |        |                                                              |
        |        v                                                              |
        |   MessageList -> chat bubble [+ ThinkingBlock if thinking]  <--------+
        |
        +-- chatMode === 'automate' -------------------------------------------+
                                                                               |
            setCurrentMatch(null), setAltMatches([])                           |
                 |                                                             |
                 v                                                             |
            buildAutomationPrompt()                                            |
            [injects REGISTRY_PROMPT_BLOCK — stable named action vocabulary]  |
                 |                                                             |
                 v                                                             |
            LLM call (same Ollama / node-llama-cpp IPC)                       |
                 |  streams JSON tokens                                        |
                 v                                                             |
            [streaming done] fullText accumulated                              |
                 |                                                             |
                 v                                                             |
            parseAutomationResponse(fullText)                                  |
                 |                                                             |
                 |  per raw step: expandAction(name, params)                   |
                 |  -> concrete AutomationStep[] (labels from registry)        |
                 |                                                             |
                 +-- success (concreteSteps.length > 0) ---------------------+|
                 |   automationStore.reset()                                  ||
                 |   automationStore.setSteps(concreteSteps)                  ||
                 |   updateLastMessage({ automationPlan, status:'done' })     ||
                 |        |                                                   ||
                 |        v                                                   ||
                 |   MessageList -> AutomationCard -> StepQueue  <-----------++
                 |
                 +-- failure (JSON error OR all steps unknown)
                     updateLastMessage({ content: fullText, status:'done' })
                          |
                          v
                     MessageList -> plain chat bubble
```

## Toggle Pill Flow

```
ChatInput footer
        |
        +-- [Chat]     onClick -> setChatMode('chat')     -> pill muted
        +-- [Automate] onClick -> setChatMode('automate') -> pill accent green
```

## Registry Expansion Flow (Conv 3)

```
LLM outputs:
  { "action": "pathly_plan_feature", "params": { "featureName": "auth-v2" } }

expandAction("pathly_plan_feature", { featureName: "auth-v2" })
        |
        v
  [
    { type: "click", label: "New Feature" },
    { type: "fill",  label: "Feature Name Input", value: "auth-v2" },
    { type: "click", label: "Create Plan" }
  ]
        |
        v
  AutomationStep[] with crypto.randomUUID() ids -> automationStore.setSteps()
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `handleSend` | Main send handler in `ChatPanel/index.tsx` |
| `chatMode` | `chatStore.chatMode` — read once at send start |
| `buildAutomationPrompt` | Zero-arg helper — injects REGISTRY_PROMPT_BLOCK |
| `parseAutomationResponse` | JSON parser + expandAction per step |
| `expandAction` | `pathlyActionRegistry.ts` — resolves named action + params to concrete steps |
| `REGISTRY_PROMPT_BLOCK` | Formatted action list injected into LLM prompt |
| `AutomationCard` | Existing component — renders when `msg.automationPlan` exists |
| `StepQueue` | Existing component — reads `automationStore.steps` |
| `ThinkingBlock` | Existing component — renders `msg.thinking` content |
