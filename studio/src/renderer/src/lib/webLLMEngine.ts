import { CreateMLCEngine, type MLCEngine } from '@mlc-ai/web-llm'
import { RECOMMENDED_MODEL_ID } from '../data/models'

let engine: MLCEngine | null = null
let engineModelId: string | null = null
let enginePromise: Promise<MLCEngine> | null = null

export async function getEngine(
  modelId: string,
  onProgress?: (pct: number, text?: string) => void
): Promise<MLCEngine> {
  if (engine && engineModelId === modelId) return engine
  if (enginePromise && engineModelId === modelId) return enginePromise

  // New model requested — reset
  engine = null
  enginePromise = null
  engineModelId = modelId

  enginePromise = (async () => {
    try {
      const mlc = await CreateMLCEngine(modelId, {
        initProgressCallback: (report) => {
          const pct = Math.round(report.progress * 100)
          // Append elapsed time so UI can show the download is alive
          const elapsed = report.timeElapsed != null ? ` (${Math.round(report.timeElapsed)}s)` : ''
          onProgress?.(pct, report.text ? `${report.text}${elapsed}` : undefined)
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
  try {
    const cache = await caches.open('webllm/model')
    const keys = await cache.keys()
    const ids = new Set<string>()
    for (const req of keys) {
      const url = req.url
      const match = url.match(/\/([^/]+)\//)?.[1]
      if (match) ids.add(match)
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
