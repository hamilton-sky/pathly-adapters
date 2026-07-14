import { useEffect, useRef, useState } from 'react'
import { previewComposedSkill } from '../../../../services/skillComposition'
import type { ComposedSection } from '../../../../services/skillComposition'

const PREVIEW_DEBOUNCE_MS = 350

interface UseComposedPreviewResult {
  sections: ComposedSection[]
  tokens: number
  loading: boolean
}

/** Debounced live preview of `skill` composed with the current toggled fragment list. */
export function useComposedPreview(
  skill: string,
  fragments: string[],
  projectRoot: string,
): UseComposedPreviewResult {
  const [sections, setSections] = useState<ComposedSection[]>([])
  const [tokens, setTokens] = useState(0)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!skill) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setLoading(true)
    debounceRef.current = setTimeout(() => {
      previewComposedSkill(skill, fragments, projectRoot)
        .then((data) => {
          setSections(data?.sections ?? [])
          setTokens(data?.tokens ?? 0)
        })
        .finally(() => setLoading(false))
    }, PREVIEW_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, fragments, projectRoot])

  return { sections, tokens, loading }
}
