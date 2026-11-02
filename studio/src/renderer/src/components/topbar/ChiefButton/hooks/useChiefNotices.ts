// The project's ended, unread chief runs (GET /chief/notices): read when the button mounts or the
// project changes, again every 15 s while the window has focus, and at once when it regains focus.
// A failed read keeps the last list. `markRead` drops the runs from the list and marks them read
// on the server (POST /chief/notices/read); if that fails, the next read brings them back.
import { useCallback, useEffect, useState } from 'react'
import {
  getChiefNotices,
  markChiefNoticesRead,
  type ChiefNotice,
} from '../../../../services/chiefApi'

export const NOTICE_POLL_MS = 15_000

export function useChiefNotices(projectRoot: string): {
  notices: ChiefNotice[]
  markRead: (runIds: string[]) => Promise<void>
} {
  const [notices, setNotices] = useState<ChiefNotice[]>([])

  useEffect(() => {
    setNotices([])
    if (!projectRoot) return
    let cancelled = false
    const load = (): void => {
      void getChiefNotices(projectRoot).then((list) => {
        if (!cancelled && list) setNotices(list)
      })
    }
    const tick = (): void => {
      if (document.hasFocus()) load()
    }
    load()
    const id = window.setInterval(tick, NOTICE_POLL_MS)
    window.addEventListener('focus', load)
    return () => {
      cancelled = true
      window.clearInterval(id)
      window.removeEventListener('focus', load)
    }
  }, [projectRoot])

  const markRead = useCallback(
    async (runIds: string[]) => {
      if (!projectRoot || runIds.length === 0) return
      setNotices((list) => list.filter((n) => !runIds.includes(n.run_id)))
      await markChiefNoticesRead(projectRoot, runIds)
    },
    [projectRoot],
  )

  return { notices, markRead }
}
