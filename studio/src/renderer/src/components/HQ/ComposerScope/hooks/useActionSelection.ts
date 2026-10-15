import { useEffect, useMemo, useState } from 'react'
import { WEB_LLM_MODELS } from '../../../../data/models'
import { ollamaHasTag } from '../../../../lib/ollamaTag'
import { fetchHqActionCatalog, type HqActionCatalog, type HqCatalogAction } from '../../../../services/hqActionsApi'
import { MAX_HQ_ACTIONS, useHqActionsStore } from '../../../../store/hqActionsStore'
import { useModelStore } from '../../../../store/modelStore'

/** The composer's Actions tab state: the catalog actions Settings allows, which
 *  of them are ticked for the next question (at most MAX_HQ_ACTIONS), and
 *  whether the selected runtime can act at all (built-in only — Ollama keeps
 *  HQ read-only). Refetches the catalog each time the popover opens, so a
 *  Settings change shows up without a reload. */
export function useActionSelection(popoverOpen: boolean) {
  const [catalog, setCatalog] = useState<HqActionCatalog | null>(null)
  const ticked = useHqActionsStore((s) => s.enabled)
  const toggle = useHqActionsStore((s) => s.toggle)
  const addMany = useHqActionsStore((s) => s.addMany)
  const clear = useHqActionsStore((s) => s.clear)
  const selectedModelId = useModelStore((s) => s.selectedModelId)
  const ollamaModelIds = useModelStore((s) => s.ollamaModelIds)

  useEffect(() => {
    let live = true
    void fetchHqActionCatalog().then((c) => { if (live && c) setCatalog(c) })
    return () => { live = false }
  }, [popoverOpen])

  // A tick for an action Settings turned off can't be sent: drop it, so it
  // doesn't hold one of the 8 slots out of sight.
  useEffect(() => {
    if (!catalog) return
    const allowed = new Set(catalog.actions.filter((a) => a.available).map((a) => a.name))
    const kept = ticked.filter((n) => allowed.has(n))
    if (kept.length !== ticked.length) useHqActionsStore.setState({ enabled: kept })
  }, [catalog, ticked])

  return useMemo(() => {
    const available: HqCatalogAction[] = catalog?.actions.filter((a) => a.available) ?? []
    const enabled = available.filter((a) => ticked.includes(a.name))
    const tag = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)?.ollamaId ?? ''
    return {
      catalog,
      available,
      ticked,
      enabledCount: enabled.length,
      atCap: ticked.length >= MAX_HQ_ACTIONS,
      schemaTokens: enabled.reduce((n, a) => n + a.schema_tokens, 0),
      builtIn: selectedModelId !== 'brightsky' && !ollamaHasTag(tag, ollamaModelIds),
      toggle,
      applyPreset: (names: string[]) => addMany(names.filter((n) => available.some((a) => a.name === n))),
      clear,
    }
  }, [catalog, ticked, selectedModelId, ollamaModelIds, toggle, addMany, clear])
}
