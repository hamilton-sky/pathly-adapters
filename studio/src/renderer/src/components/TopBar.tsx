import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { listDirs, publish, onPublishOutput } from '../services/pathlyApi'
import styles from './TopBar.module.css'

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
    clearPublishLog,
  } = useStore()

  const [activeTopics,   setActiveTopics]   = useState<string[]>([])
  const [archivedTopics, setArchivedTopics] = useState<string[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const removeListenerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false
    async function loadTopics(): Promise<void> {
      try {
        const base = projectPath + '/pathly/plans'
        const [active, archived] = await Promise.all([
          listDirs(base).catch(() => [] as string[]),
          listDirs(base + '/.archive').catch(() => [] as string[]),
        ])
        if (!cancelled) {
          setActiveTopics(active.filter((e) => e !== '.archive'))
          setArchivedTopics(archived)
        }
      } catch { /* directory may not exist yet */ }
    }
    loadTopics()
    const interval = setInterval(loadTopics, 5000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [projectPath])

  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [publishLog])

  async function handlePublish(): Promise<void> {
    clearPublishLog()
    setShowLog(true)
    setPublishing(true)
    if (removeListenerRef.current) removeListenerRef.current()
    removeListenerRef.current = onPublishOutput((line) => appendPublishLog(line))
    try {
      await publish(projectPath)
    } finally {
      setPublishing(false)
      removeListenerRef.current?.()
      removeListenerRef.current = null
    }
  }

  const badge = monitorSource === 'sse'
    ? <span className={styles.badgeLive}>● SSE live</span>
    : <span className={styles.badgeWatch}>○ File watch</span>

  return (
    <>
      <div className={styles.bar}>
        <button className={styles.backBtn} onClick={() => setProjectPath('')}>← Projects</button>

        <span className={styles.brand}>Pathly Studio</span>

        <div className={styles.center}>
          <select
            className={styles.topicSelect}
            value={activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')}
            onChange={(e) => { setActiveTopic(e.target.value || null); setActivePanel('monitor') }}
          >
            <option value="">— active topic —</option>
            {activeTopics.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select
            className={styles.topicSelectArchive}
            value={activeTopic?.startsWith('.archive/') ? activeTopic : ''}
            onChange={(e) => { setActiveTopic(e.target.value || null); setActivePanel('monitor') }}
          >
            <option value="">— archive —</option>
            {archivedTopics.map((t) => <option key={t} value={`.archive/${t}`}>{t}</option>)}
          </select>
        </div>

        <div className={styles.right}>
          {badge}
          <button className={styles.publishBtn} onClick={() => void handlePublish()} disabled={publishing}>
            {publishing ? '…' : '↑ Publish'}
          </button>
        </div>
      </div>

      {showLog && (
        <div className={styles.logPanel}>
          <div className={styles.logHeader}>
            <span>Publish output</span>
            <button className={styles.logClose} onClick={() => setShowLog(false)}>✕</button>
          </div>
          <div className={styles.logBody}>
            {publishLog.map((line, i) => <div key={i} className={styles.logLine}>{line}</div>)}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </>
  )
}
