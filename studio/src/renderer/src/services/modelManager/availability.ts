// Availability helpers — thin wrappers over the same IPC/store signals that
// `ModelSelector.tsx` already calls. Centralizing them here lets non-HQ
// consumers (e.g. the Router) probe backend readiness without re-deriving the
// logic.

import { useBrightskyStore } from '../../store/brightskyStore'

/** Is local GGUF inference (node-llama-cpp, Electron 33+) available? */
export function isGgufAvailable(): Promise<boolean> {
  return window.pathly.llm.isAvailable()
}

/** Is Ollama running, and which model tags are installed? */
export function ollamaStatus(): Promise<{ available: boolean; models: string[] }> {
  return window.pathly.llm.ollamaAvailable()
}

/** Which GGUF model ids are cached on disk? */
export function cachedGgufIds(): Promise<string[]> {
  return window.pathly.llm.listCached()
}

/** Is the user signed in to Brightsky? */
export function isBrightskyAuthenticated(): boolean {
  return useBrightskyStore.getState().authenticated
}
