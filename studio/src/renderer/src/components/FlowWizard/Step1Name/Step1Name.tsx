import styles from './Step1Name.module.css'

interface Step1NameProps {
  flowName: string
  description: string
  onFlowNameChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

export function Step1Name({
  flowName,
  description,
  onFlowNameChange,
  onDescriptionChange,
}: Step1NameProps): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.title}>Create a new flow</div>
      <div className={styles.sub}>Step 1 / 8 — Name &amp; Description</div>
      <label htmlFor="flow-name" className={styles.label}>Flow name *</label>
      <input
        id="flow-name"
        className={styles.input}
        type="text"
        placeholder="my-flow"
        value={flowName}
        onChange={(e) => onFlowNameChange(e.target.value)}
      />
      <label htmlFor="flow-description" className={styles.label}>Description (optional)</label>
      <textarea
        id="flow-description"
        className={styles.textarea}
        placeholder="Describe this flow…"
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
      />
    </div>
  )
}
