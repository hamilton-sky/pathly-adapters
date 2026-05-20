import type { Theme } from '../../../../theme'
import { makePanelStyles } from '../../shared/panelStyles'
import type { AddConditionState, ConditionType } from '../hooks/useTransitionConditions'

const CONDITION_LABELS: Record<string, { label: string }> = {
  default:     { label: 'Always continues to →' },
  on_artifact: { label: 'When artifact arrives:' },
  on_content:  { label: 'When file contains:' },
  decide:      { label: 'Human decision required:' },
}

interface AddConditionFormProps {
  addCond: AddConditionState
  setAddCond: React.Dispatch<React.SetStateAction<AddConditionState>>
  onSubmit: () => void
  onCancel: () => void
  t: Theme
}

export function AddConditionForm({ addCond, setAddCond, onSubmit, onCancel, t }: AddConditionFormProps): JSX.Element {
  const ps = makePanelStyles(t)

  return (
    <div style={ps.conditionBox}>
      <div style={ps.condFormRow}>
        <select
          aria-label="Condition type"
          title="Condition type"
          value={addCond.type}
          onChange={(e) => setAddCond((s) => ({ ...s, type: e.target.value as ConditionType }))}
          style={ps.condSelectStyle}
        >
          <option value="default">{CONDITION_LABELS.default.label}</option>
          <option value="on_artifact">{CONDITION_LABELS.on_artifact.label}</option>
          <option value="on_content">{CONDITION_LABELS.on_content.label}</option>
          <option value="decide">{CONDITION_LABELS.decide.label}</option>
        </select>
      </div>

      {addCond.type === 'on_artifact' && (
        <input
          value={addCond.artifact}
          onChange={(e) => setAddCond((s) => ({ ...s, artifact: e.target.value }))}
          placeholder="artifact.md"
          style={{ ...ps.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
        />
      )}

      {addCond.type === 'on_content' && (
        <>
          <input
            value={addCond.file}
            onChange={(e) => setAddCond((s) => ({ ...s, file: e.target.value }))}
            placeholder="file.md"
            style={{ ...ps.input, width: '100%', marginBottom: '4px', boxSizing: 'border-box' }}
          />
          <input
            value={addCond.contains}
            onChange={(e) => setAddCond((s) => ({ ...s, contains: e.target.value }))}
            placeholder="contains text…"
            style={{ ...ps.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
          />
        </>
      )}

      {addCond.type === 'decide' && (
        <>
          <input
            value={addCond.question}
            onChange={(e) => setAddCond((s) => ({ ...s, question: e.target.value }))}
            placeholder="Question for human?"
            style={{ ...ps.input, width: '100%', marginBottom: '4px', boxSizing: 'border-box' }}
          />
          <input
            value={addCond.optionLabel}
            onChange={(e) => setAddCond((s) => ({ ...s, optionLabel: e.target.value }))}
            placeholder="Option label (e.g. approve)"
            style={{ ...ps.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
          />
        </>
      )}

      <div style={ps.condFormActions}>
        <button style={{ ...ps.addBtn, marginTop: 0 }} onClick={onCancel}>
          Cancel
        </button>
        <button style={{ ...ps.addBtn, marginTop: 0, color: t.accent, borderColor: t.accent }} onClick={onSubmit}>
          Add
        </button>
      </div>
    </div>
  )
}
