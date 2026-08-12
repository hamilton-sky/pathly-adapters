// Shared progress infrastructure for one-shot AI actions.
// Extracted from MarkdownEditor/EditorHeader/editorProgress.ts — that file
// now re-exports from here so notebook code needs no import-path changes.

import { useState, useEffect } from 'react'

export interface ActionProgress {
  /** Seconds since the action was spawned. */
  elapsedS: number
  /** Latest non-empty output line (ANSI-stripped, truncated), or ''. */
  detail: string
}

const ANSI_CSI = /\x1b\[[0-9;?]*[A-Za-z]/g
const ANSI_OSC = /\x1b\][\s\S]*?\x07/g

/** Pull the last meaningful line out of a raw PTY chunk. */
function lastMeaningfulLine(chunk: string): string {
  const clean = chunk
    .replace(ANSI_CSI, '')
    .replace(ANSI_OSC, '')
    .replace(/\x1b/g, '')
    .replace(/\r/g, '\n')
    .replace(/[\b\f\v]/g, '')
  const lines = clean.split('\n').map((l) => l.trim()).filter(Boolean)
  const last = lines[lines.length - 1] ?? ''
  return last.length > 80 ? last.slice(0, 79) + '…' : last
}

/** Format elapsed seconds as m:ss. */
export function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60)
  return `${m}:${(s % 60).toString().padStart(2, '0')}`
}

const MILESTONE_THROTTLE_MS = 2500

/**
 * Subscribe to a tab's PTY output and tick an elapsed timer.
 * Returns a cleanup that unsubscribes and stops the timer.
 */
export function attachProgress(
  tabId: string,
  onProgress: (p: ActionProgress) => void,
  onMilestone?: (line: string) => void,
): () => void {
  const startTs = Date.now()
  let detail = ''
  let lastPushed = ''
  let lastPushTs = 0
  const dataUnsub = window.pathly.terminal.onData(tabId, (chunk: string) => {
    const line = lastMeaningfulLine(chunk)
    if (!line) return
    detail = line
    if (onMilestone && line !== lastPushed) {
      const now = Date.now()
      if (now - lastPushTs >= MILESTONE_THROTTLE_MS) {
        lastPushed = line
        lastPushTs = now
        onMilestone(line)
      }
    }
  })
  const tick = () => onProgress({ elapsedS: Math.max(0, Math.round((Date.now() - startTs) / 1000)), detail })
  tick()
  const timer = window.setInterval(tick, 1000)
  return () => { dataUnsub(); window.clearInterval(timer) }
}

/**
 * Hook that ticks elapsed seconds from a stored start timestamp (no PTY required).
 * Used by board/goal executors that know when they started but don't have a tabId.
 * Returns null when startedAt is undefined — pill renders idle.
 */
export function useElapsedProgress(startedAt: number | undefined): ActionProgress | null {
  const [elapsedS, setElapsedS] = useState<number>(
    startedAt ? Math.max(0, Math.round((Date.now() - startedAt) / 1000)) : 0,
  )

  useEffect(() => {
    if (!startedAt) { setElapsedS(0); return }
    setElapsedS(Math.max(0, Math.round((Date.now() - startedAt) / 1000)))
    const t = window.setInterval(() => {
      setElapsedS(Math.max(0, Math.round((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(t)
  }, [startedAt])

  if (!startedAt) return null
  return { elapsedS, detail: '' }
}
