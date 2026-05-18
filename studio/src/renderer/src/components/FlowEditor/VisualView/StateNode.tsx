import type { NodeProps } from 'reactflow'
import { useTheme } from '../../../useTheme'

interface StateNodeData {
  state: string
  agent: string
}

export function StateNode({ data }: NodeProps<StateNodeData>): JSX.Element {
  const t = useTheme()
  return (
    <div
      style={{
        backgroundColor: t.bgSurface0,
        border: `1px solid ${t.bgSurface1}`,
        borderRadius: '6px',
        color: t.textPrimary,
        width: 160,
        textAlign: 'center',
        padding: '6px 8px'
      }}
    >
      <div style={{ fontWeight: 600, fontSize: '13px' }}>{data.state}</div>
      {data.agent && (
        <div style={{ fontSize: '11px', color: t.textSecondary, marginTop: '2px' }}>{data.agent}</div>
      )}
    </div>
  )
}
