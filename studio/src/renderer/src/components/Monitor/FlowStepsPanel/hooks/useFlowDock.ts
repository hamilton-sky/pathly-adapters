import { useCallback, useState } from 'react'

const KEY = 'pathly:flowDockCollapsed'

/**
 * Collapse state for the flow dock, persisted to localStorage so the user's expand/collapse
 * choice survives reloads (same affordance pattern as the Skill Composition sidebar).
 */
export function useFlowDock(): { collapsed: boolean; toggle: () => void } {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(KEY) === '1'
    } catch {
      return false
    }
  })

  const toggle = useCallback(() => {
    setCollapsed((c) => {
      const next = !c
      try {
        localStorage.setItem(KEY, next ? '1' : '0')
      } catch {
        /* ignore — a broken localStorage must never break the dock */
      }
      return next
    })
  }, [])

  return { collapsed, toggle }
}
