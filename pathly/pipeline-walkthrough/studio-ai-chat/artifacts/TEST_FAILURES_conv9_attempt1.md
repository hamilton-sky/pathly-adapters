# Test Failures — studio-ai-chat Conv 9

Date: 2026-05-27

## FAIL: S9.3 — Selected model is NOT passed to askWebLLM

**Criterion:** ChatPanel calls `askWebLLM` when `PATHLY_CHAT_BACKEND !== 'ollama'`, and the selected model (from `modelStore.selectedModelId`) is used for all AI responses.

**What was expected:**
`ChatPanel/index.tsx` reads `selectedModelId` from `useModelStore` and either:
- passes it to `askWebLLM(text, systemPrompt, onChunk, selectedModelId)`, or
- calls `getEngine(selectedModelId)` before invoking `askWebLLM`.

**What actually happened:**
- `ChatPanel/index.tsx` does NOT import or read `useModelStore` / `selectedModelId` at all.
- `askWebLLM` in `webLLMEngine.ts` (line 104) resolves the model as:
  `const modelId = engineModelId ?? RECOMMENDED_MODEL_ID`
  where `engineModelId` is a module-level variable tracking the last engine loaded via `getEngine`.
- `ChatPanel` never calls `getEngine` with the user's selected model before invoking `askWebLLM`.
- Result: changing the model selection in `ModelSelector` updates `modelStore.selectedModelId` but has **no effect** on which model is used when the user sends a chat message.

**Files involved:**
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — missing `useModelStore` import and `getEngine` call
- `studio/src/renderer/src/lib/webLLMEngine.ts` — `askWebLLM` does not accept a `modelId` parameter

**Suggested fix:**
In `ChatPanel/index.tsx`:
1. Import `useModelStore` and read `selectedModelId`.
2. Before calling `askWebLLM`, call `await getEngine(selectedModelId)` to ensure the correct engine is loaded.

Alternatively, add a `modelId?: string` parameter to `askWebLLM` and have it call `getEngine(modelId ?? engineModelId ?? RECOMMENDED_MODEL_ID)`.
