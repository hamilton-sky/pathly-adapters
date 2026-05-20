import clsx from 'clsx'
import s from '../../shared/panel.module.css'
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
}

export function AddConditionForm({ addCond, setAddCond, onSubmit, onCancel }: AddConditionFormProps): JSX.Element {
  return (
    <div className={s.conditionBox}>
      <div className={s.condFormRow}>
        <select
          aria-label="Condition type"
          title="Condition type"
          value={addCond.type}
          onChange={(e) => setAddCond((prev) => ({ ...prev, type: e.target.value as ConditionType }))}
          className={s.condSelectStyle}
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
          onChange={(e) => setAddCond((prev) => ({ ...prev, artifact: e.target.value }))}
          placeholder="artifact.md"
          className={clsx(s.input, s.mb6)}
        />
      )}

      {addCond.type === 'on_content' && (
        <>
          <input
            value={addCond.file}
            onChange={(e) => setAddCond((prev) => ({ ...prev, file: e.target.value }))}
            placeholder="file.md"
            className={clsx(s.input, s.mb4)}
          />
          <input
            value={addCond.contains}
            onChange={(e) => setAddCond((prev) => ({ ...prev, contains: e.target.value }))}
            placeholder="contains text…"
            className={clsx(s.input, s.mb6)}
          />
        </>
      )}

      {addCond.type === 'decide' && (
        <>
          <input
            value={addCond.question}
            onChange={(e) => setAddCond((prev) => ({ ...prev, question: e.target.value }))}
            placeholder="Question for human?"
            className={clsx(s.input, s.mb4)}
          />
          <input
            value={addCond.optionLabel}
            onChange={(e) => setAddCond((prev) => ({ ...prev, optionLabel: e.target.value }))}
            placeholder="Option label (e.g. approve)"
            className={clsx(s.input, s.mb6)}
          />
        </>
      )}

      <div className={s.condFormActions}>
        <button className={clsx(s.addBtn, s.addBtnFlush)} onClick={onCancel}>
          Cancel
        </button>
        <button className={clsx(s.addBtn, s.addBtnFlush, s.addBtnAccent)} onClick={onSubmit}>
          Add
        </button>
      </div>
    </div>
  )
}
