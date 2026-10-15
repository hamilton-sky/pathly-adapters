// IPC bridge — node-llama-cpp (Electron 33+) and Ollama backends.
// On Electron 28 the node-llama-cpp path will be unavailable; Ollama is the primary backend.

import { runLocal, stopChat } from './localModelQueue'

// ── node-llama-cpp (local GGUF, requires Electron 33+) ───────────────────────

export async function getEngine(
  modelId: string,
  onProgress?: (pct: number, text?: string) => void
): Promise<void> {
  let removeProgress: (() => void) | undefined
  if (onProgress) {
    removeProgress = window.pathly.llm.onLoadProgress(({ pct, text }) => onProgress(pct, text))
  }
  try {
    await window.pathly.llm.load(modelId)
  } finally {
    removeProgress?.()
  }
}

export async function getCachedModelIds(): Promise<string[]> {
  return window.pathly.llm.listCached()
}

export async function downloadModel(
  modelId: string,
  onProgress: (pct: number, text?: string) => void
): Promise<void> {
  const removeDownload = window.pathly.llm.onDownloadProgress(({ modelId: id, pct }) => {
    if (id === modelId) onProgress(pct, `downloading… ${pct}%`)
  })
  try {
    await window.pathly.llm.download(modelId)
  } finally {
    removeDownload()
  }

  const removeLoad = window.pathly.llm.onLoadProgress(({ pct, text }) => onProgress(pct, text))
  try {
    await window.pathly.llm.load(modelId)
  } finally {
    removeLoad()
  }
}

export async function deleteModel(modelId: string): Promise<void> {
  await window.pathly.llm.delete(modelId)
}

type ChatOpts = { maxTokens?: number; contextSize?: number; thoughtBudget?: number; showReasoning?: boolean; tools?: HqToolSpec[] }

/** One built-in call: stream to *onChunk*, resolve with the text and any tool
 *  proposals. Only ever called inside runLocal — the token/done events are not
 *  tagged per call, so a second call in flight would read this one's text. */
async function chatOnce(
  prompt: string,
  systemPrompt: string,
  modelId: string,
  onChunk: (text: string) => void,
  opts?: ChatOpts,
): Promise<{ text: string; proposals: HqToolProposal[] }> {
  let text = ''
  let error: string | null = null
  const removeToken = window.pathly.llm.onToken(onChunk)
  const removeDone = window.pathly.llm.onDone((fullText) => { text = fullText })
  const removeError = window.pathly.llm.onError((msg) => { error = msg })
  try {
    // main sends llm:done / llm:error before this invoke resolves.
    const res = await window.pathly.llm.chat(prompt, systemPrompt, modelId, opts)
    if (error) throw new Error(error)
    return { text, proposals: res?.proposals ?? [] }
  } finally {
    removeToken(); removeDone(); removeError()
  }
}

async function selectedModel(): Promise<string> {
  const { useModelStore } = await import('../store/modelStore')
  return useModelStore.getState().selectedModelId
}

/** HQ's answer on the built-in runtime (queued behind any running summary). */
export async function askLlm(
  prompt: string,
  systemPrompt: string,
  onChunk: (text: string) => void,
  /** maxTokens: generation cap, thinking included (default 512). contextSize:
   *  the context to allocate — a board-grounded HQ turn is far larger than a
   *  chat line. thoughtBudget: caps a thinking model's reasoning so it cannot
   *  spend the whole maxTokens and truncate the answer. */
  opts?: { maxTokens?: number; contextSize?: number; thoughtBudget?: number; showReasoning?: boolean }
): Promise<string> {
  const modelId = await selectedModel()
  return runLocal('chat', async () => (await chatOnce(prompt, systemPrompt, modelId, onChunk, opts)).text, '')
}

/** HQ operator turn on the built-in runtime: like askLlm, but the model is
 *  offered *tools* as record-only functions. Resolves with the streamed text
 *  AND the calls it proposed — none of them executed (main/ipc/llmProposals.ts). */
export async function askLlmWithTools(
  prompt: string,
  systemPrompt: string,
  onChunk: (text: string) => void,
  opts: ChatOpts & { tools: HqToolSpec[] }
): Promise<{ text: string; proposals: HqToolProposal[] }> {
  const modelId = await selectedModel()
  return runLocal('chat', () => chatOnce(prompt, systemPrompt, modelId, onChunk, opts), { text: '', proposals: [] })
}

/** A background one-shot (artifact summaries) on *modelId* — not the HQ picker's
 *  model. Queued like every built-in call; HQ's Stop never cancels it. */
export async function askLlmBackground(prompt: string, modelId: string, opts: ChatOpts): Promise<string> {
  return runLocal('background', async () => (await chatOnce(prompt, '', modelId, () => {}, opts)).text, '')
}

/** HQ's Stop: ends HQ's answer (running or still queued); never a summary. */
export function abortLlm(): void {
  stopChat(() => { window.pathly.llm.abort().catch(() => {}) })
}

// ── Ollama backend (works on any Electron version) ────────────────────────────

async function checkOllama(): Promise<{ available: boolean; models: string[] }> {
  return window.pathly.llm.ollamaAvailable()
}

export async function pullOllamaModel(
  ollamaId: string,
  onProgress: (pct: number, text?: string) => void
): Promise<void> {
  const removeDownload = window.pathly.llm.onDownloadProgress(({ modelId: id, pct }) => {
    if (id === ollamaId) onProgress(pct, `downloading… ${pct}%`)
  })
  try {
    await window.pathly.llm.ollamaPull(ollamaId)
  } finally {
    removeDownload()
  }
}

export async function deleteOllamaModel(ollamaId: string): Promise<void> {
  await window.pathly.llm.ollamaDelete(ollamaId)
}

export async function askOllama(
  prompt: string,
  systemPrompt: string,
  ollamaModelId: string,
  onChunk: (text: string) => void,
  /** true: reason (Deep), false: don't (Fast), undefined: the model's default. */
  think?: boolean,
  /** Ollama's num_ctx. Unset, Ollama uses its small default window and
   *  silently drops the START of a longer prompt (an HQ board packet). */
  numCtx?: number
): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const removeToken = window.pathly.llm.onToken(onChunk)
    const removeDone = window.pathly.llm.onDone((fullText) => {
      removeToken(); removeDone(); removeError()
      resolve(fullText)
    })
    const removeError = window.pathly.llm.onError((msg) => {
      removeToken(); removeDone(); removeError()
      reject(new Error(msg))
    })
    window.pathly.llm.ollamaChat(prompt, systemPrompt, ollamaModelId, think, numCtx).catch((err) => {
      removeToken(); removeDone(); removeError()
      reject(err)
    })
  })
}
