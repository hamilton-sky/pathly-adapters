import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { RECOMMENDED_MODEL_ID, WEB_LLM_MODELS } from '../data/models'

const VALID_IDS = new Set([...WEB_LLM_MODELS.map((m) => m.id), 'brightsky'])

export interface ModelStore {
  selectedModelId: string
  responseMode: 'fast' | 'deep'
  cachedModelIds: string[]
  downloadProgress: Record<string, number>
  /** Whether Ollama is running locally (null = not yet checked) */
  ollamaAvailable: boolean | null
  /** Ollama model IDs currently installed (e.g. 'phi4-mini:latest') */
  ollamaModelIds: string[]
  setSelectedModel: (id: string) => void
  setResponseMode: (mode: 'fast' | 'deep') => void
  setCached: (ids: string[]) => void
  setProgress: (id: string, pct: number) => void
  setOllama: (available: boolean, modelIds: string[]) => void
}

export const useModelStore = create<ModelStore>()(
  persist(
    (set) => ({
      selectedModelId: RECOMMENDED_MODEL_ID,
      responseMode: 'fast',
      cachedModelIds: [],
      downloadProgress: {},
      ollamaAvailable: null,
      ollamaModelIds: [],

      setSelectedModel: (id) => set({ selectedModelId: id }),

      setResponseMode: (mode) => set({ responseMode: mode }),

      setCached: (ids) => set({ cachedModelIds: ids }),

      setProgress: (id, pct) =>
        set((s) => ({
          downloadProgress: { ...s.downloadProgress, [id]: pct },
        })),

      setOllama: (available, modelIds) =>
        set({ ollamaAvailable: available, ollamaModelIds: modelIds }),
    }),
    {
      name: 'pathly-model-id',
      partialize: (s) => ({ selectedModelId: s.selectedModelId, responseMode: s.responseMode }),
      // Migrate old MLC model IDs (e.g. 'Phi-4-mini-instruct-q4f16_1-MLC') to new short IDs
      merge: (persisted, current) => {
        const saved = (persisted as { selectedModelId?: string })?.selectedModelId
        const responseMode = (persisted as { responseMode?: 'fast' | 'deep' })?.responseMode === 'deep'
          ? 'deep'
          : 'fast'
        const validId = saved && VALID_IDS.has(saved) ? saved : RECOMMENDED_MODEL_ID
        return { ...current, selectedModelId: validId, responseMode }
      },
    }
  )
)
