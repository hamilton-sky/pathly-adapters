import { useEffect, useState } from 'react'
import type { PreviewTab, DrawerTarget } from '../types'

interface Result {
  tab: PreviewTab
  setTab: (t: PreviewTab) => void
  drawer: DrawerTarget | null
  inspect: (target: DrawerTarget) => void
  closeDrawer: () => void
}

/** Preview-pane UI state: which list tab is active and what the inspect drawer shows.
 *  Changing tab or skill closes the drawer. */
export function usePreviewInspector(resetKey: string): Result {
  const [tab, setTabState] = useState<PreviewTab>('fragments')
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null)

  useEffect(() => { setTabState('fragments'); setDrawer(null) }, [resetKey])

  function setTab(t: PreviewTab): void { setTabState(t); setDrawer(null) }
  function inspect(target: DrawerTarget): void { setDrawer(target) }
  function closeDrawer(): void { setDrawer(null) }

  return { tab, setTab, drawer, inspect, closeDrawer }
}
