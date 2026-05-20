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
    <div style={{ ...ps.panel, overflowY: 'auto' }}>
      <PanelHeader title={stateId} onClose={onClose} t={t} />

      {/* Remove button */}
      <button onClick={onRemove} style={ps.dangerBtn}>
        Remove from canvas
      </button>

      {/* Inline rename */}
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
              style={{ ...ps.input, flex: 1, fontFamily: 'monospace', fontSize: 12 }}
            />
            <button onMouseDown={(e) => { e.preventDefault(); commitRename() }} style={ps.renameConfirmBtn}>
              ✓
            </button>
          </div>
        ) : (
          <div
            style={{ ...ps.stateIdDisplay, cursor: onRename ? 'text' : 'default' }}
            onClick={() => onRename && setRenaming(true)}
            title={onRename ? 'Click to rename' : undefined}
          >
            <span style={ps.stateIdText}>{stateId}</span>
            {onRename && <span style={ps.editHint}>✎</span>}
          </div>
        )}
      </div>

      {/* Behavior assignment */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={ps.label}>Assigned behavior</div>

        {currentAgent ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
          style={{ ...ps.input, width: '100%', boxSizing: 'border-box' }}
        />

        <ul ref={listRef} role="listbox" aria-label="Available behaviors" style={ps.behaviorList}>
          {filtered.length === 0 && (
            <li style={{ padding: '8px 10px', fontSize: 12, color: t.textMuted }}>No matches</li>
          )}
          {filtered.map((b, idx) => {
            const isActive = b.name === currentAgent
            const isHighlighted = idx === activeIndex
            return (
              <li
                key={b.name}
                role="option"
                aria-selected={isActive}
                onClick={() => onAgentChange(stateId, b.name)}
                style={{
                  ...(isHighlighted ? ps.behaviorItemHighlighted : ps.behaviorItemDefault),
                  borderLeft: isActive ? `2px solid ${t.accent}` : '2px solid transparent',
                }}
              >
                <span style={b.kind === 'skill' ? ps.behaviorKindBadgeSkill : ps.behaviorKindBadgeAgent}>
                  {b.kind === 'skill' ? 'SKILL' : 'AGENT'}
                </span>
                <span style={{ flex: 1 }}>{b.name}</span>
                {isActive && <span style={ps.behaviorCheckmark}>✓</span>}
              </li>
            )
          })}
        </ul>
      </div>

      {/* Required artifacts */}
      {requiredArtifacts !== null && (
        <div>
          <div style={ps.label}>Required artifacts</div>
          {requiredArtifacts.length === 0 ? (
            <div style={{ fontSize: 12, color: t.textMuted, fontStyle: 'italic' }}>none</div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {requiredArtifacts.map((artifact) => (
                <li key={artifact} style={{ fontSize: 12, color: t.textSecondary }}>{artifact}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Outgoing transitions */}
      <div>
        <div style={ps.label}>Outgoing transitions</div>
        {outgoing.length === 0 ? (
          <div style={{ fontSize: 12, color: t.textMuted }}>None</div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {outgoing.map((tgt) => (
              <li key={tgt} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                <span style={{ color: t.textMuted }}>→</span>
                <span style={{ color: t.blue }}>{tgt}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Validation issues */}
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
