// Model catalog — single source of truth for the app's local-AI model list.
//
// The `Model[]` array physically lives in `data/models.ts` (kept there to avoid
// churning the existing `MODEL_REGISTRY` id-matching contract and the four
// historical import sites). modelManager is the *owner*: every consumer should
// import the catalog from here, not from `data/models.ts` directly. The data
// module is the storage detail; this service is the public surface.

import { WEB_LLM_MODELS, RECOMMENDED_MODEL_ID } from '../../data/models'
import type { Model } from '../../data/models'

export type { Model }

/** The full model catalog (Ollama-tag / GGUF local models). */
export const MODEL_CATALOG: Model[] = WEB_LLM_MODELS

/** Default model id selected on first run. */
export { RECOMMENDED_MODEL_ID }

/** Special transport ids that are not part of the GGUF/Ollama catalog. */
export const BRIGHTSKY_ID = 'brightsky'

/** Look up a catalog model by its app id (e.g. 'phi-4-mini'). */
export function getModelById(id: string): Model | undefined {
  return MODEL_CATALOG.find((m) => m.id === id)
}
