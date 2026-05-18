import { useEffect, useRef, useState } from 'react'

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
    <div style={styles.root}>
      <div style={styles.card}>
        <div style={styles.header}>
          {!error && <div style={styles.spinner} />}
          <h1 style={styles.heading}>Setting up Pathly</h1>
        </div>

        <div ref={logRef} style={styles.log}>
          {lines.map((line, i) => (
            <div key={i} style={styles.logLine}>{line}</div>
          ))}
          {lines.length === 0 && !error && (
            <div style={styles.logLine}>Starting…</div>
          )}
        </div>

        {error && (
          <div style={styles.errorBox}>
            <div style={styles.errorText}>{error}</div>
            <button
              style={styles.retryButton}
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

      <style>{spinnerKeyframes}</style>
    </div>
  )
}

const spinnerKeyframes = `
@keyframes pathly-spin {
  to { transform: rotate(360deg); }
}
`

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    backgroundColor: '#1e2030',
    color: '#cdd6f4',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  },
  card: {
    width: '520px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  heading: {
    margin: 0,
    fontSize: '20px',
    fontWeight: 600,
    color: '#cdd6f4'
  },
  spinner: {
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    border: '2px solid #45475a',
    borderTopColor: '#89b4fa',
    animation: 'pathly-spin 0.8s linear infinite',
    flexShrink: 0
  },
  log: {
    backgroundColor: '#181825',
    borderRadius: '6px',
    padding: '12px',
    height: '240px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
  },
  logLine: {
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#a6adc8',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all'
  },
  errorBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    backgroundColor: '#2a1a1a',
    border: '1px solid #f38ba8',
    borderRadius: '6px',
    padding: '12px'
  },
  errorText: {
    fontSize: '13px',
    color: '#f38ba8',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all'
  },
  retryButton: {
    alignSelf: 'flex-start',
    padding: '6px 16px',
    fontSize: '13px',
    backgroundColor: '#313244',
    color: '#cdd6f4',
    border: '1px solid #45475a',
    borderRadius: '4px',
    cursor: 'pointer'
  }
}
