import { useEffect, useRef, useState } from 'react'
import { Terminal, X, Moon, Sun } from 'lucide-react'
import { useStore } from '../store'
import { useTerminalStore } from '../store/terminalStore'
import { listDirs, publish, onPublishOutput } from '../services/pathlyApi'
import { IconButton } from './ui'
import styles from './TopBar.module.css'

export function TopBar(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    monitorSource,
    publishing,
    publishLog,
    theme,
    activePanel,
    setProjectPath,
    setActiveTopic,
    setPublishing,
    appendPublishLog,
    clearPublishLog,
    setTheme,
    setActivePanel,
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
        const plansBase = projectPath + '/pathly/plans'
        const [planActive, planArchived, debugTopics, exploreTopics] = await Promise.all([
          listDirs(plansBase).catch(() => [] as string[]),
          listDirs(plansBase + '/.archive').catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/debugs').catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/explorations').catch(() => [] as string[]),
        ])
        if (!cancelled) {
          const planNames = planActive.filter((e) => e !== '.archive')
          const extra = [...debugTopics, ...exploreTopics].filter((t) => !planNames.includes(t))
          setActiveTopics([...planNames, ...extra])
          setArchivedTopics(planArchived)
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

  const { toggle: toggleTerminal } = useTerminalStore()

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
            aria-label="Active topic"
            value={activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')}
            onChange={(e) => { setActiveTopic(e.target.value || null) }}
          >
            <option value="">— active topic —</option>
            {activeTopics.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select
            className={styles.topicSelectArchive}
            aria-label="Archived topic"
            value={activeTopic?.startsWith('.archive/') ? activeTopic : ''}
            onChange={(e) => { setActiveTopic(e.target.value || null) }}
          >
            <option value="">— archive —</option>
            {archivedTopics.map((t) => <option key={t} value={`.archive/${t}`}>{t}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 4, marginLeft: 12, flexShrink: 0 }}>
            <button
              className={`${styles.navBtn} ${activePanel === 'flow' ? styles.navBtnActive : ''}`}
              onClick={() => setActivePanel('flow')}
              title="Open flow canvas"
            >
              ⊞ Canvas
            </button>
            <button
              className={`${styles.navBtn} ${activePanel === 'plan' ? styles.navBtnActive : ''}`}
              onClick={() => setActivePanel('plan')}
              title="Open plan board"
            >
              ☰ Plan
            </button>
            <button
              className={`${styles.navBtn} ${activePanel === 'monitor' ? styles.navBtnActive : ''}`}
              onClick={() => setActivePanel('monitor')}
              title="Open monitor"
            >
              ⬡ Monitor
            </button>
          </div>
        </div>

        <div className={styles.right}>
          {badge}
          <IconButton
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </IconButton>
          <IconButton onClick={() => toggleTerminal()} title="Toggle terminal (Ctrl+`)">
            <Terminal size={14} />
          </IconButton>
          <button className={styles.publishBtn} onClick={() => void handlePublish()} disabled={publishing}>
            {publishing ? '…' : '↑ Publish'}
          </button>
        </div>
      </div>

      {showLog && (
        <div className={styles.logPanel}>
          <div className={styles.logHeader}>
            <span>Publish output</span>
            <IconButton onClick={() => setShowLog(false)} title="Close publish log">
              <X size={12} />
            </IconButton>
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
