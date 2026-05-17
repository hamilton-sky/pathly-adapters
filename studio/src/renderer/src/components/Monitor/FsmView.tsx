import { useStore } from '../../store'

const DEFAULT_STATES = ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'COMMITTING', 'DONE']

export function FsmView(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)

  const states = fsmState?.flow
    ? DEFAULT_STATES
    : DEFAULT_STATES

  const activeState = fsmState?.state ?? null

  function isCompleted(stateName: string): boolean {
    if (!activeState) return false
    const activeIdx = states.indexOf(activeState)
    const thisIdx = states.indexOf(stateName)
    return thisIdx < activeIdx
  }

  function isActive(stateName: string): boolean {
    return stateName === activeState
  }

  return (
    <div style={styles.container}>
      <div style={styles.title}>FSM State</div>
      <div style={styles.track}>
        {states.map((state) => (
          <div
            key={state}
            style={{
              ...styles.stateBox,
              ...(isActive(state) ? styles.stateActive : {}),
              ...(isCompleted(state) ? styles.stateCompleted : {})
            }}
          >
            {isCompleted(state) ? `✓ ${state}` : state}
          </div>
        ))}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '16px'
  },
  title: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#6c7086',
    marginBottom: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  },
  track: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px'
  },
  stateBox: {
    padding: '6px 12px',
    borderRadius: '4px',
    border: '1px solid #313244',
    fontSize: '13px',
    color: '#6c7086',
    backgroundColor: '#11111b'
  },
  stateActive: {
    border: '2px solid #89b4fa',
    color: '#89b4fa',
    fontWeight: 600,
    backgroundColor: '#1e1e2e'
  },
  stateCompleted: {
    color: '#a6e3a1',
    borderColor: '#a6e3a1',
    backgroundColor: '#11111b'
  }
}
