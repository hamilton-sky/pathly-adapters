import { useId } from 'react'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import { makePanelStyles } from '../shared/panelStyles'
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
  t: Theme
  issues?: FlowValidationIssue[]
}

export function NodePanel({ stateId, data, onAgentChange, onRename, onClose, onRemove, t, issues }: NodePanelProps): JSX.Element {
  const ps = makePanelStyles(t)
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
    <div style={ps.panelScrollable}>
      <PanelHeader title={stateId} onClose={onClose} t={t} />

      <button onClick={onRemove} style={ps.dangerBtn}>
        Remove from canvas
      </button>

      <div>
        <label htmlFor={renameInputId} style={ps.label}>State ID</label>
        {renaming ? (
          <div style={ps.renameRow}>
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
              style={ps.renameInput}
            />
            <button onMouseDown={(e) => { e.preventDefault(); commitRename() }} style={ps.renameConfirmBtn}>
              ✓
            </button>
          </div>
        ) : (
          <div
            style={onRename ? ps.stateIdDisplayEditable : ps.stateIdDisplay}
            onClick={() => onRename && setRenaming(true)}
            title={onRename ? 'Click to rename' : undefined}
          >
            <span style={ps.stateIdText}>{stateId}</span>
            {onRename && <span style={ps.editHint}>✎</span>}
          </div>
        )}
      </div>

      <div style={ps.behaviorSection}>
        <div style={ps.label}>Assigned behavior</div>

        {currentAgent ? (
          <div style={ps.agentChipRow}>
            <span style={inLibrary ? ps.agentChip : ps.agentChipWarn}>
              {!inLibrary && <span style={ps.agentWarnIcon} title="Not found in library">⚠</span>}
              {currentAgent}
            </span>
            <button
              onClick={() => onAgentChange(stateId, '')}
              title="Clear assignment"
              style={ps.agentClearBtn}
            >
              ×
            </button>
          </div>
        ) : (
          <div style={ps.noAssigned}>None assigned</div>
        )}

        <input
          ref={searchRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          placeholder="Search behaviors…"
          style={ps.searchInput}
        />

        <ul ref={listRef} role="listbox" aria-label="Available behaviors" style={ps.behaviorList}>
          {filtered.length === 0 && (
            <li role="option" aria-selected={false} style={ps.noAssigned}>No matches</li>
          )}
          {filtered.map((b, idx) => {
            const isActive = b.name === currentAgent
            const isHighlighted = idx === activeIndex
            const itemStyle = isHighlighted
              ? (isActive ? ps.behaviorItemHighlightedActive : ps.behaviorItemHighlighted)
              : (isActive ? ps.behaviorItemDefaultActive : ps.behaviorItemDefault)
            return (
              <li
                key={b.name}
                role="option"
                aria-selected={isActive}
                onClick={() => onAgentChange(stateId, b.name)}
                style={itemStyle}
              >
                <span style={b.kind === 'skill' ? ps.behaviorKindBadgeSkill : ps.behaviorKindBadgeAgent}>
                  {b.kind === 'skill' ? 'SKILL' : 'AGENT'}
                </span>
                <span style={ps.behaviorItemLabel}>{b.name}</span>
                {isActive && <span style={ps.behaviorCheckmark}>✓</span>}
              </li>
            )
          })}
        </ul>
      </div>

      {requiredArtifacts !== null && (
        <div>
          <div style={ps.label}>Required artifacts</div>
          {requiredArtifacts.length === 0 ? (
            <div style={ps.artifactNone}>none</div>
          ) : (
            <ul style={ps.artifactList}>
              {requiredArtifacts.map((artifact) => (
                <li key={artifact} style={ps.artifactItem}>{artifact}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div>
        <div style={ps.label}>Outgoing transitions</div>
        {outgoing.length === 0 ? (
          <div style={ps.noAssigned}>None</div>
        ) : (
          <ul style={ps.outgoingList}>
            {outgoing.map((tgt) => (
              <li key={tgt} style={ps.outgoingItem}>
                <span style={ps.outgoingArrow}>→</span>
                <span style={ps.outgoingTarget}>{tgt}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {nodeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          <div style={ps.label}>Validation</div>
          {nodeIssues.map((issue, i) => (
            <div key={i} style={issue.level === 'error' ? ps.validationError : ps.validationWarning}>
              {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
