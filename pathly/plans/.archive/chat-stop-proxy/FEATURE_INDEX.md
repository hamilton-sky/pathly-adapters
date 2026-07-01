# Feature Index — chat-stop-proxy

## What this feature delivers

Two independent but related chat-panel improvements for Pathly Studio:

1. **Stop/Abort Button** — While an LLM stream is in progress, the Send button
   transforms into a Stop button. Clicking it aborts the stream, preserves the
   partial response, and returns the input to a usable state.

2. **Chat-as-Claude-Code Proxy** — A mode toggle in `ChatInput` routes messages
   to the Claude Code PTY terminal instead of the LLM. Terminal output streams
   back into the chat panel as a normal assistant bubble.

## Primary user

Pathly Studio developer using the chat panel daily.

## Plan files

| File | Purpose |
|---|---|
| `FEATURE_INDEX.md` | This file — orientation entry point |
| `PO_NOTES.md` | Authoritative product requirements |
| `USER_STORIES.md` | Decomposed stories with acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Phases and conversation breakdown |
| `CONVERSATION_PROMPTS.md` | Builder prompts for each conversation |
| `PROGRESS.md` | Live implementation status |

## Conversations at a glance

| Conv | Scope | Delivers |
|---|---|---|
| 0 | Pre-flight | Baseline verification before any changes |
| 1 | Stop button | S-01, S-02, S-03 |
| 2 | Claude Code proxy | S-04, S-05, S-06 |

## Key files touched

- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`
- `studio/src/renderer/src/components/ChatPanel/index.tsx`
- `studio/src/renderer/src/store/chatStore.ts`
- `studio/src/renderer/src/lib/llmBridge.ts`
