import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'
import { useTransitionConditions } from './hooks/useTransitionConditions'
import { useActionEditor } from './hooks/useActionEditor'
import { AddConditionForm } from './parts/AddConditionForm'

// Human-readable label mapping — raw YAML keys never shown in UI
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
  t: Theme
  onDataChange?: (updated: FlowYaml) => void
  issues?: FlowValidationIssue[]
}

export function EdgePanel({ source, target, data, onAddAction, onClose, onRemove, t, onDataChange, issues }: EdgePanelProps): JSX.Element {
  const ps = makePanelStyles(t)
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
    <div style={{ ...ps.panel, overflowY: 'auto' }}>
      <PanelHeader title={`${source} → ${target}`} onClose={onClose} t={t} />

      {/* Delete connection */}
      <button onClick={onRemove} style={ps.dangerBtn}>
        Delete connection
      </button>

      {/* Validation issues */}
      {edgeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          {edgeIssues.map((issue, i) => (
            <div key={i} style={issue.level === 'error' ? ps.validationError : ps.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}

      {/* default rule */}
      {sourceRule.default === target && (
        <div style={ps.section}>
          <div style={ps.label}>{CONDITION_LABELS.default.icon} {CONDITION_LABELS.default.label}</div>
          <div style={ps.condRow}>
            <span style={ps.condTarget}>{target}</span>
            {onDataChange && (
              <button style={ps.removeBtn} onClick={removeDefault} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      {/* on_artifact rules */}
      {sourceRule.on_artifact && Object.entries(sourceRule.on_artifact).filter(([, tgt]) => tgt === target).length > 0 && (
        <div style={ps.section}>
          <div style={ps.label}>{CONDITION_LABELS.on_artifact.icon} {CONDITION_LABELS.on_artifact.label}</div>
          {Object.entries(sourceRule.on_artifact)
            .filter(([, tgt]) => tgt === target)
            .map(([artifactName]) => (
              <div key={artifactName} style={ps.condRow}>
                <span style={ps.condArtifact}>{artifactName}</span>
                {onDataChange && (
                  <button style={ps.removeBtn} onClick={() => removeArtifactEntry(artifactName)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {/* on_content rules */}
      {sourceRule.on_content && sourceRule.on_content.filter((e) => e.next === target).length > 0 && (
        <div style={ps.section}>
          <div style={ps.label}>{CONDITION_LABELS.on_content.icon} {CONDITION_LABELS.on_content.label}</div>
          {sourceRule.on_content
            .map((entry, idx) => ({ entry, idx }))
            .filter(({ entry }) => entry.next === target)
            .map(({ entry, idx }) => (
              <div key={idx} style={ps.condRow}>
                <span style={ps.condText}>
                  {entry.file}{entry.contains ? ` contains "${entry.contains}"` : ''}
                </span>
                {onDataChange && (
                  <button style={ps.removeBtn} onClick={() => removeContentEntry(idx)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {/* decide options */}
      {sourceRule.decide?.options && Object.entries(sourceRule.decide.options).filter(([, tgt]) => tgt === target).length > 0 && (
        <div style={ps.section}>
          <div style={ps.label}>{CONDITION_LABELS.decide.icon} {CONDITION_LABELS.decide.label}</div>
          <div style={ps.condRow}>
            <span style={ps.condText}>
              {sourceRule.decide.question ? `"${sourceRule.decide.question}"` : 'Decision'}
            </span>
            {onDataChange && (
              <button style={ps.removeBtn} onClick={removeDecide} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      {/* transition_actions */}
      <div style={ps.section}>
        <div style={ps.label}>{CONDITION_LABELS.transition_actions.icon} {CONDITION_LABELS.transition_actions.label}</div>
        {actionList.length === 0 ? (
          <div style={{ fontSize: '12px', color: t.textMuted }}>None</div>
        ) : (
          actionList.map((action, i) =>
            editingActionIdx === i ? (
              <div key={i} style={ps.actionEditRow}>
                <input
                  value={editSkill}
                  onChange={(e) => setEditSkill(e.target.value)}
                  placeholder="skill or agent name"
                  autoFocus
                  style={{ ...ps.input, width: '100%', boxSizing: 'border-box' }}
                />
                <input
                  value={editMessage}
                  onChange={(e) => setEditMessage(e.target.value)}
                  placeholder="message…"
                  onKeyDown={(e) => { if (e.key === 'Enter') commitEditAction(); if (e.key === 'Escape') cancelEditAction() }}
                  style={{ ...ps.input, width: '100%', boxSizing: 'border-box' }}
                />
                <div style={ps.actionEditActions}>
                  <button style={ps.cancelEditBtn} onClick={cancelEditAction}>Cancel</button>
                  <button style={ps.saveEditBtn} onClick={commitEditAction}>Save</button>
                </div>
              </div>
            ) : (
              <div
                key={i}
                style={onDataChange ? ps.actionDisplayRow : ps.actionDisplayRowReadOnly}
                onClick={() => onDataChange && startEditAction(i)}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
                  <span style={action.skill ? ps.actionSkillActive : ps.actionSkillEmpty}>{action.skill || '(skill)'}</span>
                  <span style={ps.actionMsg}>{action.message || '(message)'}</span>
                </div>
                {onDataChange && (
                  <button style={ps.removeBtn} onClick={(e) => { e.stopPropagation(); removeAction(i) }} title="Remove">×</button>
                )}
              </div>
            )
          )
        )}
        <button style={ps.addBtn} onClick={() => onAddAction(source, target)}>
          + Add action
        </button>
      </div>

      {/* Add condition section */}
      {onDataChange && (
        <div style={ps.section}>
          {!addCond.open ? (
            <button
              style={ps.addBtn}
              onClick={() => setAddCond((s) => ({ ...s, open: true }))}
            >
              + Add condition
            </button>
          ) : (
            <AddConditionForm
              addCond={addCond}
              setAddCond={setAddCond}
              onSubmit={submitAddCondition}
              onCancel={() => setAddCond((s) => ({ ...s, open: false }))}
              t={t}
            />
          )}
        </div>
      )}
    </div>
  )
}
