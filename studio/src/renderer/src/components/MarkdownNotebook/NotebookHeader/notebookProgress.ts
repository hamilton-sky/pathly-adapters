// Live progress for the notebook's one-shot AI actions (AI Split, AI Analyze).
// Piggybacks on the PTY data stream already forwarded to the renderer
// (terminal:data:<tabId>) — no backend changes. Surfaces an elapsed timer
// (reliable, engine-agnostic liveness) plus the latest meaningful output line.

export interface ActionProgress {
  /** Seconds since the action was spawned. */
  elapsedS: number
  /** Latest non-empty output line (ANSI-stripped, truncated), or ''. */
  detail: string
}

// Strip ANSI escapes. \x1b is ESC, \x07 is BEL.
// CSI = ESC[ … letter (colours, cursor); OSC = ESC] … BEL (title sets).
const ANSI_CSI = /\x1b\[[0-9;?]*[A-Za-z]/g
const ANSI_OSC = /\x1b\][\s\S]*?\x07/g

/** Pull the last meaningful line out of a raw PTY chunk. */
export function lastMeaningfulLine(chunk: string): string {
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

/** Minimum gap between milestone notifications, to avoid toast spam. */
const MILESTONE_THROTTLE_MS = 2500

/**
 * Subscribe to a tab's PTY output and tick an elapsed timer, pushing
 * ActionProgress to `onProgress` (the inline pill timer). When `onMilestone` is
 * given, each genuinely new output line is forwarded — deduped and throttled —
 * so callers can surface it as an app toast. Returns a cleanup that
 * unsubscribes the data feed and stops the timer.
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
