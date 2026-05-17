import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    bar: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '0 16px',
      height: '44px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    backBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textPrimary,
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
      background: t.bgBase,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textPrimary,
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
      color: t.green,
      whiteSpace: 'nowrap' as const
    },
    badgeWatch: {
      fontSize: '12px',
      color: t.textMuted,
      whiteSpace: 'nowrap' as const
    },
    publishBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '4px 12px',
      fontSize: '13px',
      fontWeight: 600
    },
    logPanel: {
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0,
      maxHeight: '200px',
      display: 'flex',
      flexDirection: 'column' as const
    },
    logHeader: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '4px 12px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      fontSize: '12px',
      color: t.textMuted
    },
    logClose: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '0 4px'
    },
    logBody: {
      overflowY: 'auto' as const,
      flex: 1,
      padding: '4px 12px',
      fontFamily: 'monospace',
      fontSize: '12px',
      color: t.green
    },
    logLine: {
      whiteSpace: 'pre-wrap' as const,
      wordBreak: 'break-all' as const
    }
  }
}

export function TopBar(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    monitorSource,
    publishing,
    publishLog,
    setProjectPath,
    setActiveTopic,
    setActivePanel,
    setPublishing,
    appendPublishLog,
    clearPublishLog
  } = useStore()

  const t = useTheme()
  const styles = makeStyles(t)

  const [topics, setTopics] = useState<string[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const removeOutputListenerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false

    async function loadTopics(): Promise<void> {
      try {
        const entries = await window.pathly.fs.listDirs(projectPath + '/pathly/plans')
        if (!cancelled) {
          setTopics(entries.filter((e) => e !== '.archive'))
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
            onChange={(e) => {
              setActiveTopic(e.target.value || null)
              setActivePanel('plan')
            }}
          >
            <option value="">— select topic —</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>
                {topic}
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
