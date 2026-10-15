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
import { createProposalRecorder, recordingFunctions, type HqToolSpec, type ToolProposal } from './llmProposals'
import { stripThinkTags } from './llmText'

interface ModelInfo {
  uri: string
  filename: string
}

const MODEL_REGISTRY: Record<string, ModelInfo> = {
  'qwen3-4b': {
    uri: 'hf:unsloth/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf',
    filename: 'Qwen3-4B-Q4_K_M.gguf',
  },
  'qwen3-8b': {
    uri: 'hf:unsloth/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf',
    filename: 'Qwen3-8B-Q4_K_M.gguf',
  },
  'qwen2.5-coder-7b': {
    uri: 'hf:bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf',
    filename: 'Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf',
  },
  'phi-4-mini': {
    // NOT bartowski/Phi-4-mini-instruct-GGUF — that repo does not exist (HF 401s);
    // bartowski's copy is microsoft_-prefixed. unsloth keeps this exact filename.
    uri: 'hf:unsloth/Phi-4-mini-instruct-GGUF/Phi-4-mini-instruct-Q4_K_M.gguf',
    filename: 'Phi-4-mini-instruct-Q4_K_M.gguf',
  },
  'deepseek-r1-1.5b': {
    uri: 'hf:bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf',
    filename: 'DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf',
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
      // Pin the name: node-llama-cpp otherwise saves `hf_<user>_<file>`, which
      // getModelPath / llm:listCached never find — the download "succeeds" and
      // the model can never be loaded or shown as cached.
      fileName: info.filename,
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
    { prompt, systemPrompt, modelId, maxTokens, contextSize, thoughtBudget, showReasoning, tools }: {
      prompt: string; systemPrompt: string; modelId: string
      maxTokens?: number; contextSize?: number; thoughtBudget?: number; showReasoning?: boolean
      tools?: HqToolSpec[]  // HQ operator: offered as record-only functions (llmProposals.ts)
    }
  ): Promise<{ proposals: ToolProposal[] }> => {
    const { LlamaChatSession } = await loadLlamaCpp()
    const model = await ensureModel(modelId, (pct, text) => {
      event.sender.send('llm:load-progress', { pct, text })
    })
    // An HQ board turn asks for exactly what it needs (~16k). Without a max,
    // node-llama-cpp grows to the model's full window (41k for Qwen3) — ~3.5 GB
    // more KV cache per answer; without a min it could start too small.
    const context = await model.createContext(
      contextSize ? { contextSize: { min: contextSize, max: contextSize } } : undefined,
    )
    const session = new LlamaChatSession({ contextSequence: context.getSequence(), systemPrompt })
    activeAbortController = new AbortController()
    let fullText = ''
    let inThought = false
    const recorder = createProposalRecorder(tools ?? [])
    const emit = (text: string): void => {
      fullText += text
      event.sender.send('llm:token', text)
    }
    const closeThought = (): void => {
      if (inThought) { emit('</think>'); inThought = false }
    }
    try {
      await session.prompt(prompt, {
        signal: activeAbortController.signal,
        maxTokens: maxTokens ?? 512,
        // Qwen3 reasons in a separate "thought" segment whose tokens count
        // against maxTokens (measured 552 thought + 469 answer = cut off at
        // 1024). The budget caps it; 0 turns reasoning off (Fast mode).
        ...(thoughtBudget !== undefined ? { budgets: { thoughtTokens: thoughtBudget } } : {}),
        temperature: 0.7,
        ...(tools?.length ? { functions: recordingFunctions(tools, recorder) } : {}),
        // Deep mode streams the reasoning wrapped in <think>…</think> — the
        // format ThinkingBlock already renders for Ollama. Otherwise onToken
        // streams the answer only (thought segments are not passed to it).
        ...(showReasoning
          ? {
              onResponseChunk: (chunk: { type?: string; segmentType?: string; text: string }) => {
                if (chunk.type === 'segment') {
                  if (chunk.segmentType !== 'thought' || !chunk.text) return
                  if (!inThought) { emit('<think>'); inThought = true }
                  emit(chunk.text)
                } else {
                  closeThought()
                  emit(stripThinkTags(chunk.text))
                }
              },
            }
          : { onToken: (tokens: unknown[]) => emit(stripThinkTags(model.detokenize(tokens))) }),
      })
      closeThought()
      event.sender.send('llm:done', fullText)
    } catch (err: unknown) {
      const isAbort = err instanceof Error &&
        (err.name === 'AbortError' || err.message.toLowerCase().includes('abort'))
      if (isAbort) {
        closeThought()
        event.sender.send('llm:done', fullText)
      } else {
        event.sender.send('llm:error', err instanceof Error ? err.message : String(err))
      }
    } finally {
      try { await context.dispose() } catch { /* ignore */ }
      activeAbortController = null
    }
    return { proposals: recorder.proposals }
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
    { prompt, systemPrompt, modelId, think, numCtx }: {
      prompt: string; systemPrompt: string; modelId: string; think?: boolean; numCtx?: number
    }
  ): Promise<void> => {
    activeAbortController = new AbortController()
    let fullText = ''
    let inThinking = false
    try {
      // Without num_ctx Ollama uses its small default window and silently
      // truncates the START of a longer prompt — the HQ board packet.
      const res = await fetch('http://localhost:11434/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: modelId, prompt, system: systemPrompt, stream: true,
          // Fast sends think:false — omitted, a thinking model (qwen3) reasons anyway.
          ...(think !== undefined ? { think } : {}),
          ...(numCtx ? { options: { num_ctx: numCtx } } : {}),
        }),
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
            const obj = JSON.parse(line) as { response?: string; thinking?: string; done?: boolean }
            if (obj.thinking) {
              if (!inThinking) {
                // Open a single <think> block for all thinking chunks
                const token = `<think>${obj.thinking}`
                fullText += token
                event.sender.send('llm:token', token)
                inThinking = true
              } else {
                fullText += obj.thinking
                event.sender.send('llm:token', obj.thinking)
              }
            } else if (obj.response) {
              if (inThinking) {
                // Close the think block when response starts
                const closeToken = `</think>`
                fullText += closeToken
                event.sender.send('llm:token', closeToken)
                inThinking = false
              }
              fullText += obj.response
              event.sender.send('llm:token', obj.response)
            }
          } catch { /* skip */ }
        }
      }
      // Close unclosed think block if stream ended mid-thinking
      if (inThinking) {
        fullText += '</think>'
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
