import { Handle, Position, type NodeProps } from 'reactflow'
import { useTheme } from '../../../useTheme'
import type { StateNodeData } from '../utils/flowToGraph'

export type { StateNodeData }

export function StateNode({ data }: NodeProps<StateNodeData>): JSX.Element {
  const t = useTheme()
  const hasError = data.issues?.some((i) => i.severity === 'error')
  const hasWarning = data.issues && data.issues.length > 0

  const borderColor = hasError ? t.red : hasWarning ? t.yellow : t.bgSurface1

  return (
    <div
      style={{
        backgroundColor: t.bgSurface0,
        border: `1px solid ${borderColor}`,
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
      {hasWarning && (
        <div
          title={data.issues?.map((i) => i.message).join('\n')}
          style={{
            position: 'absolute',
            top: -6,
            right: -6,
            width: 16,
            height: 16,
            borderRadius: '50%',
            backgroundColor: hasError ? t.red : t.yellow,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            color: t.bgBase,
            fontWeight: 700,
            cursor: 'default'
          }}
          aria-label={`${data.issues?.length} validation issue(s)`}
        >
          !
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: t.blue, width: 8, height: 8, border: 'none' }}
      />
    </div>
  )
}
