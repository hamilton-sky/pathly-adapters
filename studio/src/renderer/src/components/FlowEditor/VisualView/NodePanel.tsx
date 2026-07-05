import React, { useId } from 'react'
import clsx from 'clsx'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import s from '../shared/panel.module.css'
import { Tooltip } from '../../ui'
import { useRenameState } from './hooks/useRenameState'
import { useBehaviorList } from './hooks/useBehaviorList'
import { useRequiredArtifacts } from './hooks/useRequiredArtifacts'

const ADAPTER_OPTIONS = [
  { value: '', label: '— unassigned —' },
  { value: 'claude', label: 'Claude Code' },
  { value: 'codex', label: 'Codex' },
  { value: 'antigravity', label: 'Antigravity' },
  { value: 'copilot', label: 'Copilot' },
]

function agentAccent(agent: string): string {
  const a = (agent ?? '').toLowerCase()
  if (a.includes('review')) return '#A78BFA'
  if (a.includes('test')) return 'var(--yellow)'
  if (a.includes('retro') || a.includes('done')) return 'var(--green)'
  return 'var(--blue)'
}

function getConditionTag(
  rules: Record<string, unknown> | undefined,
  source: string,
  target: string,
): string {
  if (!rules) return ''
  const rule = rules[source] as {
    default?: string
    on_artifact?: Record<string, string>
    on_content?: Array<{ next: string }>
    decide?: { options?: Record<string, string> }
  } | undefined
  if (!rule) return ''
  if (rule.default === target) return 'default'
  if (rule.on_artifact) {
    const arts = Object.entries(rule.on_artifact)
      .filter(([, t]) => t === target)
      .map(([a]) => a.replace(/\.md$/i, ''))
    if (arts.length > 0) return arts[0]
  }
  if (rule.on_content?.some((e) => e.next === target)) return 'on content'
  if (rule.decide?.options && Object.values(rule.decide.options).includes(target)) return 'decide'
  return ''
}

interface NodePanelProps {
  stateId: string
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onAdapterChange: (stateId: string, value: string) => void
  onSkillChange: (stateId: string, value: string) => void
  onRename?: (oldId: string, newId: string) => void
  onClose: () => void
  onRemove: () => void
  onSelectEdge?: (source: string, target: string) => void
  issues?: FlowValidationIssue[]
}

