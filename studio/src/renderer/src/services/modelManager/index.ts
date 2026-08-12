// modelManager — app-level service that owns the local-AI model catalog and a
// one-shot run entry point. This is the single source of truth: HQ
// (ModelSelector, modelStore) and the Router (aiRouter, later conversation)
// consume the catalog and `runModel` from here, never from `data/models.ts`
// or the transport modules directly.
//
// Public API:
//   - MODEL_CATALOG / getModelById / RECOMMENDED_MODEL_ID / BRIGHTSKY_ID — catalog
//   - Model (type)
//   - runModel(id, prompt) → { text, cost_usd? } — one-shot, non-streaming
//   - RunResult (type)
//   - availability helpers (isGgufAvailable, ollamaStatus, cachedGgufIds,
//     isBrightskyAuthenticated)

export {
  MODEL_CATALOG,
  
  RECOMMENDED_MODEL_ID,
  BRIGHTSKY_ID,
} from './catalog'


export { runModel } from './runModel'



