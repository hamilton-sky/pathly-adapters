import React, { useId } from 'react'
import clsx from 'clsx'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import s from '../shared/panel.module.css'
import { PanelHeader } from '../shared/PanelHeader'
import { useRenameState } from './hooks/useRenameState'
import { useBehaviorList } from './hooks/useBehaviorList'
import { useRequiredArtifacts } from './hooks/useRequiredArtifacts'
import { useBehaviorSearch } from './hooks/useBehaviorSearch'

interface NodePanelProps {
  stateId: string
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onRename?: (oldId: string, newId: string) => void
  onClose: () => void
  onRemove: () => void
  issues?: FlowValidationIssue[]
}

export function NodePanel({ stateId, data, onAgentChange, onRename, onClose, onRemove, issues }: NodePanelProps): JSX.Element {
  const renameInputId = useId()

  const currentAgent = data.agent_map[stateId] ?? ''

  const { renaming, renameValue, renameInputRef, setRenaming, setRenameValue, commitRename } =
    useRenameState(stateId, data, onRename)

  const behaviors = useBehaviorList()
  const inLibrary = !currentAgent || behaviors.some((b) => b.name === currentAgent)

  const requiredArtifacts = useRequiredArtifacts(currentAgent)

  const { query, setQuery, activeIndex, filtered, searchRef, listRef, handleSearchKeyDown } =
    useBehaviorSearch(behaviors, (name) => onAgentChange(stateId, name))

  const outgoing = data.transitions[stateId] ?? []
  const nodeIssues = issues?.filter((i) => i.target === 'node' && i.id === stateId) ?? []

  return (
    <div className={s.panelScrollable}>
      <PanelHeader title={stateId} onClose={onClose} />

      <button onClick={onRemove} className={s.dangerBtn}>
        Remove from canvas
      </button>

      <div>
        <label htmlFor={renameInputId} className={s.label}>State ID</label>
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
            <button onMouseDown={(e) => { e.preventDefault(); commitRename() }} className={s.renameConfirmBtn}>
              ✓
            </button>
          </div>
        ) : (
          <div
            className={clsx(s.stateIdDisplay, onRename && s.stateIdDisplayEditable)}
            onClick={() => onRename && setRenaming(true)}
            title={onRename ? 'Click to rename' : undefined}
          >
            <span className={s.stateIdText}>{stateId}</span>
            {onRename && <span className={s.editHint}>✎</span>}
          </div>
        )}
      </div>

      <div className={s.behaviorSection}>
        <div className={s.label}>Assigned behavior</div>

        {currentAgent ? (
          <div className={s.agentChipRow}>
            <span className={clsx(s.agentChip, !inLibrary && s.agentChipWarn)}>
              {!inLibrary && <span className={s.agentWarnIcon} title="Not found in library">⚠</span>}
              {currentAgent}
            </span>
            <button
              onClick={() => onAgentChange(stateId, '')}
              title="Clear assignment"
              className={s.agentClearBtn}
            >
              ×
            </button>
          </div>
        ) : (
          <div className={s.noAssigned}>None assigned</div>
        )}

        <input
          ref={searchRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          placeholder="Search behaviors…"
          className={s.searchInput}
        />

        <ul ref={listRef} role="listbox" aria-label="Available behaviors" className={s.behaviorList}>
          {filtered.length === 0 && (
            <li role="option" aria-selected="false" className={clsx(s.behaviorItem, s.noAssigned)}>No matches</li>
          )}
          {filtered.map((b, idx) => {
            const isActive = b.name === currentAgent
            const isHighlighted = idx === activeIndex
            return (
              <li
                key={b.name}
                role="option"
                {...{ 'aria-selected': isActive ? 'true' : 'false' } as React.AriaAttributes}
                onClick={() => onAgentChange(stateId, b.name)}
                className={clsx(
                  s.behaviorItem,
                  isHighlighted && s.behaviorItemHighlighted,
                  isActive && s.behaviorItemActive,
                )}
              >
                <span className={clsx(s.behaviorKindBadge, b.kind === 'skill' ? s.behaviorKindBadgeSkill : s.behaviorKindBadgeAgent)}>
                  {b.kind === 'skill' ? 'SKILL' : 'AGENT'}
                </span>
                <span className={s.behaviorItemLabel}>{b.name}</span>
                {isActive && <span className={s.behaviorCheckmark}>✓</span>}
              </li>
            )
          })}
        </ul>
      </div>

      {requiredArtifacts !== null && (
        <div>
          <div className={s.label}>Required artifacts</div>
          {requiredArtifacts.length === 0 ? (
            <div className={s.artifactNone}>none</div>
          ) : (
            <ul className={s.artifactList}>
              {requiredArtifacts.map((artifact) => (
                <li key={artifact} className={s.artifactItem}>{artifact}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div>
        <div className={s.label}>Outgoing transitions</div>
        {outgoing.length === 0 ? (
          <div className={s.noAssigned}>None</div>
        ) : (
          <ul className={s.outgoingList}>
            {outgoing.map((tgt) => (
              <li key={tgt} className={s.outgoingItem}>
                <span className={s.outgoingArrow}>→</span>
                <span className={s.outgoingTarget}>{tgt}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {nodeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          <div className={s.label}>Validation</div>
          {nodeIssues.map((issue, i) => (
            <div key={i} className={issue.level === 'error' ? s.validationError : s.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
