// node-llama-cpp v3 is pure ESM and uses `import ... with { type: 'json' }` (Node 22 syntax).
// - Electron 28 (Node 20) → `with` keyword not supported → dynamic import throws SyntaxError
// - Electron 33 (Node 22) → fully supported ✓
//
// All handlers use dynamic import() wrapped in try/catch so the app starts cleanly on any
// Electron version and falls back gracefully to Ollama or skill-matching.
// This project now targets Electron 33 (devDependencies updated).

import { ipcMain, app } from 'electron'
import * as fs from 'fs'
import * as path from 'path'

interface ModelInfo {
  uri: string
  filename: string
}

const MODEL_REGISTRY: Record<string, ModelInfo> = {
  'qwen2.5-coder-7b': {
    uri: 'hf:bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf',
    filename: 'Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf',
  },
  'qwen3-4b': {
    uri: 'hf:unsloth/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf',
    filename: 'Qwen3-4B-Q4_K_M.gguf',
  },
  'phi-4-mini': {
    uri: 'hf:bartowski/microsoft_Phi-4-mini-instruct-GGUF/Phi-4-mini-instruct-Q4_K_M.gguf',
    filename: 'Phi-4-mini-instruct-Q4_K_M.gguf',
  },
  'llama-3.2-3b': {
    uri: 'hf:bartowski/Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf',
    filename: 'Llama-3.2-3B-Instruct-Q4_K_M.gguf',
  },
}

function getModelsDir(): string {
  return path.join(app.getPath('userData'), 'models')
}

function getModelPath(modelId: string): string {
  const info = MODEL_REGISTRY[modelId]
  if (!info) throw new Error(`Unknown model: ${modelId}`)
  return path.join(getModelsDir(), info.filename)
}

// Lazily loaded — populated on first successful import of node-llama-cpp
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let llamaModule: any = null
let llamaLoadError: string | null = null

async function loadLlamaCpp() {
  if (llamaModule) return llamaModule
  if (llamaLoadError) throw new Error(llamaLoadError)
  try {
    llamaModule = await import('node-llama-cpp')
    return llamaModule
  } catch (err) {
    llamaLoadError =
      'Local LLM unavailable — node-llama-cpp requires Electron 33+ (Node 22). ' +
      'Upgrade Electron in devDependencies, or use PATHLY_CHAT_BACKEND=ollama. ' +
      `Original error: ${err instanceof Error ? err.message : String(err)}`
    throw new Error(llamaLoadError)
  }
}

// In-memory model state
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let llamaInstance: any = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let loadedModel: any = null
let loadedModelId: string | null = null
let activeAbortController: AbortController | null = null

async function getLlamaInstance() {
  const { getLlama } = await loadLlamaCpp()
  if (!llamaInstance) llamaInstance = await getLlama()
  return llamaInstance
}

async function ensureModel(
  modelId: string,
  onProgress?: (pct: number, text: string) => void
) {
  if (loadedModel && loadedModelId === modelId) return loadedModel
  if (loadedModel) {
    try { await loadedModel.dispose() } catch { /* ignore */ }
    loadedModel = null
    loadedModelId = null
  }
  const instance = await getLlamaInstance()
  onProgress?.(0, 'loading model into memory…')
  loadedModel = await instance.loadModel({
    modelPath: getModelPath(modelId),
    onLoadProgress: (progress: number) => {
      const pct = Math.round(progress * 100)
      onProgress?.(pct, `loading model… ${pct}%`)
    },
  })
  loadedModelId = modelId
  return loadedModel
}

