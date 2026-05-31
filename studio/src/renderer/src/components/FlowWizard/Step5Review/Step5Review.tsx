import React from 'react'

interface Step5ReviewProps {
  yamlPreview: string
  storagePath: string
  onStoragePathChange: (value: string) => void
  error: string | null
  styles: Record<string, React.CSSProperties>
}

export function Step5Review({
  storagePath,
  onStoragePathChange,
  error,
  styles
}: Step5ReviewProps): JSX.Element {
  const checklist = [
    { icon: '✓', text: 'Name: the YAML updates live as you move through the wizard.' },
    { icon: '✓', text: 'Stages: the current state order is mirrored in the sidebar preview.' },
    { icon: '⚠', text: 'Agents: unassigned non-terminal states can still save, but may stall the flow.' },
    { icon: '✓', text: 'Transitions: gates, routes, and rules are already included in the generated output.' },
    { icon: '✓', text: 'Quality: optional checks stay out of the way until you expand them.' }
  ]

  return (
    <div>
      <div style={styles.stepHeader}>Review &amp; save</div>
      <div style={styles.stepSub}>Step 5 / 5 - Review the generated YAML</div>

      <div style={styles.summaryCard}>
        {checklist.map((row) => (
          <div key={row.text} style={styles.checklistRow}>
            <span style={styles.checklistIcon}>{row.icon}</span>
            <span>{row.text}</span>
          </div>
        ))}
      </div>

      <div style={styles.reviewPathBox}>
        <div style={{ color: styles.stepSub.color, fontSize: '11px', marginBottom: '6px' }}>Save to</div>
        <input
          id="storage-path"
          style={{
            ...styles.storageInput,
            marginBottom: 0,
            backgroundColor: 'transparent',
            border: 'none',
            padding: 0,
            fontSize: '12px'
          }}
          type="text"
          value={storagePath}
          onChange={(e) => onStoragePathChange(e.target.value)}
        />
      </div>

      {error && <div style={styles.error}>{error}</div>}
    </div>
  )
}
