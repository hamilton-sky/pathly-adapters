import React from 'react'

interface Step1NameProps {
  flowName: string
  description: string
  onFlowNameChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  styles: Record<string, React.CSSProperties>
}

export function Step1Name({
  flowName,
  description,
  onFlowNameChange,
  onDescriptionChange,
  styles
}: Step1NameProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Create a new flow</div>
      <div style={styles.stepSub}>Step 1 / 8 — Name &amp; Description</div>
      <label htmlFor="flow-name" style={styles.label}>Flow name *</label>
      <input
        id="flow-name"
        style={styles.input}
        type="text"
        placeholder="my-flow"
        value={flowName}
        onChange={(e) => onFlowNameChange(e.target.value)}
      />
      <label htmlFor="flow-description" style={styles.label}>Description (optional)</label>
      <textarea
        id="flow-description"
        style={styles.textarea}
        placeholder="Describe this flow…"
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
      />
    </div>
  )
}
