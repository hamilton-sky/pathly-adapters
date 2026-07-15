import { useMemo } from 'react'
import type { ComposedSection } from '../../../../services/skillComposition'
import { BODY_CHIP_ID, FULL_CHIP_ID } from '../../chipIds'
import { useFragmentContent } from './useFragmentContent'

interface ActiveChipContent {
  title: string
  sections: ComposedSection[]
  loading: boolean
}

/**
 * Resolves the sections to render for the active chip.
 * - `Full composed` → the whole composed preview (skill body + every included fragment).
 * - `Skill body` → the body-origin slice of that preview.
 * - any fragment chip (included OR excluded) → an on-demand single-fragment fetch
 *   (`useFragmentContent`), so both inspect identically. That uniformity is the fix for the
 *   old bug where selecting an excluded fragment rendered "No content".
 */
export function useActiveChipContent(
  skill: string,
  projectRoot: string,
  sections: ComposedSection[],
  previewLoading: boolean,
  activeChipId: string,
): ActiveChipContent {
  const isFragment = activeChipId !== BODY_CHIP_ID && activeChipId !== FULL_CHIP_ID
  const fragment = useFragmentContent(skill, isFragment ? activeChipId : null, projectRoot)

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
    return { title: activeChipId, sections: fragment.sections, loading: fragment.loading }
  }, [activeChipId, sections, previewLoading, fragment.sections, fragment.loading])
}
