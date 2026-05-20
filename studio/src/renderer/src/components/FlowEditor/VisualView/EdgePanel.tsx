import clsx from 'clsx'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import s from '../shared/panel.module.css'
import { PanelHeader } from '../shared/PanelHeader'
import { useTransitionConditions } from './hooks/useTransitionConditions'
import { useActionEditor } from './hooks/useActionEditor'
import { AddConditionForm } from './parts/AddConditionForm'

const CONDITION_LABELS: Record<string, { label: string; icon: string }> = {
  default:            { label: 'Always continues to →', icon: '→' },
  on_artifact:        { label: 'When artifact arrives:', icon: '📄' },
  on_content:         { label: 'When file contains:', icon: '🔍' },
  decide:             { label: 'Human decision required:', icon: '⑃' },
  transition_actions: { label: 'Run before transitioning:', icon: '⚡' },
}

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
      <PanelHeader title={`${source} → ${target}`} onClose={onClose} />

      <button onClick={onRemove} className={s.dangerBtn}>
        Delete connection
      </button>

      {edgeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          {edgeIssues.map((issue, i) => (
            <div key={i} className={issue.level === 'error' ? s.validationError : s.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}

      {sourceRule.default === target && (
        <div className={s.section}>
          <div className={s.label}>{CONDITION_LABELS.default.icon} {CONDITION_LABELS.default.label}</div>
          <div className={s.condRow}>
            <span className={s.condTarget}>{target}</span>
            {onDataChange && (
              <button className={s.removeBtn} onClick={removeDefault} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      {sourceRule.on_artifact && Object.entries(sourceRule.on_artifact).filter(([, tgt]) => tgt === target).length > 0 && (
        <div className={s.section}>
          <div className={s.label}>{CONDITION_LABELS.on_artifact.icon} {CONDITION_LABELS.on_artifact.label}</div>
          {Object.entries(sourceRule.on_artifact)
            .filter(([, tgt]) => tgt === target)
            .map(([artifactName]) => (
              <div key={artifactName} className={s.condRow}>
                <span className={s.condArtifact}>{artifactName}</span>
                {onDataChange && (
                  <button className={s.removeBtn} onClick={() => removeArtifactEntry(artifactName)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {sourceRule.on_content && sourceRule.on_content.filter((e) => e.next === target).length > 0 && (
        <div className={s.section}>
          <div className={s.label}>{CONDITION_LABELS.on_content.icon} {CONDITION_LABELS.on_content.label}</div>
          {sourceRule.on_content
            .map((entry, idx) => ({ entry, idx }))
            .filter(({ entry }) => entry.next === target)
            .map(({ entry, idx }) => (
              <div key={idx} className={s.condRow}>
                <span className={s.condText}>
                  {entry.file}{entry.contains ? ` contains "${entry.contains}"` : ''}
                </span>
                {onDataChange && (
                  <button className={s.removeBtn} onClick={() => removeContentEntry(idx)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {sourceRule.decide?.options && Object.entries(sourceRule.decide.options).filter(([, tgt]) => tgt === target).length > 0 && (
        <div className={s.section}>
          <div className={s.label}>{CONDITION_LABELS.decide.icon} {CONDITION_LABELS.decide.label}</div>
          <div className={s.condRow}>
            <span className={s.condText}>
              {sourceRule.decide.question ? `"${sourceRule.decide.question}"` : 'Decision'}
            </span>
            {onDataChange && (
              <button className={s.removeBtn} onClick={removeDecide} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      <div className={s.section}>
        <div className={s.label}>{CONDITION_LABELS.transition_actions.icon} {CONDITION_LABELS.transition_actions.label}</div>
        {actionList.length === 0 ? (
          <div className={s.noAssigned}>None</div>
        ) : (
          actionList.map((action, i) =>
            editingActionIdx === i ? (
              <div key={i} className={s.actionEditRow}>
                <input
                  value={editSkill}
                  onChange={(e) => setEditSkill(e.target.value)}
                  placeholder="skill or agent name"
                  autoFocus
                  className={s.input}
                />
                <input
                  value={editMessage}
                  onChange={(e) => setEditMessage(e.target.value)}
                  placeholder="message…"
                  onKeyDown={(e) => { if (e.key === 'Enter') commitEditAction(); if (e.key === 'Escape') cancelEditAction() }}
                  className={s.input}
                />
                <div className={s.actionEditActions}>
                  <button className={s.cancelEditBtn} onClick={cancelEditAction}>Cancel</button>
                  <button className={s.saveEditBtn} onClick={commitEditAction}>Save</button>
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
                  <button className={s.removeBtn} onClick={(e) => { e.stopPropagation(); removeAction(i) }} title="Remove">×</button>
                )}
              </div>
            )
          )
        )}
        <button className={s.addBtn} onClick={() => onAddAction(source, target)}>
          + Add action
        </button>
      </div>

      {onDataChange && (
        <div className={s.section}>
          {!addCond.open ? (
            <button
              className={s.addBtn}
              onClick={() => setAddCond((prev) => ({ ...prev, open: true }))}
            >
              + Add condition
            </button>
          ) : (
            <AddConditionForm
              addCond={addCond}
              setAddCond={setAddCond}
              onSubmit={submitAddCondition}
              onCancel={() => setAddCond((prev) => ({ ...prev, open: false }))}
            />
          )}
        </div>
      )}
    </div>
  )
}
