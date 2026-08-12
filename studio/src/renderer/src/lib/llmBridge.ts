// IPC bridge — node-llama-cpp (Electron 33+) and Ollama backends.
// On Electron 28 the node-llama-cpp path will be unavailable; Ollama is the primary backend.

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

export async function askLlm(
  prompt: string,
  systemPrompt: string,
  onChunk: (text: string) => void
): Promise<string> {
  const { useModelStore } = await import('../store/modelStore')
  const modelId = useModelStore.getState().selectedModelId

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
    window.pathly.llm.chat(prompt, systemPrompt, modelId).catch((err) => {
      removeToken(); removeDone(); removeError()
      reject(err)
    })
  })
}

export function abortLlm(): void {
  window.pathly.llm.abort().catch(() => {})
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
  think = false
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
    window.pathly.llm.ollamaChat(prompt, systemPrompt, ollamaModelId, think).catch((err) => {
      removeToken(); removeDone(); removeError()
      reject(err)
    })
  })
}
