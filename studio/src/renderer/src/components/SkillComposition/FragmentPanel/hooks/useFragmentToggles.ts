import { useEffect, useRef, useState } from 'react'
import { saveSkillCompositionOverride, resetSkillComposition } from '../../../../services/skillComposition'

const SAVE_DEBOUNCE_MS = 500

interface UseFragmentTogglesResult {
  fragments: string[]
  toggleFragment: (name: string) => void
  resetToDefault: () => void
  saving: boolean
  resetting: boolean
}

/**
 * Local toggle state for the selected skill's fragment stack, saved to the per-project
 * override on a debounce. Re-seeds from `initialFragments` when the selected skill changes
 * or when `source` flips (first override save, or a reset back to the packaged default) —
 * never on an in-place same-source refetch, so an in-flight debounced edit is never
 * clobbered by the refetch its own save just triggered.
 */
export function useFragmentToggles(
  skill: string,
  initialFragments: string[],
  source: 'manifest' | 'override',
  projectRoot: string,
  onSaved: () => void,
): UseFragmentTogglesResult {
  const [fragments, setFragments] = useState<string[]>(initialFragments)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const skipNextSaveRef = useRef(true)

  useEffect(() => {
    skipNextSaveRef.current = true
    setFragments(initialFragments)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, source])

  useEffect(() => {
    if (skipNextSaveRef.current) {
      skipNextSaveRef.current = false
      return
    }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSaving(true)
      saveSkillCompositionOverride(skill, fragments, projectRoot)
        .then(() => onSaved())
        .finally(() => setSaving(false))
    }, SAVE_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fragments])

  function toggleFragment(name: string): void {
    setFragments((prev) => (prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name]))
  }

  function resetToDefault(): void {
    setResetting(true)
    resetSkillComposition(skill, projectRoot)
      .then(() => onSaved())
      .finally(() => setResetting(false))
  }

  return { fragments, toggleFragment, resetToDefault, saving, resetting }
}