export function registerLlmHandlers(): void {
  fs.mkdirSync(getModelsDir(), { recursive: true })

  ipcMain.handle('llm:isAvailable', async (): Promise<boolean> => {
    try {
      const mod = await loadLlamaCpp()
      return typeof mod.createModelDownloader === 'function'
    } catch {
      return false
    }
  })

  ipcMain.handle('llm:listCached', async (): Promise<string[]> => {
    try {
      const files = new Set(fs.readdirSync(getModelsDir()))
      return Object.entries(MODEL_REGISTRY)
        .filter(([, info]) => files.has(info.filename))
        .map(([id]) => id)
    } catch {
      return []
    }
  })

  ipcMain.handle('llm:download', async (event, modelId: string): Promise<void> => {
    const info = MODEL_REGISTRY[modelId]
    if (!info) throw new Error(`Unknown model: ${modelId}`)
    const mod = await loadLlamaCpp()
    if (typeof mod.createModelDownloader !== 'function') {
      throw new Error('Model download requires node-llama-cpp v3 and Electron 33+. Upgrade Electron in devDependencies to enable local inference.')
    }
    const downloader = await mod.createModelDownloader({
      modelUri: info.uri,
      dirPath: getModelsDir(),
      skipExisting: true,
      onProgress: (status: { downloadedSize: number; totalSize: number }) => {
        const pct = status.totalSize > 0
          ? Math.round((status.downloadedSize / status.totalSize) * 100) : 0
        event.sender.send('llm:dl-progress', { modelId, pct, downloaded: status.downloadedSize, total: status.totalSize })
      },
    })
    await downloader.download()
    event.sender.send('llm:dl-progress', { modelId, pct: 100, downloaded: 0, total: 0 })
  })

  ipcMain.handle('llm:delete', async (_event, modelId: string): Promise<void> => {
    const modelPath = getModelPath(modelId)
    if (fs.existsSync(modelPath)) fs.unlinkSync(modelPath)
    if (loadedModelId === modelId) {
      try { await loadedModel?.dispose() } catch { /* ignore */ }
      loadedModel = null
      loadedModelId = null
    }
  })

  ipcMain.handle('llm:load', async (event, modelId: string): Promise<void> => {
    await ensureModel(modelId, (pct, text) => {
      event.sender.send('llm:load-progress', { pct, text })
    })
    event.sender.send('llm:load-progress', { pct: 100, text: 'ready' })
  })

  ipcMain.handle('llm:chat', async (
    event,
    { prompt, systemPrompt, modelId }: { prompt: string; systemPrompt: string; modelId: string }
  ): Promise<void> => {
    const { LlamaChatSession } = await loadLlamaCpp()
    const model = await ensureModel(modelId, (pct, text) => {
      event.sender.send('llm:load-progress', { pct, text })
    })
    const context = await model.createContext()
    const session = new LlamaChatSession({ contextSequence: context.getSequence(), systemPrompt })
    activeAbortController = new AbortController()
    let fullText = ''
    try {
      await session.prompt(prompt, {
        signal: activeAbortController.signal,
        maxTokens: 512,
        temperature: 0.7,
        onToken: (tokens: unknown[]) => {
          const text: string = model.detokenize(tokens)
          fullText += text
          event.sender.send('llm:token', text)
        },
      })
      event.sender.send('llm:done', fullText)
    } catch (err: unknown) {
      const isAbort = err instanceof Error &&
        (err.name === 'AbortError' || err.message.toLowerCase().includes('abort'))
      if (isAbort) {
        event.sender.send('llm:done', fullText)
      } else {
        event.sender.send('llm:error', err instanceof Error ? err.message : String(err))
      }
    } finally {
      try { await context.dispose() } catch { /* ignore */ }
      activeAbortController = null
    }
  })

  ipcMain.handle('llm:abort', (): void => {
    activeAbortController?.abort()
    activeAbortController = null
  })

  // ── Ollama backend ────────────────────────────────────────────────────────
  // Works on any Electron version — no native bindings needed.
  // User must have Ollama installed: https://ollama.ai

  ipcMain.handle('llm:ollamaAvailable', async (): Promise<{ available: boolean; models: string[] }> => {
    try {
      const res = await fetch('http://localhost:11434/api/tags', {
        signal: AbortSignal.timeout(2000),
      })
      if (!res.ok) return { available: false, models: [] }
      const data = await res.json() as { models?: Array<{ name: string }> }
      return { available: true, models: (data.models ?? []).map((m) => m.name) }
    } catch {
      return { available: false, models: [] }
    }
  })

  ipcMain.handle('llm:ollamaPull', async (event, ollamaId: string): Promise<void> => {
    const res = await fetch('http://localhost:11434/api/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: ollamaId, stream: true }),
    })
    if (!res.ok) throw new Error(`Ollama pull failed: ${res.statusText}`)
    if (!res.body) throw new Error('Ollama pull: no response body')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const obj = JSON.parse(line) as { status?: string; completed?: number; total?: number }
          const total = obj.total ?? 0
          const pct = total > 0 ? Math.round(((obj.completed ?? 0) / total) * 100) : 0
          event.sender.send('llm:dl-progress', { modelId: ollamaId, pct, downloaded: obj.completed ?? 0, total })
        } catch { /* skip malformed line */ }
      }
    }
    event.sender.send('llm:dl-progress', { modelId: ollamaId, pct: 100, downloaded: 0, total: 0 })
  })

  ipcMain.handle('llm:ollamaDelete', async (_event, ollamaId: string): Promise<void> => {
    await fetch('http://localhost:11434/api/delete', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: ollamaId }),
    })
  })

  ipcMain.handle('llm:ollamaChat', async (
    event,
    { prompt, systemPrompt, modelId }: { prompt: string; systemPrompt: string; modelId: string }
  ): Promise<void> => {
    activeAbortController = new AbortController()
    let fullText = ''
    try {
      const res = await fetch('http://localhost:11434/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId, prompt, system: systemPrompt, stream: true }),
        signal: activeAbortController.signal,
      })
      if (!res.ok) throw new Error(`Ollama error ${res.status}: ${await res.text()}`)
      if (!res.body) throw new Error('Ollama: no response body')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const obj = JSON.parse(line) as { response?: string; done?: boolean }
            if (obj.response) {
              fullText += obj.response
              event.sender.send('llm:token', obj.response)
            }
          } catch { /* skip */ }
        }
      }
      event.sender.send('llm:done', fullText)
    } catch (err: unknown) {
      const isAbort = err instanceof Error &&
        (err.name === 'AbortError' || err.message.toLowerCase().includes('abort'))
      if (isAbort) {
        event.sender.send('llm:done', fullText)
      } else {
        event.sender.send('llm:error', err instanceof Error ? err.message : String(err))
      }
    } finally {
      activeAbortController = null
    }
  })
}
