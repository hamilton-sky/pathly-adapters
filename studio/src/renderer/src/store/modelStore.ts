import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { RECOMMENDED_MODEL_ID, MODEL_CATALOG, BRIGHTSKY_ID } from '../services/modelManager'

const VALID_IDS = new Set([...MODEL_CATALOG.map((m) => m.id), BRIGHTSKY_ID])

/** The default before v1. persist() saves the default as if it were a choice, so
 *  a saved v0 'phi-4-mini' is almost always "never picked" — move it to the new
 *  default (qwen3-8b) once. Anyone who really wants Phi-4 Mini re-picks it. */
const V0_DEFAULT_MODEL_ID = 'phi-4-mini'

export function migrateModelSelection(persisted: unknown, version: number): unknown {
  const s = (persisted ?? {}) as { selectedModelId?: string }
  if (version < 1 && s.selectedModelId === V0_DEFAULT_MODEL_ID) {
    return { ...s, selectedModelId: RECOMMENDED_MODEL_ID }
  }
  return persisted
}

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
      version: 1,
      migrate: (persisted, version) => migrateModelSelection(persisted, version) as ModelStore,
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
