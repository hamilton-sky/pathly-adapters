import { useState } from 'react'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'

// Human-readable label mapping — raw YAML keys never shown in UI
const CONDITION_LABELS: Record<string, { label: string; icon: string }> = {
  default:           { label: 'Always continues to →', icon: '→' },
  on_artifact:       { label: 'When artifact arrives:', icon: '📄' },
  on_content:        { label: 'When file contains:', icon: '🔍' },
  decide:            { label: 'Human decision required:', icon: '⑃' },
  transition_actions:{ label: 'Run before transitioning:', icon: '⚡' },
}

type ConditionType = 'default' | 'on_artifact' | 'on_content' | 'decide'

interface StateRule {
  default?: string
  on_artifact?: Record<string, string>
  on_content?: Array<{ file?: string; contains?: string; regex?: string; next: string }>
  decide?: { question?: string; options?: Record<string, string>; default?: string }
}

interface AddConditionState {
  open: boolean
  type: ConditionType
  artifact: string
  file: string
  contains: string
  question: string
  optionLabel: string
}

interface EdgePanelProps {
  source: string
  target: string
  data: FlowYaml
  onAddAction: (source: string, target: string) => void
  onClose: () => void
  t: Theme
  onDataChange?: (updated: FlowYaml) => void
  issues?: FlowValidationIssue[]
}