export function NodePanel({
  stateId,
  data,
  onAgentChange,
  onAdapterChange,
  onSkillChange,
  onRename,
  onClose,
  onRemove,
  onSelectEdge,
  issues,
}: NodePanelProps): JSX.Element {
  const renameInputId = useId()

  const currentAgent = data.agent_map?.[stateId] ?? ''
  const currentAdapter = data.adapter_map?.[stateId] ?? ''
  const currentSkill = data.skill_map?.[stateId] ?? ''

  const { renaming, renameValue, renameInputRef, setRenaming, setRenameValue, commitRename } =
    useRenameState(stateId, data, onRename)

  const behaviors = useBehaviorList()
  const agents = behaviors.filter((b) => b.kind === 'agent')
  const skills = behaviors.filter((b) => b.kind === 'skill')

  const requiredArtifacts = useRequiredArtifacts(currentAgent)

  const stateIndex = new Map((data.states ?? []).map((st, i) => [st, i] as [string, number]))
  const srcIdx = stateIndex.get(stateId) ?? 0

  const outgoing = data.transitions?.[stateId] ?? []
  const rules = data.transition_rules as Record<string, unknown> | undefined
  const nodeIssues = issues?.filter((i) => i.target === 'node' && i.id === stateId) ?? []

  const accent = agentAccent(currentAgent)

  return (
    <div className={s.panelScrollable}>
      {/* Inspector header */}
      <div className={s.header}>
        <div className={s.inspHeader}>
          <span
            className={s.inspPip}
            style={{ '--pip-color': accent } as React.CSSProperties}
          />
          <span className={s.inspTitle}>State · {stateId}</span>
        </div>
        <Tooltip label="Close panel" shortcut="Esc" placement="left">
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Close panel">×</button>
        </Tooltip>
      </div>

      {/* State name */}
      <div className={s.section}>
        <label htmlFor={renameInputId} className={s.label}>State name</label>
        {renaming ? (
          <div className={s.renameRow}>
            <input
              id={renameInputId}
              ref={renameInputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'))}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename()
                if (e.key === 'Escape') { setRenaming(false); setRenameValue(stateId) }
              }}
              className={s.renameInput}
            />
            <button type="button" onMouseDown={(e) => { e.preventDefault(); commitRename() }} className={s.renameConfirmBtn}>
              ✓
            </button>
          </div>
        ) : onRename ? (
          <Tooltip label="Click to rename" placement="bottom">
            <div
              className={clsx(s.ctrl, s.ctrlMono, s.ctrlClickable)}
              onClick={() => setRenaming(true)}
            >
              <span className={s.ctrlText}>{stateId}</span>
              <span className={s.ctrlEditHint}>&#x270E;</span>
            </div>
          </Tooltip>
        ) : (
          <div className={clsx(s.ctrl, s.ctrlMono)}>
            <span className={s.ctrlText}>{stateId}</span>
          </div>
        )}
      </div>

      {/* CLI host (adapter) */}
      <div className={s.section}>
        <label className={s.label}>CLI host</label>
        <div className={s.ctrlSelectWrapper}>
          <select
            className={s.ctrlSelect}
            value={currentAdapter}
            onChange={(e) => onAdapterChange(stateId, e.target.value)}
            aria-label="CLI host"
          >
            {ADAPTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <span className={s.ctrlSelectChevron} aria-hidden="true">▾</span>
        </div>
      </div>

      {/* Agent */}
      <div className={s.section}>
        <label className={s.label}>Agent</label>
        <div className={s.ctrlSelectWrapper}>
          <select
            className={s.ctrlSelect}
            value={currentAgent}
            onChange={(e) => onAgentChange(stateId, e.target.value)}
            aria-label="Agent"
          >
            <option value="">— unassigned —</option>
            {agents.map((a) => (
              <option key={a.name} value={a.name}>{a.name}</option>
            ))}
            {currentAgent && !agents.some((a) => a.name === currentAgent) && (
              <option value={currentAgent}>{currentAgent} (unknown)</option>
            )}
          </select>
          <span className={s.ctrlSelectChevron} aria-hidden="true">▾</span>
        </div>
      </div>

      {/* Skill */}
      <div className={s.section}>
        <label className={s.label}>Skill</label>
        <div className={s.ctrlSelectWrapper}>
          <select
            className={s.ctrlSelect}
            value={currentSkill}
            onChange={(e) => onSkillChange(stateId, e.target.value)}
            aria-label="Skill"
          >
            <option value="">— none —</option>
            {skills.map((sk) => (
              <option key={sk.name} value={sk.name}>{sk.name}</option>
            ))}
            {currentSkill && !skills.some((sk) => sk.name === currentSkill) && (
              <option value={currentSkill}>{currentSkill}</option>
            )}
          </select>
          <span className={s.ctrlSelectChevron} aria-hidden="true">▾</span>
        </div>
      </div>

      {/* Required artifacts (read-only hint) */}
      {requiredArtifacts !== null && requiredArtifacts.length > 0 && (
        <div className={s.section}>
          <div className={s.label}>Required artifacts</div>
          <ul className={s.artifactList}>
            {requiredArtifacts.map((artifact) => (
              <li key={artifact} className={s.artifactItem}>{artifact}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Transitions */}
      <div className={s.section}>
        <div className={s.label}>Transitions</div>
        {outgoing.length === 0 ? (
          <div className={s.noAssigned}>None — draw an edge from this node</div>
        ) : (
          <div className={s.transSection}>
            {outgoing.map((target) => {
              const tgtIdx = stateIndex.get(target) ?? 0
              const isBackward = tgtIdx < srcIdx || target === stateId
              const condTag = getConditionTag(rules, stateId, target)
              return (
                <Tooltip label="Click to configure this transition" placement="bottom">
                  <button
                    key={target}
                    type="button"
                    className={s.transRow}
                    onClick={() => onSelectEdge?.(stateId, target)}
                  >
                    <span className={s.transKey}>{isBackward ? 'retry' : 'next'}</span>
                    <span className={clsx(s.transVal, isBackward && s.transValReturn)}>
                      {isBackward ? '↩ ' : '→ '}{target}
                    </span>
                    {condTag && <span className={s.transCondTag}>{condTag}</span>}
                  </button>
                </Tooltip>
              )
            })}
          </div>
        )}
      </div>

      {/* Validation issues */}
      {nodeIssues.length > 0 && (
        <div role="alert" aria-live="polite" className={s.section}>
          <div className={s.label}>Validation</div>
          {nodeIssues.map((issue, i) => (
            <div key={i} className={issue.level === 'error' ? s.validationError : s.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}

      <button type="button" onClick={onRemove} className={s.dangerBtn}>
        Remove from canvas
      </button>
    </div>
  )
}
