import { useEffect, useRef, useState } from 'react'
import s from './SetupScreen.module.css'

interface Props {
  onComplete: () => void
}

export function SetupScreen({ onComplete }: Props): JSX.Element {
  const [lines, setLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  function runSetup(): void {
    setLines([])
    setError(null)
    setRetrying(false)

    const removeListener = window.pathly.setup.onProgress((msg) => {
      setLines((prev) => [...prev, msg])
      setTimeout(() => {
        if (logRef.current) {
          logRef.current.scrollTop = logRef.current.scrollHeight
        }
      }, 0)
    })

    window.pathly.setup.run().then((result) => {
      removeListener()
      if (result.ok) {
        onComplete()
      } else {
        setError(result.error ?? 'Unknown error during setup.')
      }
    })
  }

  useEffect(() => {
    runSetup()
  }, [])

  return (
    <div className={s.root}>
      <div className={s.card}>
        <div className={s.header}>
          {!error && <div className={s.spinner} />}
          <h1 className={s.heading}>Setting up Pathly</h1>
        </div>

        <div ref={logRef} className={s.log}>
          {lines.map((line, i) => (
            <div key={i} className={s.logLine}>{line}</div>
          ))}
          {lines.length === 0 && !error && (
            <div className={s.logLine}>Starting…</div>
          )}
        </div>

        {error && (
          <div className={s.errorBox}>
            <div className={s.errorText}>{error}</div>
            <button
              className={s.retryButton}
              disabled={retrying}
              onClick={() => {
                setRetrying(true)
                runSetup()
              }}
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
