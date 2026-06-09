import clsx from 'clsx'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import s from '../shared/panel.module.css'
import { Tooltip } from '../../ui'
import { useTransitionConditions } from './hooks/useTransitionConditions'
import { useActionEditor } from './hooks/useActionEditor'
import { AddConditionForm } from './parts/AddConditionForm'

interface EdgePanelProps {
  source: string
  target: string
  data: FlowYaml
  onAddAction: (source: string, target: string) => void
  onClose: () => void
  onRemove: () => void
  onDataChange?: (updated: FlowYaml) => void
  issues?: FlowValidationIssue[]
}

export function EdgePanel({ source, target, data, onAddAction, onClose, onRemove, onDataChange, issues }: EdgePanelProps): JSX.Element {
  const actionKey = `${source}->${target}`

  const actions = (data.transition_actions as Record<string, Array<{ skill: string; message: string }>> | undefined) ?? {}
  const actionList = actions[actionKey] ?? []

  const rules = (data.transition_rules as Record<string, import('./hooks/useTransitionConditions').StateRule> | undefined) ?? {}
  const sourceRule = rules[source] ?? {}

  const { addCond, setAddCond, submitAddCondition, removeDefault, removeArtifactEntry, removeContentEntry, removeDecide } =
    useTransitionConditions(source, target, data, onDataChange)

  const { editingActionIdx, editSkill, editMessage, setEditSkill, setEditMessage, startEditAction, commitEditAction, cancelEditAction, removeAction } =
    useActionEditor(actionKey, actionList, actions, data, onDataChange)

  const edgeIssues = issues?.filter((i) => i.target === 'edge' && i.id === actionKey) ?? []

  return (
    <div className={clsx(s.panel, s.panelScrollable)}>
      {/* Header */}
      <div className={s.header}>
        <div className={s.inspHeader}>
          <span className={s.edgeHeaderArrow}>→</span>
          <span className={s.edgeHeaderTitle}>{source} → {target}</span>
        </div>
        <Tooltip label="Close panel" shortcut="Esc" placement="left">
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Close panel">×</button>
        </Tooltip>
      </div>

      {/* Validation */}
      {edgeIssues.length > 0 && (
        <div role="alert" aria-live="polite" className={s.section}>
          {edgeIssues.map((issue, i) => (
            <div key={i} className={issue.level === 'error' ? s.validationError : s.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}

      {/* Conditions section */}
      <div className={s.section}>
        <div className={s.label}>Conditions</div>

        {sourceRule.default === target && (
          <div className={s.condPill}>
            <span className={s.condPillKey}>default</span>
            <span className={clsx(s.condPillVal, s.condPillTarget)}>{target}</span>
            {onDataChange && (
              <Tooltip label="Remove" placement="top">
                <button type="button" className={s.removeBtn} onClick={removeDefault} aria-label="Remove">×</button>
              </Tooltip>
            )}
          </div>
        )}

        {sourceRule.on_artifact && Object.entries(sourceRule.on_artifact)
          .filter(([, tgt]) => tgt === target)
          .map(([artifactName]) => (
            <div key={artifactName} className={s.condPill}>
              <span className={s.condPillKey}>artifact</span>
              <span className={clsx(s.condPillVal, s.condPillArtifact)}>{artifactName}</span>
              {onDataChange && (
                <Tooltip label="Remove" placement="top">
                <button type="button" className={s.removeBtn} onClick={() => removeArtifactEntry(artifactName)} aria-label="Remove">×</button>
              </Tooltip>
              )}
            </div>
          ))
        }

        {sourceRule.on_content && sourceRule.on_content
          .map((entry, idx) => ({ entry, idx }))
          .filter(({ entry }) => entry.next === target)
          .map(({ entry, idx }) => (
            <div key={idx} className={s.condPill}>
              <span className={s.condPillKey}>content</span>
              <span className={s.condPillVal}>{entry.file}{entry.contains ? ` → "${entry.contains}"` : ''}</span>
              {onDataChange && (
                <Tooltip label="Remove" placement="top">
                <button type="button" className={s.removeBtn} onClick={() => removeContentEntry(idx)} aria-label="Remove">×</button>
              </Tooltip>
              )}
            </div>
          ))
        }

        {sourceRule.decide?.options && Object.entries(sourceRule.decide.options)
          .filter(([, tgt]) => tgt === target)
          .length > 0 && (
            <div className={s.condPill}>
              <span className={s.condPillKey}>decide</span>
              <span className={s.condPillVal}>
                {sourceRule.decide.question ? `"${sourceRule.decide.question}"` : 'Human decision'}
              </span>
              {onDataChange && (
                <Tooltip label="Remove" placement="top">
                <button type="button" className={s.removeBtn} onClick={removeDecide} aria-label="Remove">×</button>
              </Tooltip>
              )}
            </div>
          )
        }

        {!sourceRule.default && !sourceRule.on_artifact && !sourceRule.on_content && !sourceRule.decide && (
          <div className={s.noAssigned}>No conditions — transition fires freely</div>
        )}

        {onDataChange && (
          !addCond.open ? (
            <button type="button" className={s.addBtn} onClick={() => setAddCond((prev) => ({ ...prev, open: true }))}>
              + Add condition
            </button>
          ) : (
            <AddConditionForm
              addCond={addCond}
              setAddCond={setAddCond}
              onSubmit={submitAddCondition}
              onCancel={() => setAddCond((prev) => ({ ...prev, open: false }))}
            />
          )
        )}
      </div>

      {/* Actions section */}
      <div className={s.section}>
        <div className={s.label}>⚡ Pre-transition actions</div>
        {actionList.length === 0 ? (
          <div className={s.noAssigned}>None</div>
        ) : (
          actionList.map((action, i) =>
            editingActionIdx === i ? (
              <div key={i} className={s.actionEditRow}>
                <input value={editSkill} onChange={(e) => setEditSkill(e.target.value)} placeholder="skill or agent name" autoFocus className={s.input} />
                <input
                  value={editMessage}
                  onChange={(e) => setEditMessage(e.target.value)}
                  placeholder="message…"
                  onKeyDown={(e) => { if (e.key === 'Enter') commitEditAction(); if (e.key === 'Escape') cancelEditAction() }}
                  className={s.input}
                />
                <div className={s.actionEditActions}>
                  <button type="button" className={s.cancelEditBtn} onClick={cancelEditAction}>Cancel</button>
                  <button type="button" className={s.saveEditBtn} onClick={commitEditAction}>Save</button>
                </div>
              </div>
            ) : (
              <div
                key={i}
                className={onDataChange ? s.actionDisplayRow : s.actionDisplayRowReadOnly}
                onClick={() => onDataChange && startEditAction(i)}
              >
                <div className={s.actionRow}>
                  <span className={action.skill ? s.actionSkillActive : s.actionSkillEmpty}>{action.skill || '(skill)'}</span>
                  <span className={s.actionMsg}>{action.message || '(message)'}</span>
                </div>
                {onDataChange && (
                  <Tooltip label="Remove" placement="top">
                    <button type="button" className={s.removeBtn} onClick={(e) => { e.stopPropagation(); removeAction(i) }} aria-label="Remove">×</button>
                  </Tooltip>
                )}
              </div>
            )
          )
        )}
        <button type="button" className={s.addBtn} onClick={() => onAddAction(source, target)}>
          + Add action
        </button>
      </div>

      <button type="button" onClick={onRemove} className={s.dangerBtn}>
        Delete connection
      </button>
    </div>
  )
}
