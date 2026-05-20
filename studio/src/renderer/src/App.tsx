import { Component, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useStore } from './store'
import { readFile } from './services/pathlyApi'
import { HomeScreen } from './components/HomeScreen'
import { Sidebar } from './components/sidebar'
import { Editor } from './components/Editor'
import { FlowEditor } from './components/FlowEditor'
import { TopBar } from './components/TopBar'
import { Monitor } from './components/Monitor'
import { PlanBoard } from './components/PlanBoard'
import { Settings } from './components/Settings'
import { Terminal } from './components/Terminal'
import { PopoutTerminal } from './components/Terminal/PopoutTerminal'
import { SetupScreen } from './components/SetupScreen'
import { darkTheme, lightTheme } from './theme'
import appStyles from './App.module.css'

class PanelErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null }
  static getDerivedStateFromError(e: Error) { return { error: e.message } }
  render() {
    if (this.state.error) {
      return (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
          <span style={{ fontSize: '14px', color: '#f87171' }}>Panel error</span>
          <span style={{ fontSize: '12px', color: '#5a5d8a', maxWidth: '400px', textAlign: 'center' }}>{this.state.error}</span>
          <button style={{ marginTop: '8px', padding: '4px 12px', fontSize: '12px', cursor: 'pointer' }} onClick={() => this.setState({ error: null })}>Dismiss</button>
        </div>
      )
    }
    return this.props.children
  }
}

function MainPanel(): JSX.Element {
  const { activePanel, selectedItem } = useStore()
  if (activePanel === 'plan') return <PlanBoard />
  if (activePanel === 'editor' && selectedItem) return <Editor />
  if (activePanel === 'flow' && selectedItem) return <FlowEditor />
  if (activePanel === 'flow')
    return (
      <div className={appStyles.mainPanel}>
        <span className={appStyles.placeholder}>Select a flow from the sidebar</span>
      </div>
    )
  if (activePanel === 'monitor') return <Monitor />
  if (activePanel === 'settings') return <Settings />
  return (
    <div className={appStyles.mainPanel}>
      <span className={appStyles.placeholder}>Select an item from the sidebar</span>
    </div>
  )
}

export default function App(): JSX.Element | null {
  const params = new URLSearchParams(window.location.search)
  const popoutTabId = params.get('terminal')
  const popoutLabel = params.get('label') ?? 'Terminal'

  if (popoutTabId) {
    return <PopoutTerminal tabId={popoutTabId} label={popoutLabel} />
  }

  return <MainApp />
}

function MainApp(): JSX.Element | null {
  const projectPath = useStore((s) => s.projectPath)
  const theme = useStore((s) => s.theme)
  const fsmState = useStore((s) => s.fsmState)
  const setActivePanel = useStore((s) => s.setActivePanel)
  const lastUsedFlowPath = useStore((s) => s.lastUsedFlowPath)
  const setLastUsedFlowPath = useStore((s) => s.setLastUsedFlowPath)
  const setSelectedItem = useStore((s) => s.setSelectedItem)

  const [setupDone, setSetupDone] = useState<boolean | null>(null)

  useEffect(() => {
    window.pathly.setup.isNeeded().then((needed: boolean) => {
      setSetupDone(!needed)
    })
  }, [])

  useEffect(() => {
    const resolved = theme === 'dark' ? darkTheme : lightTheme
    document.documentElement.setAttribute('data-theme', theme)
    window.pathly?.window?.setTitleBarOverlay(resolved.bgMantle, resolved.textPrimary)
  }, [theme])

  // Auto-open Monitor if a flow is already running on mount (EC-2.5 handled via catch)
  useEffect(() => {
    const isRunning = fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'

    if (isRunning) {
      setActivePanel('monitor')
    }

    if (lastUsedFlowPath && !isRunning) {
      readFile(lastUsedFlowPath)
        .then(() => {
          setSelectedItem({
            name: lastUsedFlowPath.split('/').pop() ?? lastUsedFlowPath,
            path: lastUsedFlowPath,
            type: 'flow'
          })
          setActivePanel('flow')
        })
        .catch(() => {
          // File deleted — clear stored path and show empty state (EC-2.5)
          setLastUsedFlowPath(null)
        })
    }
  }, []) // run once on mount only

  if (setupDone === null) return null

  if (!setupDone) {
    return <SetupScreen onComplete={() => setSetupDone(true)} />
  }

  if (projectPath === '') {
    return (
      <>
        <HomeScreen />
        <PanelErrorBoundary><Terminal /></PanelErrorBoundary>
      </>
    )
  }

  return (
    <div className={appStyles.root}>
      <TopBar />
      <div className={appStyles.body}>
        <PanelErrorBoundary><Sidebar /></PanelErrorBoundary>
        <PanelErrorBoundary><MainPanel /></PanelErrorBoundary>
      </div>
      <PanelErrorBoundary><Terminal /></PanelErrorBoundary>
    </div>
  )
}
