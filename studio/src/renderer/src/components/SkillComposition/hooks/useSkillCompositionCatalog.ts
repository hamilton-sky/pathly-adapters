import { useCallback, useEffect, useState } from 'react'
import { fetchSkillComposition } from '../../../services/skillComposition'
import type { SkillCompositionCatalog } from '../../../services/skillComposition'

interface UseSkillCompositionCatalogResult {
  catalog: SkillCompositionCatalog | null
  loading: boolean
  error: string | null
  selectedSkill: string | null
  setSelectedSkill: (skill: string) => void
  refetch: () => void
}

/** Data hook: loads the merged skill/fragment catalog and tracks the selected skill. */
export function useSkillCompositionCatalog(projectRoot: string): UseSkillCompositionCatalogResult {
  const [catalog, setCatalog] = useState<SkillCompositionCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    if (!projectRoot) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSkillComposition(projectRoot)
      .then((data) => {
        if (cancelled) return
        if (!data) {
          setError('Could not load skill composition — is the Pathly server running?')
          setCatalog(null)
          return
        }
        setCatalog(data)
        setSelectedSkill((prev) => (prev && data.skills[prev] ? prev : Object.keys(data.skills).sort()[0] ?? null))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectRoot, reloadTick])

  const refetch = useCallback(() => setReloadTick((t) => t + 1), [])

  return { catalog, loading, error, selectedSkill, setSelectedSkill, refetch }
}
