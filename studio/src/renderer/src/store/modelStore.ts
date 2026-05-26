import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { RECOMMENDED_MODEL_ID } from '../data/models'

export interface ModelStore {
  selectedModelId: string
  cachedModelIds: string[]
  downloadProgress: Record<string, number>
  setSelectedModel: (id: string) => void
  setCached: (ids: string[]) => void
  setProgress: (id: string, pct: number) => void
}

export const useModelStore = create<ModelStore>()(
  persist(
    (set) => ({
      selectedModelId: RECOMMENDED_MODEL_ID,
      cachedModelIds: [],
      downloadProgress: {},

      setSelectedModel: (id) => set({ selectedModelId: id }),

      setCached: (ids) => set({ cachedModelIds: ids }),

      setProgress: (id, pct) =>
        set((s) => ({
          downloadProgress: { ...s.downloadProgress, [id]: pct },
        })),
    }),
    {
      name: 'pathly-model-id',
      partialize: (s) => ({ selectedModelId: s.selectedModelId }),
    }
  )
)
