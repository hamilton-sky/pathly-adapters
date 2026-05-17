import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'

export function TopBar(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    monitorSource,
    publishing,
    publishLog,
    setProjectPath,
    setActiveTopic,
    setPublishing,
    appendPublishLog,
    clearPublishLog
  } = useStore()

  const [topics, setTopics] = useState<string[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const removeOutputListenerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false

    async function loadTopics(): Promise<void> {
      try {
        const entries = await window.pathly.fs.list(projectPath + '/pathly/plans/')
        if (!cancelled) {
          setTopics(entries.filter((e) => !e.includes('.archive')))
        }
      } catch {
        // directory may not exist yet
      }
    }

    loadTopics()
    const interval = setInterval(loadTopics, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [projectPath])

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [publishLog])

  async function handlePublish(): Promise<void> {
    clearPublishLog()
    setShowLog(true)
    setPublishing(true)
    // Register listener once, storing the cleanup so it can be removed after publish
    if (removeOutputListenerRef.current) removeOutputListenerRef.current()
    removeOutputListenerRef.current = window.pathly.shell.onOutput((line) => {
      appendPublishLog(line)
    })
    try {
      await window.pathly.shell.publish(projectPath)
    } finally {
      setPublishing(false)
      if (removeOutputListenerRef.current) {
        removeOutputListenerRef.current()
        removeOutputListenerRef.current = null
      }
    }
  }

  const connectionBadge =
    monitorSource === 'mcp' ? (
      <span style={styles.badgeLive}>● MCP live</span>
    ) : (
      <span style={styles.badgeWatch}>○ File watch</span>
    )

  return (
    <>
      <div style={styles.bar}>
        <button style={styles.backBtn} onClick={() => setProjectPath('')}>
          ← Projects
        </button>

        <div style={styles.center}>
          <select
            style={styles.topicSelect}
            value={activeTopic ?? ''}
            onChange={(e) => setActiveTopic(e.target.value || null)}
          >
            <option value="">— select topic —</option>
            {topics.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div style={styles.right}>
          {connectionBadge}
          <button
            style={styles.publishBtn}
            onClick={handlePublish}
            disabled={publishing}
          >
            {publishing ? '…' : '↑ Publish'}
          </button>
        </div>
      </div>

      {showLog && (
        <div style={styles.logPanel}>
          <div style={styles.logHeader}>
            <span>Publish output</span>
            <button style={styles.logClose} onClick={() => setShowLog(false)}>
              ✕
            </button>
          </div>
          <div style={styles.logBody}>
            {publishLog.map((line, i) => (
              <div key={i} style={styles.logLine}>
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </>
  )
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '0 16px',
    height: '44px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
    flexShrink: 0
  },
  backBtn: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '4px 10px',
    fontSize: '13px'
  },
  center: {
    flex: 1,
    display: 'flex',
    justifyContent: 'center'
  },
  topicSelect: {
    background: '#1e1e2e',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    fontSize: '13px',
    padding: '4px 8px',
    cursor: 'pointer'
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  badgeLive: {
    fontSize: '12px',
    color: '#a6e3a1',
    whiteSpace: 'nowrap'
  },
  badgeWatch: {
    fontSize: '12px',
    color: '#6c7086',
    whiteSpace: 'nowrap'
  },
  publishBtn: {
    background: '#cba6f7',
    border: 'none',
    borderRadius: '4px',
    color: '#1e1e2e',
    cursor: 'pointer',
    padding: '4px 12px',
    fontSize: '13px',
    fontWeight: 600
  },
  logPanel: {
    backgroundColor: '#11111b',
    borderBottom: '1px solid #313244',
    flexShrink: 0,
    maxHeight: '200px',
    display: 'flex',
    flexDirection: 'column'
  },
  logHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 12px',
    borderBottom: '1px solid #313244',
    fontSize: '12px',
    color: '#6c7086'
  },
  logClose: {
    background: 'none',
    border: 'none',
    color: '#6c7086',
    cursor: 'pointer',
    fontSize: '12px',
    padding: '0 4px'
  },
  logBody: {
    overflowY: 'auto',
    flex: 1,
    padding: '4px 12px',
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#a6e3a1'
  },
  logLine: {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all'
  }
}
