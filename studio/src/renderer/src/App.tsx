import { Component, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useStore } from './store'
import { useUiStore } from './store/uiStore'
import { useBrightskyStore } from './store/brightskyStore'
import { brightskyClient } from './lib/brightskyClient'
import { readFile } from './services/pathlyApi'
import { HomeScreen } from './components/HomeScreen'
import { Sidebar } from './components/sidebar'
import { Editor } from './components/Editor'
import { FlowEditor } from './components/FlowEditor'
import { TopBar } from './components/topbar'
import { Monitor } from './components/Monitor'
import { PlanBoard } from './components/PlanBoard'
import { Settings } from './components/Settings'
import { Terminal } from './components/Terminal'
import { PopoutTerminal } from './components/Terminal/PopoutTerminal'
import { SetupScreen } from './components/SetupScreen'
import { ChatPanel } from './components/ChatPanel'
import { Toaster } from './components/Toaster'
import { themes } from './theme'
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

  return (
    <>
      <MainApp />
      <Toaster />
    </>
  )
}

function isBrightskyAuthError(p: unknown): p is BrightskyAuthError {
  return typeof p === 'object' && p !== null && 'error' in p
}

function MainApp(): JSX.Element | null {
  const projectPath = useStore((s) => s.projectPath)
  const setProjectPath = useStore((s) => s.setProjectPath)
  const theme = useStore((s) => s.theme)
  const fsmState = useStore((s) => s.fsmState)

  // Seed projectPath from the Electron-injected PROJECT_PATH query param on
  // first mount. Electron passes it via loadFile({ query: { PROJECT_PATH } })
  // but the renderer never reads it — without this the FSM /status call has
  // no project_root and always returns "unknown" (no menu card).
  useEffect(() => {
    if (projectPath) return  // already set (user navigated to a project)
    const qp = new URLSearchParams(window.location.search).get('PROJECT_PATH')
    if (qp) setProjectPath(decodeURIComponent(qp))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const setActivePanel = useStore((s) => s.setActivePanel)
  const lastUsedFlowPath = useStore((s) => s.lastUsedFlowPath)
  const setLastUsedFlowPath = useStore((s) => s.setLastUsedFlowPath)
  const setSelectedItem = useStore((s) => s.setSelectedItem)
  const chatOpen = useUiStore((s) => s.chatOpen)

  const [setupDone, setSetupDone] = useState<boolean | null>(null)

  useEffect(() => {
    window.pathly.setup.isNeeded().then((needed: boolean) => {
      setSetupDone(!needed)
    })
  }, [])

  useEffect(() => {
    const resolved = themes[theme] ?? themes.dark
    document.documentElement.setAttribute('data-theme', theme)
    window.pathly?.window?.setTitleBarOverlay(resolved.bgMantle, resolved.textPrimary)
    const root = document.documentElement
    root.style.setProperty('--theme-bg-base', resolved.bgBase)
    root.style.setProperty('--theme-bg-mantle', resolved.bgMantle)
    root.style.setProperty('--theme-bg-surface0', resolved.bgSurface0)
    root.style.setProperty('--theme-text-primary', resolved.textPrimary)
    root.style.setProperty('--theme-text-secondary', resolved.textSecondary)
    root.style.setProperty('--theme-text-muted', resolved.textMuted)
    root.style.setProperty('--theme-accent', resolved.accent)
    root.style.setProperty('--theme-accent-a11', `${resolved.accent}11`)
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

  // Auto-connect WebSocket on mount if a token is already persisted (returning user)
  useEffect(() => {
    const { authenticated, accessToken, wsUrl } = useBrightskyStore.getState()
    if (authenticated && accessToken) {
      brightskyClient.connect(wsUrl, accessToken)
    }
  }, [])

  useEffect(() => {
    if (!window.pathly?.brightsky) return
    const cleanup = window.pathly.brightsky.onToken((payload) => {
      if (isBrightskyAuthError(payload)) {
        useBrightskyStore.getState().setAuthError(payload.error)
      } else {
        useBrightskyStore.getState().setTokens(payload.access_token, payload.refresh_token, payload.user)
        // Auto-connect WebSocket immediately after fresh auth
        const { wsUrl } = useBrightskyStore.getState()
        brightskyClient.connect(wsUrl, payload.access_token)
      }
    })
    return cleanup
  }, [])

  useEffect(() => {
    let prevUserId = useBrightskyStore.getState().userId
    const unsub = useBrightskyStore.subscribe((state) => {
      const newId = state.userId
      if (prevUserId !== null && newId !== null && newId !== prevUserId) {
        useBrightskyStore.getState().setSessionId(null)
      }
      prevUserId = newId
    })
    return unsub
  }, [])

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
        {chatOpen && (
          <PanelErrorBoundary><ChatPanel /></PanelErrorBoundary>
        )}
      </div>
      <PanelErrorBoundary><Terminal /></PanelErrorBoundary>
    </div>
  )
}
