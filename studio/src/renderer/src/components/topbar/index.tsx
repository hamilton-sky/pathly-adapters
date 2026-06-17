import React, { useState } from 'react'
import { Menu, Brain, Moon, Sun, Copy, Activity } from 'lucide-react'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { useTerminalStore } from '../../store/terminalStore'
import { isLightPalette } from '../../theme'
import { IconButton, Tooltip } from '../ui'
import { TopicSelector } from './TopicSelector'
import { EditorLauncher } from './EditorLauncher'
import { TerminalLauncher } from './TerminalLauncher'
import { PanelNav } from './PanelNav'
import { PublishControl } from './PublishControl'
import { PublishLog } from './PublishLog'
import { useWindowWidth } from '../sidebar/shell/useWindowWidth'
import styles from './TopBar.module.css'

const TOPBAR_COMPACT_BREAKPOINT = 1060

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

  const { chatOpen, toggleChat, cliMonitorOpen, toggleCliMonitor } = useUiStore()
  const hasRunningEngine = useTerminalStore((s) => s.tabs.some((t) => t.status === 'running'))
  const [showLog, setShowLog] = useState(false)
  const compact = useWindowWidth() < TOPBAR_COMPACT_BREAKPOINT

  const badgeLabel = monitorSource === 'sse' ? 'SSE live' : 'File watch'

  return (
    <>
      <div data-testid="topbar" className={styles.bar}>
        <IconButton
          data-testid="topbar-sidebar-toggle"
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          title={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'}
          placement="bottom"
        >
          <Menu size={15} />
        </IconButton>

        <Tooltip label="Back to projects" placement="bottom">
          <button type="button" data-testid="topbar-back-btn" className={styles.backBtn} onClick={() => setProjectPath('')}>Projects</button>
        </Tooltip>

        <div className={styles.center}>
          <TopicSelector compact={compact} />
          <EditorLauncher />
          {projectPath && !compact && (
            <IconButton
              onClick={() => void window.pathly.shell.openWindow(projectPath)}
              title="New Pathly window"
              description="Open multiple projects simultaneously in separate windows"
              placement="bottom"
            >
              <Copy size={14} />
            </IconButton>
          )}
          <PanelNav compact={compact} />
        </div>

        <div className={styles.right}>
          <div className={styles.cliMonitorWrap} data-active={hasRunningEngine || undefined}>
            <IconButton
              onClick={toggleCliMonitor}
              title="CLI Engines"
              description="Monitor and stop active CLI processes"
              placement="bottom"
            >
              <Activity size={14} />
            </IconButton>
            {hasRunningEngine && <span className={styles.cliDot} aria-hidden="true" />}
          </div>
          <IconButton
            data-testid="topbar-chat-toggle"
            data-label="Chat"
            onClick={toggleChat}
            title="HQ"
            description="Command center above your AI model orchestrators"
            placement="bottom"
          >
            <Brain size={14} style={{ color: chatOpen ? 'var(--theme-accent)' : undefined }} />
          </IconButton>
          <IconButton
            data-testid="topbar-theme-toggle"
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
