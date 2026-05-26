import { CreateMLCEngine, type MLCEngine } from '@mlc-ai/web-llm'
import { RECOMMENDED_MODEL_ID } from '../data/models'

let engine: MLCEngine | null = null
let engineModelId: string | null = null
let enginePromise: Promise<MLCEngine> | null = null
// Module-level callback — always points to the most recently registered listener.
// Updated by every getEngine() call so late subscribers (e.g. ModelSelector opening
// mid-download) still receive progress events.
let activeOnProgress: ((pct: number, text?: string) => void) | undefined

export async function getEngine(
  modelId: string,
  onProgress?: (pct: number, text?: string) => void
): Promise<MLCEngine> {
  // Always update the active callback so the latest caller gets progress events,
  // even if the engine is already loading.
  if (onProgress) activeOnProgress = onProgress

  if (engine && engineModelId === modelId) return engine

  if (enginePromise && engineModelId === modelId) {
    // Engine already loading — re-use the promise; callback updated above.
    return enginePromise
  }

  // New model requested — reset
  engine = null
  enginePromise = null
  engineModelId = modelId
  activeOnProgress = onProgress

  enginePromise = (async () => {
    try {
      const mlc = await CreateMLCEngine(modelId, {
        // Use IndexedDB — Cache API is unreliable in Electron's file:// context.
        // See: https://github.com/mlc-ai/web-llm/issues/313
        appConfig: { model_list: [], cacheBackend: 'indexeddb' },
        initProgressCallback: (report) => {
          const pct = Math.round(report.progress * 100)
          const elapsed = report.timeElapsed != null ? ` (${Math.round(report.timeElapsed)}s)` : ''
          activeOnProgress?.(pct, report.text ? `${report.text}${elapsed}` : undefined)
        },
      })
      engine = mlc
      return mlc
    } catch (err) {
      enginePromise = null
      engineModelId = null
      const msg = err instanceof Error ? err.message : String(err)
      if (
        msg.toLowerCase().includes('webgpu') ||
        msg.toLowerCase().includes('gpu') ||
        msg.toLowerCase().includes('not supported')
      ) {
        throw new Error('WebGPU not supported')
      }
      throw err
    }
  })()

  return enginePromise
}

export async function getCachedWebLLMModelIds(): Promise<string[]> {
  // With indexeddb backend, check IndexedDB for model records.
  // WebLLM stores each shard as a record keyed by URL; we extract the model ID
  // segment from those keys. Falls back to Cache API for legacy installs.
  try {
    const ids = new Set<string>()

    // IndexedDB check (primary — matches WEBLLM_APP_CONFIG cacheBackend)
    await new Promise<void>((resolve) => {
      const req = indexedDB.open('webllm-model-cache', 1)
      req.onsuccess = () => {
        try {
          const db = req.result
          const storeNames = Array.from(db.objectStoreNames)
          if (storeNames.length === 0) { db.close(); resolve(); return }
          const tx = db.transaction(storeNames[0], 'readonly')
          const store = tx.objectStore(storeNames[0])
          const keysReq = store.getAllKeys()
          keysReq.onsuccess = () => {
            for (const k of keysReq.result as string[]) {
              const m = String(k).match(/\/([^/]+)\//)
              if (m) ids.add(m[1])
            }
            db.close()
            resolve()
          }
          keysReq.onerror = () => { db.close(); resolve() }
        } catch { resolve() }
      }
      req.onerror = () => resolve()
    })

    // Cache API fallback (legacy / browser context)
    if (ids.size === 0) {
      try {
        const cache = await caches.open('webllm/model')
        const keys = await cache.keys()
        for (const req of keys) {
          const m = req.url.match(/\/([^/]+)\//)
          if (m) ids.add(m[1])
        }
      } catch { /* Cache API unavailable */ }
    }

    return [...ids]
  } catch {
    return []
  }
}

export async function cacheWebLLMModel(
  modelId: string,
  onProgress: (pct: number, text?: string) => void
): Promise<void> {
  await getEngine(modelId, onProgress)
}

export async function deleteCachedWebLLMModel(modelId: string): Promise<void> {
  try {
    const cacheNames = await caches.keys()
    for (const name of cacheNames) {
      if (name.startsWith('webllm')) {
        const cache = await caches.open(name)
        const keys = await cache.keys()
        for (const req of keys) {
          if (req.url.includes(modelId)) {
            await cache.delete(req)
          }
        }
      }
    }
    // If this was the active engine model, reset it
    if (engineModelId === modelId) {
      engine = null
      enginePromise = null
      engineModelId = null
    }
  } catch {
    // Cache API may not be available in some contexts
  }
}

let interrupted = false

export async function askWebLLM(
  prompt: string,
  systemPrompt: string,
  onChunk: (text: string) => void
): Promise<string> {
  interrupted = false
  const modelId = engineModelId ?? RECOMMENDED_MODEL_ID
  const mlc = await getEngine(modelId)

  const chunks = await mlc.chat.completions.create({
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: prompt },
    ],
    stream: true,
    temperature: 0.7,
    max_tokens: 512,
  })

  let fullText = ''
  for await (const chunk of chunks) {
    if (interrupted) break
    const delta = chunk.choices[0]?.delta?.content ?? ''
    if (delta) {
      fullText += delta
      onChunk(delta)
    }
  }
  return fullText
}

export function interruptWebLLM(): void {
  interrupted = true
  engine?.interruptGenerate?.()
}

export function cancelEngineLoad(): void {
  // Resets engine state so the user can switch models immediately.
  // The underlying CreateMLCEngine fetch cannot be aborted via WebLLM's API,
  // but resetting here allows a fresh load on the next send.
  engine = null
  enginePromise = null
  engineModelId = null
}
