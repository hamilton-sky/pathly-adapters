// useMergedPresets — merge the built-in presets a host passes with the user's DB-backed
// library prompts, so a "＋ saved" prompt appears in the SAME dropdown as the built-ins.
//
// The host owns selection + resolution from its `presets` array (see PromptPeekModal), so
// the merge must live in the array itself — not hidden inside PromptActionConfig. This hook
// returns that merged array plus an `addPreset(name, body)` that persists to the library and
// refetches. `library` is optional: when omitted, presets === builtins and addPreset no-ops,
// so a host that doesn't opt in is unchanged.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { PromptPreset } from './presetTypes'
import {
  listUserPrompts,
  saveUserPrompt,
  type PromptLibraryRow,
} from '../../../services/promptLibrary'

export interface PromptLibraryRef {
  kind: 'preset' | 'ability'
  category: string
  projectRoot?: string
}

function rowToPreset(row: PromptLibraryRow): PromptPreset {
  return {
    name: row.name,
    label: row.label || row.name,
    hint: row.hint || 'saved prompt',
    prompt: row.body,
    skillRef: row.skill_ref || undefined,
  }
}

export interface MergedPresets {
  presets: PromptPreset[]
  addPreset: (name: string, body: string) => Promise<void>
  reload: () => void
}

export function useMergedPresets(
  builtins: PromptPreset[],
  library?: PromptLibraryRef,
): MergedPresets {
  const [userPresets, setUserPresets] = useState<PromptPreset[]>([])
  const [nonce, setNonce] = useState(0)
  const kind = library?.kind
  const category = library?.category
  const projectRoot = library?.projectRoot

  useEffect(() => {
    if (!kind || !category) {
      setUserPresets([])
      return
    }
    let cancelled = false
    void listUserPrompts({ kind, category, projectRoot }).then((rows) => {
      if (!cancelled) setUserPresets(rows.map(rowToPreset))
    })
    return () => {
      cancelled = true
    }
  }, [kind, category, projectRoot, nonce])

  const addPreset = useCallback(
    async (name: string, body: string) => {
      const n = name.trim()
      if (!kind || !category || !n || !body.trim()) return
      await saveUserPrompt({ kind, category, name: n, label: n, body, projectRoot })
      setNonce((v) => v + 1)
    },
    [kind, category, projectRoot],
  )

  // Built-ins first, then user prompts. A user prompt whose name matches a built-in
  // overrides it in place (Map keeps first-seen order, later set replaces the value).
  const presets = useMemo(() => {
    const byName = new Map<string, PromptPreset>()
    for (const p of builtins) byName.set(p.name, p)
    for (const p of userPresets) byName.set(p.name, p)
    return Array.from(byName.values())
  }, [builtins, userPresets])

  const reload = useCallback(() => setNonce((v) => v + 1), [])

  return { presets, addPreset, reload }
}
