import { useCallback, useEffect } from 'react'
import { BRIGHTSKY_ID } from '../../../services/modelManager'
import { getModelById } from '../../../services/modelManager/catalog'
import { getCachedModelIds } from '../../../lib/llmBridge'
import { ollamaHasTag } from '../../../lib/ollamaTag'
import { useModelStore } from '../../../store/modelStore'
import { useBrightskyStore } from '../../../store/brightskyStore'

/** Why a local model can't be picked yet (undefined: it can). Refreshes the
 *  downloaded-model list on mount — only HQ's model picker fills it otherwise. */
export function useModelReadiness(): (id: string) => string | undefined {
  const cached = useModelStore((s) => s.cachedModelIds)
  const setCached = useModelStore((s) => s.setCached)
  const ollamaIds = useModelStore((s) => s.ollamaModelIds)
  const brightsky = useBrightskyStore((s) => s.authenticated)

  useEffect(() => {
    void getCachedModelIds().then(setCached).catch(() => {})
  }, [setCached])

  return useCallback(
    (id: string) => {
      if (id === BRIGHTSKY_ID) return brightsky ? undefined : 'Sign in to Brightsky first'
      if (cached.includes(id)) return undefined
      if (ollamaHasTag(getModelById(id)?.ollamaId ?? '', ollamaIds)) return undefined
      return "Not downloaded — download it in HQ's model menu"
    },
    [cached, ollamaIds, brightsky],
  )
}
