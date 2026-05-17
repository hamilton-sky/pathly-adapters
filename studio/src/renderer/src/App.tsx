import { useStore } from './store'
import { HomeScreen } from './components/HomeScreen'
import { Sidebar } from './components/Sidebar'

function TopBar(): JSX.Element {
  const { setProjectPath } = useStore()
  return (
    <div style={topBarStyles.bar}>
      <button style={topBarStyles.backBtn} onClick={() => setProjectPath('')}>
        ← Projects
      </button>
      <span style={topBarStyles.title}>Pathly Studio</span>
    </div>
  )
}

function MainPanel(): JSX.Element {
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

const topBarStyles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    padding: '0 16px',
    height: '44px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
    flexShrink: 0
  },
  backBtn: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '4px 10px',
    fontSize: '13px'
  },
  title: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#cba6f7'
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
