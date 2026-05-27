# Chat/Automate Mode Toggle — Flow Diagram

## Primary Flow: handleSend with mode branch

```
User presses Send
        │
        ▼
handleSend() reads chatMode
        │
        ├─ chatMode === 'chat' ────────────────────────────────────────────┐
        │                                                                  │
        │   matchIntent(text) + buildPathlyContext()                       │
        │        │                                                         │
        │        ▼                                                         │
        │   setCurrentMatch / setAltMatches                               │
        │        │                                                         │
        │        ▼                                                         │
        │   buildSystemPrompt(context, topMatch)                           │
        │        │                                                         │
        │        ▼                                                         │
        │   LLM call (Ollama / node-llama-cpp)                            │
        │        │  streams tokens                                         │
        │        ▼                                                         │
        │   splitThinkingContent(fullText)                                 │
        │        │                                                         │
        │        ▼                                                         │
        │   updateLastMessage({ content, thinking, status:'done' })        │
        │        │                                                         │
        │        ▼                                                         │
        │   MessageList → chat bubble [+ ThinkingBlock if thinking]  ◄────┘
        │
        └─ chatMode === 'automate' ────────────────────────────────────────┐
                                                                           │
            setCurrentMatch(null), setAltMatches([])                       │
                 │                                                         │
                 ▼                                                         │
            buildAutomationPrompt(context.studioSchema)                    │
                 │                                                         │
                 ▼                                                         │
            LLM call (same Ollama / node-llama-cpp IPC)                   │
                 │  streams JSON tokens                                    │
                 ▼                                                         │
            [streaming done] fullText accumulated                          │
                 │                                                         │
                 ▼                                                         │
            parseAutomationResponse(fullText)                              │
                 │                                                         │
                 ├─ success ──────────────────────────────────────────────┤
                 │   automationStore.reset()                               │
                 │   automationStore.setSteps(steps)                       │
                 │   updateLastMessage({ automationPlan, status:'done' })  │
                 │        │                                                │
                 │        ▼                                                │
                 │   MessageList → AutomationCard → StepQueue  ◄──────────┘
                 │
                 └─ failure (JSON parse error)
                     updateLastMessage({ content: fullText, status:'done' })
                          │
                          ▼
                     MessageList → plain chat bubble
```

## Toggle Pill Flow

```
ChatInput footer
        │
        ├─ [Chat]     onClick → setChatMode('chat')     → pill muted
        └─ [Automate] onClick → setChatMode('automate') → pill accent green
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `handleSend` | Main send handler in `ChatPanel/index.tsx` |
| `chatMode` | `chatStore.chatMode` — read once at send start |
| `buildAutomationPrompt` | New helper — JSON schema prompt with studioSchema |
| `parseAutomationResponse` | New helper — JSON parser with code-fence stripping |
| `AutomationCard` | Existing component — renders when `msg.automationPlan` exists |
| `StepQueue` | Existing component — reads `automationStore.steps` |
| `ThinkingBlock` | Existing component — renders `msg.thinking` content |
