import { useEffect, useRef, useState } from 'react'
import { previewComposedSkill } from '../../../../services/skillComposition'
import type { ComposedSection } from '../../../../services/skillComposition'

const DEBOUNCE_MS = 150

interface UseFragmentContentResult {
  sections: ComposedSection[]
  loading: boolean
}

/**
 * On-demand content for ONE fragment, composed in isolation and filtered to its own
 * `origin` sections (the endpoint always returns the skill body alongside — discarded here).
 * Used for EVERY fragment chip regardless of include/exclude state, so an included and an
 * excluded fragment inspect identically — this uniformity is what fixes the old
 * "excluded fragment shows No content" bug (the included path filtered the composed
 * preview, the excluded path fetched separately, and only one was ever right). Pass
 * `fragmentName: null` for the body/full chips (they read the composed preview instead).
 * A `cancelled` guard drops a stale response so fast chip-switching can't show the wrong
 * fragment's text.
 */
export function useFragmentContent(
  skill: string,
  fragmentName: string | null,
  projectRoot: string,
): UseFragmentContentResult {
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
    let cancelled = false
    debounceRef.current = setTimeout(() => {
      previewComposedSkill(skill, [fragmentName], projectRoot)
        .then((data) => {
          if (cancelled) return
          const all = data?.sections ?? []
          setSections(all.filter((s) => s.origin === fragmentName))
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, fragmentName, projectRoot])

  return { sections, loading }
}
