import { Handle, Position, type NodeProps } from 'reactflow'
import { useTheme } from '../../../useTheme'
import type { StateNodeData } from '../utils/flowToGraph'

export type { StateNodeData }

// Left accent bar color by agent type keyword
function accentColor(agent: string, blue: string, purple: string, green: string, amber: string, muted: string): string {
  if (!agent) return muted
  const a = agent.toLowerCase()
  if (a.includes('review') || a.includes('reviewer')) return purple
  if (a.includes('test') || a.includes('tester')) return amber
  if (a.includes('retro') || a.includes('done')) return green
  return blue
}

const HANDLE_STYLE = { width: 8, height: 8, border: 'none' }

export function StateNode({ data }: NodeProps<StateNodeData>): JSX.Element {
  const t = useTheme()
  const hasError = data.issues?.some((i) => i.level === 'error')
  const hasWarning = data.issues && data.issues.length > 0

  const borderColor = hasError ? t.red : hasWarning ? t.yellow : t.bgSurface1
  const accent = accentColor(data.agent, t.blue, t.purple ?? '#A78BFA', t.green, t.yellow, t.bgSurface1)

  return (
    <div
      style={{
        backgroundColor: t.bgSurface0,
        border: `1px solid ${borderColor}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: '6px',
        color: t.textPrimary,
        width: 160,
        padding: '8px 10px 8px 10px',
        position: 'relative',
        boxSizing: 'border-box',
      }}
    >
      {/* Top handles — forward in/out for TB layout */}
      <Handle type="target" position={Position.Top} id="top-tgt"
        style={{ ...HANDLE_STYLE, background: t.blue, left: '50%' }} />
      <Handle type="source" position={Position.Top} id="top-src"
        style={{ ...HANDLE_STYLE, background: t.blue, left: '35%' }} />

      {/* Bottom handles — main forward flow */}
      <Handle type="source" position={Position.Bottom} id="bot-src"
        style={{ ...HANDLE_STYLE, background: t.blue, left: '50%' }} />
      <Handle type="target" position={Position.Bottom} id="bot-tgt"
        style={{ ...HANDLE_STYLE, background: t.blue, left: '35%' }} />

      {/* Left handles — backward loop entry/exit (left side) */}
      <Handle type="target" position={Position.Left} id="left-tgt"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '35%' }} />
      <Handle type="source" position={Position.Left} id="left-src"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '65%' }} />

      {/* Right handles — backward loop entry/exit (right side) */}
      <Handle type="target" position={Position.Right} id="right-tgt"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '35%' }} />
      <Handle type="source" position={Position.Right} id="right-src"
        style={{ ...HANDLE_STYLE, background: '#F59E0B', top: '65%' }} />

      {/* Start indicator */}
      {data.isStart && (
        <div
          title="Start state"
          style={{
            position: 'absolute',
            top: -8, left: -8,
            width: 16, height: 16,
            borderRadius: '50%',
            backgroundColor: t.accent,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '9px', color: '#fff', fontWeight: 700,
          }}
        >
          ▶
        </div>
      )}

      {/* Validation badge */}
      {hasWarning && (
        <div
          title={data.issues?.map((i) => i.message).join('\n')}
          aria-label={`${data.issues?.length} validation issue(s)`}
          style={{
            position: 'absolute',
            top: -6, right: -6,
            width: 16, height: 16,
            borderRadius: '50%',
            backgroundColor: hasError ? t.red : t.yellow,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '10px', color: t.bgBase, fontWeight: 700, cursor: 'default',
          }}
        >
          !
        </div>
      )}

      {/* State name */}
      <div style={{ fontWeight: 700, fontSize: '12px', letterSpacing: '0.03em', fontFamily: 'monospace' }}>
        {data.state}
      </div>

      {/* Agent name */}
      {data.agent && (
        <div style={{ fontSize: '11px', color: t.textSecondary, marginTop: '3px', fontFamily: 'inherit' }}>
          {data.agent}
        </div>
      )}

      {/* Feedback routing arrivals — artifacts that escalate back to this state */}
      {data.feedbackArrivals && data.feedbackArrivals.length > 0 && (
        <div
          title={`feedback_routing: ${data.feedbackArrivals.join(', ')}`}
          style={{
            marginTop: '5px',
            paddingTop: '4px',
            borderTop: '1px solid #8B5CF622',
            fontSize: '9px',
            color: '#8B5CF6',
            fontFamily: 'monospace',
            lineHeight: 1.4,
          }}
        >
          ↩ {data.feedbackArrivals.join(', ')}
        </div>
      )}
    </div>
  )
}
