import { useEffect, useRef, useState } from 'react'
import { saveSkillCompositionOverride, resetSkillComposition } from '../integration'
import type { SkillSource } from '../types'

const SAVE_DEBOUNCE_MS = 500

interface Result {
  fragments: string[]
  toggleFragment: (name: string) => void
  resetToDefault: () => void
  saving: boolean
  resetting: boolean
}

/**
 * Local toggle state for the selected skill's fragment stack, persisted to the per-project
 * override on a debounce. Re-seeds from initialFragments when the skill changes or source
 * flips (first override save, or a reset to the packaged default) — never on an in-place
 * same-source refetch, so an in-flight debounced edit is never clobbered by the refetch its
 * own save triggered.
 */
export function useFragmentToggles(
  skill: string,
  initialFragments: string[],
  source: SkillSource,
  projectRoot: string,
  onSaved: () => void,
): Result {
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
    if (skipNextSaveRef.current) { skipNextSaveRef.current = false; return }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSaving(true)
      saveSkillCompositionOverride(skill, fragments, projectRoot)
        .then(() => onSaved())
        .finally(() => setSaving(false))
    }, SAVE_DEBOUNCE_MS)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
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
