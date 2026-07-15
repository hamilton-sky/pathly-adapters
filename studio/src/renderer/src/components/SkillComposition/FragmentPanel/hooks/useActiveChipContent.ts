import { useMemo } from 'react'
import type { ComposedSection } from '../../../../services/skillComposition'
import { BODY_CHIP_ID, FULL_CHIP_ID } from '../../chipIds'
import { useFallbackFragmentPreview } from './useFallbackFragmentPreview'

interface ActiveChipContent {
  title: string
  sections: ComposedSection[]
  loading: boolean
}

/**
 * Resolves the sections to render for the active chip. Body + Full composed always read
 * from the main preview response (grouped by `origin`); an INCLUDED fragment does too
 * (its sections are already in that response). An EXCLUDED fragment has no sections there
 * (it wasn't sent to `/skills/preview`), so it falls back to an on-demand single-fragment
 * preview fetch.
 */
export function useActiveChipContent(
  skill: string,
  projectRoot: string,
  fragments: string[],
  sections: ComposedSection[],
  previewLoading: boolean,
  activeChipId: string,
): ActiveChipContent {
  const isSpecial = activeChipId === BODY_CHIP_ID || activeChipId === FULL_CHIP_ID
  const needsFallback = !isSpecial && !fragments.includes(activeChipId)

  const fallback = useFallbackFragmentPreview(skill, needsFallback ? activeChipId : null, projectRoot)

  return useMemo(() => {
    if (activeChipId === FULL_CHIP_ID) {
      return { title: 'Full composed', sections, loading: previewLoading }
    }
    if (activeChipId === BODY_CHIP_ID) {
      return {
        title: 'Skill body',
        sections: sections.filter((s) => s.origin === 'body'),
        loading: previewLoading,
      }
    }
    if (needsFallback) {
      return { title: activeChipId, sections: fallback.sections, loading: fallback.loading }
    }
    return {
      title: activeChipId,
      sections: sections.filter((s) => s.origin === activeChipId),
      loading: previewLoading,
    }
  }, [activeChipId, sections, previewLoading, needsFallback, fallback.sections, fallback.loading])
}
