import React from 'react'

interface YamlPreviewProps {
  yaml: string
  styles: Record<string, React.CSSProperties>
}

export function YamlPreview({ yaml, styles }: YamlPreviewProps): JSX.Element {
  return (
    <div style={styles.summaryCard}>
      <div style={styles.stepHeader}>Live YAML</div>
      <div style={styles.stepSub}>Updates as you edit the wizard.</div>
      <pre style={{ ...styles.preBlock, maxHeight: 'none' }}>{yaml}</pre>
    </div>
  )
}
