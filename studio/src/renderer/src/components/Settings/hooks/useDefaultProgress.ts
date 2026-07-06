import { useEffect, useState } from 'react'
import { apiGetDefaultProgress, apiSetDefaultProgress } from '../../../store/commsApi'

// Loads + persists the app-default board-updates verbosity — the single source of truth for
// how chatty headless board runs are (single agent, Evaluate, decompose, single-executor all
// resolve it server-side when a run doesn't override). Seeds from apiGetDefaultProgress() on
// mount; writes back via apiSetDefaultProgress() on change. Falls back to 'normal' until the
// server responds.
export function useDefaultProgress(): { progress: string; setProgress: (p: string) => void } {
  const [progress, setProgressState] = useState('normal')

  useEffect(() => {
    let alive = true
    void apiGetDefaultProgress().then((p) => {
      if (alive && p) setProgressState(p)
    })
    return () => {
      alive = false
    }
  }, [])

  function setProgress(p: string): void {
    setProgressState(p)
    void apiSetDefaultProgress(p)
  }

  return { progress, setProgress }
}
