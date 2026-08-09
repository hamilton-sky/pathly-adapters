import { useEffect, useState } from 'react'
import { apiGetLoggingConfig, apiSetLoggingConfig } from '../../../../store/commsApi'

// Loads + persists whether agents narrate to the board. This governs the comms-post /
// progress-logging fragments ONLY — the cost/monitor spine (run history, cost, gate liveness) is
// the control plane itself and is always on (never represented here). Verbosity is a separate
// setting (useDefaultProgress) since it shares the board:default_progress key. Defaults to ON
// until the server responds.
export function useLoggingConfig(): {
  boardEnabled: boolean
  setBoardEnabled: (enabled: boolean) => void
} {
  const [boardEnabled, setState] = useState(true)

  useEffect(() => {
    let alive = true
    void apiGetLoggingConfig().then((c) => {
      if (alive && c) setState(c.board)
    })
    return () => {
      alive = false
    }
  }, [])

  function setBoardEnabled(enabled: boolean): void {
    setState(enabled)
    void apiSetLoggingConfig(enabled)
  }

  return { boardEnabled, setBoardEnabled }
}
