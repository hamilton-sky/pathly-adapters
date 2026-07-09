import React, { useState } from 'react'
import { Brain, Moon, Sun, Cpu } from 'lucide-react'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import { useTerminalStore } from '../../store/terminalStore'
import { isLightPalette } from '../../theme'
import { IconButton } from '../ui'
import { PathlyLogo } from './PathlyLogo'
import { ProjectSelector } from './ProjectSelector'
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
    monitorSource,
    theme,
    preferredDark,
    preferredLight,
    setProjectPath,
    setTheme,
  } = useStore()

  const { chatOpen, toggleChat, cliMonitorOpen, toggleCliMonitor } = useUiStore()
  // Read the authoritative spawn-gate state (same source as the CLI monitor's ACTIVE list), NOT
  // per-tab status — so the dot lights for EVERY engine (board/runner, editor, manual) and any
  // queued run, instead of missing backend spawns whose tab never reaches status:'running'.
  const hasRunningEngine = useTerminalStore((s) => s.spawnQueue.total > 0 || s.spawnQueue.queued.length > 0)
  const [showLog, setShowLog] = useState(false)
  const compact = useWindowWidth() < TOPBAR_COMPACT_BREAKPOINT

  const badgeLabel = monitorSource === 'sse' ? 'SSE live' : 'File watch'

  return (
    <>
      <div data-testid="topbar" className={styles.bar}>
        <PathlyLogo onHome={() => setProjectPath('')} />

        <div className={styles.center}>
          <ProjectSelector compact={compact} />
          <EditorLauncher />
          <PanelNav compact={compact} />
        </div>

        <div className={styles.right}>
          <div className={styles.cliMonitorWrap} data-active={hasRunningEngine || undefined}>
            <IconButton
              size="md"
              onClick={toggleCliMonitor}
              title="CLI Engines"
              description="Monitor and stop active CLI processes"
              placement="bottom"
            >
              <Cpu size={14} />
            </IconButton>
            {hasRunningEngine && <span className={styles.cliDot} aria-hidden="true" />}
          </div>
          <IconButton
            data-testid="topbar-chat-toggle"
            data-label="Chat"
            size="md"
            onClick={toggleChat}
            title="HQ"
            description="Command center above your AI model orchestrators"
            placement="bottom"
          >
            <Brain size={14} style={{ color: chatOpen ? 'var(--theme-accent)' : undefined }} />
          </IconButton>
          <IconButton
            data-testid="topbar-theme-toggle"
            size="md"
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
