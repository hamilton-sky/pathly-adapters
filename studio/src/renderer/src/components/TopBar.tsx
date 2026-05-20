import { useEffect, useRef, useState } from 'react'
import { Terminal, X, Moon, Sun, Menu, LayoutGrid, List, Activity } from 'lucide-react'
import { useStore } from '../store'
import { useTerminalStore } from '../store/terminalStore'
import { listDirs, publish, onPublishOutput } from '../services/pathlyApi'
import { IconButton, Tooltip } from './ui'
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
    sidebarCollapsed,
    setProjectPath,
    setActiveTopic,
    setPublishing,
    appendPublishLog,
    clearPublishLog,
    setTheme,
    setActivePanel,
    setSidebarCollapsed,
  } = useStore()

  const [activeTopics,   setActiveTopics]   = useState<string[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const removeListenerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false
    async function loadTopics(): Promise<void> {
      try {
        const plansBase = projectPath + '/pathly/plans'
        const [planActive, debugTopics, exploreTopics] = await Promise.all([
          listDirs(plansBase).catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/debugs').catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/explorations').catch(() => [] as string[]),
        ])
        if (!cancelled) {
          const planNames = planActive.filter((e) => e !== '.archive')
          const extra = [...debugTopics, ...exploreTopics].filter((t) => !planNames.includes(t))
          setActiveTopics([...planNames, ...extra])
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

  const badgeLabel = monitorSource === 'sse' ? 'SSE live' : 'File watch'
  const badge = (
    <Tooltip label={badgeLabel} placement="bottom">
      <span className={monitorSource === 'sse' ? styles.badgeLive : styles.badgeWatch}>●</span>
    </Tooltip>
  )

  return (
    <>
      <div className={styles.bar}>
        <IconButton onClick={() => setSidebarCollapsed(!sidebarCollapsed)} title={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'} placement="bottom">
          <Menu size={15} />
        </IconButton>

        <Tooltip label="Back to projects" placement="bottom">
          <button className={styles.backBtn} onClick={() => setProjectPath('')}>Projects</button>
        </Tooltip>

        <div className={styles.center}>
          <div className={styles.selectWrap}>
            <select
              className={styles.topicSelect}
              aria-label="Active topic"
              value={activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')}
              onChange={(e) => { setActiveTopic(e.target.value || null) }}
            >
              <option value="">— active topic —</option>
              {activeTopics.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 4, marginLeft: 12, flexShrink: 0 }}>
            <Tooltip label="Flow canvas" shortcut="Ctrl+1" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'flow' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('flow')}
              >
                <LayoutGrid size={13} />
                Canvas
              </button>
            </Tooltip>
            <Tooltip label="Plan board" shortcut="Ctrl+2" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'plan' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('plan')}
              >
                <List size={13} />
                Plan
              </button>
            </Tooltip>
            <Tooltip label="Live monitor" shortcut="Ctrl+3" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'monitor' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('monitor')}
              >
                <Activity size={13} />
                Monitor
              </button>
            </Tooltip>
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
          <IconButton onClick={() => toggleTerminal()} title="Toggle terminal" shortcut="Ctrl+`">
            <Terminal size={14} />
          </IconButton>
          <Tooltip label="Push hooks to server" placement="bottom">
            <button className={styles.publishBtn} onClick={() => void handlePublish()} disabled={publishing}>
              {publishing ? '…' : 'Publish'}
            </button>
          </Tooltip>
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
