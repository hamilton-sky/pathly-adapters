import { useCallback, useEffect, useState } from 'react'
import { fetchHqActionCatalog, saveHqAvailableActions, type HqActionCatalog } from '../../../services/hqActionsApi'

/** Settings → HQ actions: the operator catalog and which of it HQ may use
 *  (server-stored `hq.actions.available`, enforced by the server). */
export function useHqActionAvailability() {
  const [catalog, setCatalog] = useState<HqActionCatalog | null>(null)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let live = true
    void fetchHqActionCatalog().then((c) => {
      if (!live) return
      if (c) setCatalog(c)
      else setFailed(true)
    })
    return () => { live = false }
  }, [])

  const save = useCallback(async (names: string[]) => {
    setSaving(true)
    const next = await saveHqAvailableActions(names)
    setSaving(false)
    if (next) { setCatalog(next); setFailed(false) } else setFailed(true)
  }, [])

  const setAvailable = useCallback((name: string, on: boolean) => {
    if (!catalog) return
    void save(catalog.actions.filter((a) => (a.name === name ? on : a.available)).map((a) => a.name))
  }, [catalog, save])

  const resetDefaults = useCallback(() => {
    if (catalog) void save(catalog.actions.filter((a) => a.default_available).map((a) => a.name))
  }, [catalog, save])

  const isDefault = !!catalog && catalog.actions.every((a) => a.available === a.default_available)
  return { catalog, failed, saving, isDefault, setAvailable, resetDefaults }
}
