import { Handle, Position, type NodeProps } from 'reactflow'
import type { StateNodeData } from '../utils/flowToGraph'
import { ClaudeIcon, CodexIcon, AntigravityIcon } from '../../Terminal/BrandIcons'
import styles from './StateNode.module.css'

export type { StateNodeData }

function agentAccent(agent: string): string {
  const a = (agent ?? '').toLowerCase()
  if (a.includes('review')) return '#A78BFA'
  if (a.includes('test')) return 'var(--yellow)'
  if (a.includes('retro') || a.includes('done')) return 'var(--green)'
  return 'var(--blue)'
}

const ADAPTER_LABELS: Record<string, string> = {
  claude: 'Claude',
  codex: 'Codex',
  copilot: 'Copilot',
  antigravity: 'Antigravity',
}

function AdapterChipIcon({ adapter }: { adapter: string }): JSX.Element | null {
  if (adapter === 'claude') return <ClaudeIcon size={15} />
  if (adapter === 'codex') return <CodexIcon size={15} />
  if (adapter === 'antigravity') return <AntigravityIcon size={15} />
  return null
}

function DiamondIcon(): JSX.Element {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M12 2L22 7L12 12L2 7L12 2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

const HANDLE_STYLE: React.CSSProperties = { width: 8, height: 8, border: 'none' }

export function StateNode({ data }: NodeProps<StateNodeData>): JSX.Element {
  const hasError = data.issues?.some((i) => i.level === 'error')
  const hasWarning = data.issues && data.issues.length > 0
  const accent = agentAccent(data.agent)

  const nodeClass = [
    styles.node,
    hasError ? styles.nodeError : hasWarning ? styles.nodeWarning : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={nodeClass}
      style={{ '--node-accent': accent } as React.CSSProperties}
    >
      {/* Top handles â€” forward flow */}
      <Handle type="target" position={Position.Top} id="top-tgt"
        style={{ ...HANDLE_STYLE, background: 'var(--blue)', left: '50%' }} />
      <Handle type="source" position={Position.Top} id="top-src"
        style={{ ...HANDLE_STYLE, background: 'var(--blue)', left: '35%' }} />

      {/* Bottom handles â€” main forward flow */}
      <Handle type="source" position={Position.Bottom} id="bot-src"
        style={{ ...HANDLE_STYLE, background: 'var(--blue)', left: '50%' }} />
      <Handle type="target" position={Position.Bottom} id="bot-tgt"
        style={{ ...HANDLE_STYLE, background: 'var(--blue)', left: '35%' }} />

      {/* Left handles â€” backward loop */}
      <Handle type="target" position={Position.Left} id="left-tgt"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '35%' }} />
      <Handle type="source" position={Position.Left} id="left-src"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '65%' }} />

      {/* Right handles â€” backward loop */}
      <Handle type="target" position={Position.Right} id="right-tgt"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '35%' }} />
      <Handle type="source" position={Position.Right} id="right-src"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '65%' }} />

      {data.isStart && (
        <div className={styles.startBadge} title="Start state">â–¶</div>
      )}

      {hasWarning && (
        <div
          className={`${styles.validBadge}${hasError ? ` ${styles.validBadgeError}` : ''}`}
          title={data.issues?.map((i) => i.message).join('\n')}
          aria-label={`${data.issues?.length} validation issue(s)`}
        >
          !
        </div>
      )}

      <div className={styles.header}>
        <span className={styles.pip} aria-hidden="true" />
        <span className={styles.name}>{data.state}</span>
        {data.agent && <span className={styles.agentLabel}>{data.agent}</span>}
      </div>

      {(data.adapter || data.skill) && (
        <div className={styles.chips}>
          {data.adapter && (
            <span className={styles.chip}>
              <AdapterChipIcon adapter={data.adapter} />
              {ADAPTER_LABELS[data.adapter] ?? data.adapter}
            </span>
          )}
          {data.skill && (
            <span className={styles.chip}>
              <DiamondIcon />
              {data.skill}
            </span>
          )}
        </div>
      )}

      {data.feedbackArrivals && data.feedbackArrivals.length > 0 && (
        <div
          className={styles.feedbackArrivals}
          title={`feedback_routing: ${data.feedbackArrivals.join(', ')}`}
        >
          â†© {data.feedbackArrivals.join(', ')}
        </div>
      )}
    </div>
  )
}
