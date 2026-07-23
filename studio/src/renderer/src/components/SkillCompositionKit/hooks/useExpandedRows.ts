import { useCallback, useEffect, useState } from 'react'

interface Result {
  isExpanded: (name: string) => boolean
  toggle: (name: string) => void
}

/** Tracks which Config rows are expanded inline. Clears when resetKey (the skill) changes. */
export function useExpandedRows(resetKey: string): Result {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  useEffect(() => { setOpen({}) }, [resetKey])
  const toggle = useCallback((name: string) => {
    setOpen((prev) => ({ ...prev, [name]: !prev[name] }))
  }, [])
  const isExpanded = useCallback((name: string) => !!open[name], [open])
  return { isExpanded, toggle }
}
