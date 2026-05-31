import React, { useState } from 'react'
import { Menu, Brain, Moon, Sun, Copy } from 'lucide-react'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { isLightPalette } from '../../theme'
import { IconButton, Tooltip } from '../ui'
import { TopicSelector } from './TopicSelector'
import { EditorLauncher } from './EditorLauncher'
import { TerminalLauncher } from './TerminalLauncher'
import { PanelNav } from './PanelNav'
import { PublishControl } from './PublishControl'
import { PublishLog } from './PublishLog'
import styles from './TopBar.module.css'

export function TopBar(): JSX.Element {
  const {
    projectPath,
    monitorSource,
    theme,
    preferredDark,
    preferredLight,
    sidebarCollapsed,
    setProjectPath,
    setTheme,
    setSidebarCollapsed,
  } = useStore()

  const { chatOpen, toggleChat } = useUiStore()
  const [showLog, setShowLog] = useState(false)

  const badgeLabel = monitorSource === 'sse' ? 'SSE live' : 'File watch'

  return (
    <>
      <div className={styles.bar}>
        <IconButton
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          title={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'}
          placement="bottom"
        >
          <Menu size={15} />
        </IconButton>

        <Tooltip label="Back to projects" placement="bottom">
          <button className={styles.backBtn} onClick={() => setProjectPath('')}>Projects</button>
        </Tooltip>

        <div className={styles.center}>
          <TopicSelector />
          <EditorLauncher />
          {projectPath && (
            <IconButton
              onClick={() => void window.pathly.shell.openWindow(projectPath)}
              title="New Pathly window"
              description="Open multiple projects simultaneously in separate windows"
              placement="bottom"
            >
              <Copy size={14} />
            </IconButton>
          )}
          <PanelNav />
        </div>

        <div className={styles.right}>
          <Tooltip label={badgeLabel} placement="bottom">
            <span className={monitorSource === 'sse' ? styles.badgeLive : styles.badgeWatch}>●</span>
          </Tooltip>
          <IconButton
            onClick={toggleChat}
            title="HQ"
            description="Command center above your AI model orchestrators"
            placement="bottom"
          >
            <Brain size={14} style={{ color: chatOpen ? 'var(--theme-accent)' : undefined }} />
          </IconButton>
          <IconButton
            onClick={() => setTheme(isLightPalette(theme) ? preferredDark : preferredLight)}
            title={isLightPalette(theme) ? `Switch to dark (${preferredDark})` : `Switch to light (${preferredLight})`}
          >
            {isLightPalette(theme) ? <Moon size={14} /> : <Sun size={14} />}
          </IconButton>
          <TerminalLauncher />
          <PublishControl onShowLog={() => setShowLog(true)} />
        </div>
      </div>

      {showLog && <PublishLog onClose={() => setShowLog(false)} />}
    </>
  )
}
