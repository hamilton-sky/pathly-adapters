import { useEffect, useRef, useState } from 'react'
import { previewComposedSkill } from '../../../../services/skillComposition'
import type { ComposedSection } from '../../../../services/skillComposition'

const FALLBACK_DEBOUNCE_MS = 200

interface UseFallbackFragmentPreviewResult {
  sections: ComposedSection[]
  loading: boolean
}

/**
 * On-demand preview for a fragment that is currently EXCLUDED from the composition, so
 * it has no sections in the main `/skills/preview` response (only included fragments are
 * requested there). Fetches that one fragment in isolation and keeps only its own
 * sections, discarding the skill-body sections the endpoint always includes alongside it.
 * Pass `fragmentName: null` when the active chip doesn't need this (body/full/included).
 */
export function useFallbackFragmentPreview(
  skill: string,
  fragmentName: string | null,
  projectRoot: string,
): UseFallbackFragmentPreviewResult {
  const [sections, setSections] = useState<ComposedSection[]>([])
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!skill || !fragmentName) {
      setSections([])
      setLoading(false)
      return
    }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setLoading(true)
    debounceRef.current = setTimeout(() => {
      previewComposedSkill(skill, [fragmentName], projectRoot)
        .then((data) => {
          const all = data?.sections ?? []
          setSections(all.filter((s) => s.origin === fragmentName))
        })
        .finally(() => setLoading(false))
    }, FALLBACK_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, fragmentName, projectRoot])

  return { sections, loading }
}