export function EdgePanel({ source, target, data, onAddAction, onClose, t, onDataChange, issues }: EdgePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const actionKey = `${source}->${target}`

  const actions = (data.transition_actions as Record<string, Array<{ skill: string; message: string }>> | undefined) ?? {}
  const actionList = actions[actionKey] ?? []

  const rules = (data.transition_rules as Record<string, StateRule> | undefined) ?? {}
  const sourceRule: StateRule = rules[source] ?? {}

  const [addCond, setAddCond] = useState<AddConditionState>({
    open: false, type: 'default', artifact: '', file: '', contains: '', question: '', optionLabel: 'approve'
  })

  const edgeIssues = issues?.filter((i) => i.scope === 'edge' && i.key === actionKey) ?? []

  function updateRule(updated: StateRule): void {
    if (!onDataChange) return
    const newRules = { ...rules, [source]: updated }
    onDataChange({ ...data, transition_rules: newRules })
  }

  function removeDefault(): void {
    const updated = { ...sourceRule }
    delete updated.default
    updateRule(updated)
  }

  function removeArtifactEntry(artifactName: string): void {
    const newArtifacts = { ...(sourceRule.on_artifact ?? {}) }
    delete newArtifacts[artifactName]
    const updated: StateRule = { ...sourceRule, on_artifact: newArtifacts }
    if (Object.keys(newArtifacts).length === 0) delete updated.on_artifact
    updateRule(updated)
  }

  function removeContentEntry(idx: number): void {
    const arr = [...(sourceRule.on_content ?? [])]
    arr.splice(idx, 1)
    const updated: StateRule = { ...sourceRule, on_content: arr }
    if (arr.length === 0) delete updated.on_content
    updateRule(updated)
  }

  function removeDecide(): void {
    const updated = { ...sourceRule }
    delete updated.decide
    updateRule(updated)
  }

  function removeAction(idx: number): void {
    if (!onDataChange) return
    const newList = [...actionList]
    newList.splice(idx, 1)
    const newActions = { ...actions, [actionKey]: newList }
    onDataChange({ ...data, transition_actions: newActions })
  }

  function submitAddCondition(): void {
    const type = addCond.type
    if (type === 'default') {
      updateRule({ ...sourceRule, default: target })
    } else if (type === 'on_artifact') {
      const artifactName = addCond.artifact.trim() || 'artifact.md'
      updateRule({
        ...sourceRule,
        on_artifact: { ...(sourceRule.on_artifact ?? {}), [artifactName]: target }
      })
    } else if (type === 'on_content') {
      const entry = { file: addCond.file.trim() || 'notes.md', contains: addCond.contains.trim(), next: target }
      updateRule({
        ...sourceRule,
        on_content: [...(sourceRule.on_content ?? []), entry]
      })
    } else if (type === 'decide') {
      const question = addCond.question.trim() || 'Where next?'
      const optLabel = addCond.optionLabel.trim() || 'approve'
      updateRule({
        ...sourceRule,
        decide: { question, options: { [optLabel]: target }, default: optLabel }
      })
    }
    setAddCond((s) => ({ ...s, open: false }))
  }

  const sectionStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px'
  }
  const condRowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '4px',
    fontSize: '12px',
    backgroundColor: t.bgSurface0,
    borderRadius: '4px',
    padding: '6px 8px'
  }
  const removeBtnStyle: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: t.textMuted,
    cursor: 'pointer',
    fontSize: '12px',
    padding: '0 2px',
    flexShrink: 0
  }

  return (
    <div style={panelStyles.panel}>
      <PanelHeader title={`${source} → ${target}`} onClose={onClose} t={t} />

      {/* Validation issues */}
      {edgeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          {edgeIssues.map((issue, i) => (
            <div key={i} style={{ fontSize: '11px', color: issue.severity === 'error' ? t.red : t.yellow, padding: '2px 0' }}>
              {issue.message}
            </div>
          ))}
        </div>
      )}

      {/* default rule */}
      {sourceRule.default === target && (
        <div style={sectionStyle}>
          <div style={panelStyles.label}>{CONDITION_LABELS.default.icon} {CONDITION_LABELS.default.label}</div>
          <div style={condRowStyle}>
            <span style={{ color: t.blue }}>{target}</span>
            {onDataChange && (
              <button style={removeBtnStyle} onClick={removeDefault} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      {/* on_artifact rules for this edge */}
      {sourceRule.on_artifact && Object.entries(sourceRule.on_artifact).filter(([, tgt]) => tgt === target).length > 0 && (
        <div style={sectionStyle}>
          <div style={panelStyles.label}>{CONDITION_LABELS.on_artifact.icon} {CONDITION_LABELS.on_artifact.label}</div>
          {Object.entries(sourceRule.on_artifact)
            .filter(([, tgt]) => tgt === target)
            .map(([artifactName]) => (
              <div key={artifactName} style={condRowStyle}>
                <span style={{ color: t.green }}>{artifactName}</span>
                {onDataChange && (
                  <button style={removeBtnStyle} onClick={() => removeArtifactEntry(artifactName)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {/* on_content rules for this edge */}
      {sourceRule.on_content && sourceRule.on_content.filter((e) => e.next === target).length > 0 && (
        <div style={sectionStyle}>
          <div style={panelStyles.label}>{CONDITION_LABELS.on_content.icon} {CONDITION_LABELS.on_content.label}</div>
          {sourceRule.on_content
            .map((entry, idx) => ({ entry, idx }))
            .filter(({ entry }) => entry.next === target)
            .map(({ entry, idx }) => (
              <div key={idx} style={condRowStyle}>
                <span style={{ color: t.textSecondary, fontSize: '11px' }}>
                  {entry.file}{entry.contains ? ` contains "${entry.contains}"` : ''}
                </span>
                {onDataChange && (
                  <button style={removeBtnStyle} onClick={() => removeContentEntry(idx)} title="Remove">×</button>
                )}
              </div>
            ))}
        </div>
      )}

      {/* decide options for this edge */}
      {sourceRule.decide?.options && Object.entries(sourceRule.decide.options).filter(([, tgt]) => tgt === target).length > 0 && (
        <div style={sectionStyle}>
          <div style={panelStyles.label}>{CONDITION_LABELS.decide.icon} {CONDITION_LABELS.decide.label}</div>
          <div style={condRowStyle}>
            <span style={{ color: t.textSecondary, fontSize: '11px' }}>
              {sourceRule.decide.question ? `"${sourceRule.decide.question}"` : 'Decision'}
            </span>
            {onDataChange && (
              <button style={removeBtnStyle} onClick={removeDecide} title="Remove">×</button>
            )}
          </div>
        </div>
      )}

      {/* transition_actions */}
      <div style={sectionStyle}>
        <div style={panelStyles.label}>{CONDITION_LABELS.transition_actions.icon} {CONDITION_LABELS.transition_actions.label}</div>
        {actionList.length === 0 ? (
          <div style={{ fontSize: '12px', color: t.textMuted }}>None</div>
        ) : (
          actionList.map((action, i) => (
            <div key={i} style={condRowStyle}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
                <span style={{ color: t.green, fontSize: '11px' }}>{action.skill || '(skill)'}</span>
                <span style={{ color: t.textSecondary, fontSize: '11px' }}>{action.message || '(message)'}</span>
              </div>
              {onDataChange && (
                <button style={removeBtnStyle} onClick={() => removeAction(i)} title="Remove">×</button>
              )}
            </div>
          ))
        )}
        <button style={panelStyles.addBtn} onClick={() => onAddAction(source, target)}>
          + Add action
        </button>
      </div>

      {/* Add condition section */}
      {onDataChange && (
        <div style={sectionStyle}>
          {!addCond.open ? (
            <button
              style={panelStyles.addBtn}
              onClick={() => setAddCond((s) => ({ ...s, open: true }))}
            >
              + Add condition
            </button>
          ) : (
            <div style={{ backgroundColor: t.bgSurface0, borderRadius: '6px', padding: '8px' }}>
              <div style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
                <select
                  value={addCond.type}
                  onChange={(e) => setAddCond((s) => ({ ...s, type: e.target.value as ConditionType }))}
                  style={{
                    flex: 1,
                    backgroundColor: t.bgSurface1,
                    border: t.border,
                    borderRadius: '4px',
                    color: t.textPrimary,
                    fontSize: '12px',
                    padding: '4px'
                  }}
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
                  style={{ ...panelStyles.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
                />
              )}

              {addCond.type === 'on_content' && (
                <>
                  <input
                    value={addCond.file}
                    onChange={(e) => setAddCond((s) => ({ ...s, file: e.target.value }))}
                    placeholder="file.md"
                    style={{ ...panelStyles.input, width: '100%', marginBottom: '4px', boxSizing: 'border-box' }}
                  />
                  <input
                    value={addCond.contains}
                    onChange={(e) => setAddCond((s) => ({ ...s, contains: e.target.value }))}
                    placeholder='contains text…'
                    style={{ ...panelStyles.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
                  />
                </>
              )}

              {addCond.type === 'decide' && (
                <>
                  <input
                    value={addCond.question}
                    onChange={(e) => setAddCond((s) => ({ ...s, question: e.target.value }))}
                    placeholder="Question for human?"
                    style={{ ...panelStyles.input, width: '100%', marginBottom: '4px', boxSizing: 'border-box' }}
                  />
                  <input
                    value={addCond.optionLabel}
                    onChange={(e) => setAddCond((s) => ({ ...s, optionLabel: e.target.value }))}
                    placeholder="Option label (e.g. approve)"
                    style={{ ...panelStyles.input, width: '100%', marginBottom: '6px', boxSizing: 'border-box' }}
                  />
                </>
              )}

              <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                <button
                  style={{ ...panelStyles.addBtn, marginTop: 0 }}
                  onClick={() => setAddCond((s) => ({ ...s, open: false }))}
                >
                  Cancel
                </button>
                <button
                  style={{ ...panelStyles.addBtn, marginTop: 0, color: t.accent, borderColor: t.accent }}
                  onClick={submitAddCondition}
                >
                  Add
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
