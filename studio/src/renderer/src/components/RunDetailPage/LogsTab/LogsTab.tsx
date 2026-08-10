import type { RunDetailLog } from '../types'
import s from './LogsTab.module.css'

interface Props {
  logs: RunDetailLog[]
}

// Logs tab: per-stage prompt + stdout. prompt_sent is NULL for renderer one-shots (the gate sends
// only stdout) and for P0 flow runs (board context is embedded in the prompt, discrete in P1) — a
// note explains that instead of an empty block. Empty stdout → an explicit "none captured" line.
export function LogsTab({ logs }: Props): JSX.Element {
  if (logs.length === 0) {
    return <div className={s.empty}>No logs captured for this run.</div>
  }
  return (
    <div className={s.list}>
      {logs.map((lg, i) => (
        <div key={i} className={s.entry}>
          <div className={s.stage}>{lg.stage || 'stage'}</div>

          {lg.prompt_sent ? (
            <details className={s.block}>
              <summary className={s.summary}>
                Prompt sent <span className={s.hint}>may contain paths / tokens</span>
              </summary>
              <pre className={s.pre}>{lg.prompt_sent}</pre>
            </details>
          ) : (
            <div className={s.note}>
              Prompt not captured on this path (board context is embedded in the prompt; discrete in P1).
            </div>
          )}

          {lg.stdout && lg.stdout.trim() ? (
            <details className={s.block}>
              <summary className={s.summary}>
                stdout <span className={s.hint}>PTY tail — may be truncated</span>
              </summary>
              <pre className={s.pre}>{lg.stdout}</pre>
            </details>
          ) : (
            <>
              <div className={s.stdoutLabel}>
                stdout <span className={s.hint}>PTY tail — may be truncated</span>
              </div>
              <div className={s.note}>No stdout captured for this stage.</div>
            </>
          )}
        </div>
      ))}
    </div>
  )
}
