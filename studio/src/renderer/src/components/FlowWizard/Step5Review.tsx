import React from 'react'

interface Step5ReviewProps {
  yamlPreview: string
  storagePath: string
  onStoragePathChange: (value: string) => void
  error: string | null
  styles: Record<string, React.CSSProperties>
}

export function Step5Review({
  yamlPreview,
  storagePath,
  onStoragePathChange,
  error,
  styles
}: Step5ReviewProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Review &amp; Save</div>
      <div style={styles.stepSub}>Step 5 / 5 — Review the generated YAML</div>
      <pre style={styles.preBlock}>{yamlPreview}</pre>
      <div style={styles.storageRow}>
        <label htmlFor="storage-path" style={styles.storageLabel}>Storage path:</label>
        <input
          id="storage-path"
          style={styles.storageInput}
          type="text"
          value={storagePath}
          onChange={(e) => onStoragePathChange(e.target.value)}
        />
      </div>
      {error && <div style={styles.error}>{error}</div>}
    </div>
  )
}
