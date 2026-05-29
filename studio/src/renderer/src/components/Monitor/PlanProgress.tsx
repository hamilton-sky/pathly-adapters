import { usePlanFiles } from '../../hooks/usePlanFiles'
import { useTheme } from '../../useTheme'

export function PlanProgress(): JSX.Element {
  const { planFolders } = usePlanFiles()
  const t = useTheme()

  if (planFolders.length === 0) {
    return (
      <div style={{
        padding: '8px 12px',
        fontSize: '11px',
        color: t.textMuted,
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontStyle: 'italic',
        flexShrink: 0,
        borderBottom: `1px solid ${t.bgSurface0}`,
      }}>
        No active plans
      </div>
    )
  }

  return (
    <div style={{
      maxHeight: '200px',
      overflowY: 'auto',
      flexShrink: 0,
      borderBottom: `1px solid ${t.bgSurface0}`,
    }}>
      {planFolders.map((folder) => (
        <div
          key={folder.name}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '5px 12px',
            fontSize: '12px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            color: t.textSecondary,
            borderBottom: `1px solid ${t.bgSurface0}`,
          }}
        >
          <span style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}>
            {folder.name}
          </span>
          <span style={{
            flexShrink: 0,
            marginLeft: '8px',
            fontSize: '10px',
            fontWeight: 600,
            color: folder.convDone > 0 ? t.accent : t.textMuted,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {folder.convDone}/{folder.convTotal}✓
          </span>
        </div>
      ))}
    </div>
  )
}
