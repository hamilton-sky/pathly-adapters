import styles from './Step5Review.module.css'

interface Step5ReviewProps {
  yamlPreview: string
  storagePath: string
  onStoragePathChange: (value: string) => void
  error: string | null
}

export function Step5Review({
  storagePath,
  onStoragePathChange,
  error,
}: Step5ReviewProps): JSX.Element {
  const checklist = [
    { icon: '✓', text: 'Name: the YAML updates live as you move through the wizard.' },
    { icon: '✓', text: 'Stages: the current state order is mirrored in the sidebar preview.' },
    { icon: '⚠', text: 'Agents: unassigned non-terminal states can still save, but may stall the flow.' },
    { icon: '✓', text: 'Transitions: gates, routes, and rules are already included in the generated output.' },
    { icon: '✓', text: 'Quality: optional checks stay out of the way until you expand them.' }
  ]

  return (
    <div className={styles.root}>
      <div className={styles.title}>Review &amp; save</div>
      <div className={styles.sub}>Step 5 / 5 - Review the generated YAML</div>

      <div className={styles.summaryCard}>
        {checklist.map((row) => (
          <div key={row.text} className={styles.checklistRow}>
            <span className={styles.checklistIcon}>{row.icon}</span>
            <span>{row.text}</span>
          </div>
        ))}
      </div>

      <div className={styles.reviewPathBox}>
        <div className={styles.reviewPathLabel}>Save to</div>
        <input
          id="storage-path"
          className={styles.reviewPathInput}
          type="text"
          aria-label="Storage path"
          value={storagePath}
          onChange={(e) => onStoragePathChange(e.target.value)}
        />
      </div>

      {error && <div className={styles.error}>{error}</div>}
    </div>
  )
}
