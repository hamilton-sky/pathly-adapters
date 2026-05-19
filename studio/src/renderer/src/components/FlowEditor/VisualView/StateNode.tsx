import { Handle, Position, type NodeProps } from 'reactflow'
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
        padding: '6px 8px',
        position: 'relative'
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: t.blue, width: 8, height: 8, border: 'none' }}
      />
      <div style={{ fontWeight: 600, fontSize: '13px' }}>{data.state}</div>
      {data.agent && (
        <div style={{ fontSize: '11px', color: t.textSecondary, marginTop: '2px' }}>{data.agent}</div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: t.blue, width: 8, height: 8, border: 'none' }}
      />
    </div>
  )
}
