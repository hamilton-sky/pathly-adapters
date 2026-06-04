# Review Failures — Conv 3

## Violation 1: suggestedTools is advisory metadata — tools never injected into Gemini API call

**File:** `C:\Users\Yafit\brightsky-ai\backend\src\services\unified-ai.service.ts:186-189`
**Rule:** Phase 10a spec — "add 'web_search', 'youtube_search', 'youtube_transcript' to the tool set when messageType === 'pathly_chat'"
**Found:** The three tool names are returned in `suggestedTools` on the `UnifiedAIResult` object (lines 186–189), but `callProvider()` (called at line 152) never receives a tool list. The Gemini API request assembled inside `geminiService.processWithContext()` has no knowledge of these tools. The log at line 131 ("Extra tools: web_search, youtube_search, youtube_transcript") is misleading — no tools are actually injected.
**Required:** The tools must be passed into the Gemini API call so the model can invoke them. Either `callProvider()` must accept a `tools` parameter and forward it to `geminiService.processWithContext()`, or the tools must be registered on the Gemini session before the call. Returning them in the result object alone satisfies neither the spec nor story S-10 ("Search + YouTube tools for Pathly agent").
**Fix:** Add a `tools?: string[]` parameter to `callProvider()`. In the `isPathlyChat` branch of `process()`, assemble `const pathlyTools = ['web_search', 'youtube_search', 'youtube_transcript']` and pass it to `callProvider()`. Forward it to `geminiService.processWithContext()` (or the appropriate Gemini method that accepts tool declarations).

---

## Violation 2: Fallback drops messageType — Gemini pin broken on primary failure

**File:** `C:\Users\Yafit\brightsky-ai\backend\src\services\unified-ai.service.ts:119-204`
**Rule:** Phase 10a spec — "when messageType === 'pathly_chat', force provider = 'gemini'"; the Gemini pin must hold for the lifetime of the request, including fallback.
**Found:** `messageType` is destructured out of `options` at line 119 and is NOT included in the `otherOptions` spread passed to `tryFallback()` at lines 194–205. `tryFallback()` has no `messageType` parameter. If the primary Gemini call fails (rate limit, 503, MAX_TOKENS), the fallback iterates `['xai', 'gemini', 'openai']` with no knowledge that this was a `pathly_chat` request, and can route to xAI or OpenAI — violating the Gemini pin.
**Required:** `messageType` must be forwarded into `tryFallback()`. The fallback must skip non-Gemini providers when `messageType === 'pathly_chat'`.
**Fix:** Add `messageType?: string` to `tryFallback()`'s `options` parameter. Pass `messageType` through from `process()` at the call site (line 194). Inside `tryFallback()`, after the `fullOrder` declaration, insert a guard: `const filteredOrder = messageType === 'pathly_chat' ? (['gemini'] as const) : fallbackOrder;` and iterate `filteredOrder` instead of `fallbackOrder`.
