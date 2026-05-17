import { useStore } from './store'
import { HomeScreen } from './components/HomeScreen'
import { Sidebar } from './components/Sidebar'
import { Editor } from './components/Editor'
import { FlowEditor } from './components/FlowEditor'
import { TopBar } from './components/TopBar'
import { Monitor } from './components/Monitor'

function MainPanel(): JSX.Element {
  const { activePanel, selectedItem } = useStore()
  if (activePanel === 'editor' && selectedItem) return <Editor />
  if (activePanel === 'flow' && selectedItem) return <FlowEditor />
  if (activePanel === 'flow')
    return (
      <div style={mainPanelStyles.panel}>
        <span style={mainPanelStyles.placeholder}>Select a flow from the sidebar</span>
      </div>
    )
  if (activePanel === 'monitor') return <Monitor />
  return (
    <div style={mainPanelStyles.panel}>
      <span style={mainPanelStyles.placeholder}>Select an item from the sidebar</span>
    </div>
  )
}

export default function App(): JSX.Element {
  const projectPath = useStore((s) => s.projectPath)

  if (projectPath === '') {
    return <HomeScreen />
  }

  return (
    <div style={appStyles.root}>
      <TopBar />
      <div style={appStyles.body}>
        <Sidebar />
        <MainPanel />
      </div>
    </div>
  )
}

const appStyles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#1e1e2e',
    color: '#cdd6f4',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    overflow: 'hidden'
  },
  body: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden'
  }
}


const mainPanelStyles: Record<string, React.CSSProperties> = {
  panel: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1e1e2e',
    overflow: 'auto'
  },
  placeholder: {
    color: '#6c7086',
    fontSize: '15px'
  }
}
