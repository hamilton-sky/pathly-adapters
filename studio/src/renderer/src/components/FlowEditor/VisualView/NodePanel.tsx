import { useEffect, useRef, useState, useId } from 'react'
import * as jsYaml from 'js-yaml'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'
import { useProjectFiles } from '../../../hooks/useProjectFiles'
import { readFile } from '../../../services/pathlyApi'
import type { SectionState, PathlyItem } from '../../../types'

function sectionAllItems(s: SectionState | undefined): PathlyItem[] {
  if (!s) return []
  return [
    ...(s.items ?? []),
    ...(s.subdirs ?? []).flatMap((sd) => sd.files ?? []),
  ]
}

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

interface BehaviorItem {
  name: string
  kind: 'skill' | 'agent'
}

export function NodePanel({ stateId, data, onAgentChange, onRename, onClose, onRemove, t, issues }: NodePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const { sections } = useProjectFiles()
  const renameInputId = useId()

  const currentAgent = data.agent_map[stateId] ?? ''

  // Inline rename state
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(stateId)
  const renameInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setRenameValue(stateId) }, [stateId])
  useEffect(() => { if (renaming) renameInputRef.current?.select() }, [renaming])

  function commitRename(): void {
    setRenaming(false)
    const newId = renameValue.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_')
    if (!newId || newId === stateId) { setRenameValue(stateId); return }
    if (data.states.includes(newId)) { setRenameValue(stateId); return }
    onRename?.(stateId, newId)
  }

  // Behavior list — merge core + user global + project-local, including subdirectory files
  const behaviors: BehaviorItem[] = [
    ...['Skills', 'UserSkills', 'My Skills'].flatMap((key) =>
      sectionAllItems(sections[key]).map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'skill' as const }))
    ),
    ...['Agents', 'UserAgents', 'My Agents'].flatMap((key) =>
      sectionAllItems(sections[key]).map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'agent' as const }))
    ),
  ].filter((b, i, arr) => arr.findIndex((x) => x.name === b.name) === i)

  const currentInLibrary = !currentAgent || behaviors.some((b) => b.name === currentAgent)
  const outgoing = data.transitions[stateId] ?? []

  // Required artifacts from assigned behavior frontmatter
  const [requiredArtifacts, setRequiredArtifacts] = useState<string[] | null>(null)

  useEffect(() => {
    setRequiredArtifacts(null)
    if (!currentAgent) return
    const allItems = [
      ...['Skills', 'UserSkills', 'My Skills'].flatMap((k) => sectionAllItems(sections[k])),
      ...['Agents', 'UserAgents', 'My Agents'].flatMap((k) => sectionAllItems(sections[k])),
    ]
    const item = allItems.find((i) => i.name.replace(/\.[^.]+$/, '') === currentAgent)
    if (!item) return
    readFile(item.path)
      .then((content) => {
        const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/)
        if (!fmMatch) return
        const fm = jsYaml.load(fmMatch[1]) as Record<string, unknown> | null
        if (!fm) return
        const artifacts = fm['required_artifacts']
        setRequiredArtifacts(Array.isArray(artifacts) && artifacts.length > 0 ? artifacts.map(String) : [])
      })
      .catch(() => { /* unreadable */ })
  }, [currentAgent, sections])

  // Inline search + keyboard nav
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const filtered = behaviors.filter((b) => b.name.toLowerCase().includes(query.toLowerCase()))

  useEffect(() => { setActiveIndex(0) }, [query])

  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const item = list.children[activeIndex] as HTMLElement | undefined
    item?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  function handleSearchKeyDown(e: React.KeyboardEvent): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[activeIndex]) {
      e.preventDefault()
      onAgentChange(stateId, filtered[activeIndex].name)
    }
  }

  const nodeIssues = issues?.filter((i) => i.target === 'node' && i.id === stateId) ?? []

  return (
    <div style={{ ...panelStyles.panel, overflowY: 'auto' }}>
      <PanelHeader title={stateId} onClose={onClose} t={t} />

      {/* Remove button */}
      <button
        onClick={onRemove}
        style={{
          width: '100%',
          padding: '5px 0',
          background: 'none',
          border: `1px solid ${t.red}`,
          borderRadius: 4,
          color: t.red,
          fontSize: 12,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        Remove from canvas
      </button>

      {/* Inline rename */}
      <div>
        <label htmlFor={renameInputId} style={panelStyles.label}>State ID</label>
        {renaming ? (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginTop: 4 }}>
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
              style={{ ...panelStyles.input, flex: 1, fontFamily: 'monospace', fontSize: 12 }}
            />
            <button
              onMouseDown={(e) => { e.preventDefault(); commitRename() }}
              style={{ ...panelStyles.addBtn, marginTop: 0, color: t.accent, borderColor: t.accent, padding: '3px 8px' }}
            >
              ✓
            </button>
          </div>
        ) : (
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, cursor: onRename ? 'text' : 'default' }}
            onClick={() => onRename && setRenaming(true)}
            title={onRename ? 'Click to rename' : undefined}
          >
            <span style={{ fontSize: '12px', color: t.textSecondary, fontFamily: 'monospace' }}>{stateId}</span>
            {onRename && <span style={{ fontSize: '10px', color: t.textMuted }}>✎</span>}
          </div>
        )}
      </div>

      {/* Behavior assignment — inline list + search */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={panelStyles.label}>Assigned behavior</div>

        {/* Current assignment chip */}
        {currentAgent ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              backgroundColor: t.bgSurface0,
              border: currentInLibrary ? `1px solid ${t.bgSurface1}` : `1px solid ${t.yellow}`,
              borderRadius: 12,
              fontSize: 12,
              padding: '3px 10px',
              color: t.textPrimary,
            }}>
              {!currentInLibrary && <span style={{ color: t.yellow, fontSize: 10 }} title="Not found in library">⚠</span>}
              {currentAgent}
            </span>
            <button
              onClick={() => onAgentChange(stateId, '')}
              title="Clear assignment"
              style={{ background: 'none', border: 'none', color: t.textMuted, cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: '0 2px' }}
            >
              ×
            </button>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: t.textMuted, fontStyle: 'italic' }}>None assigned</div>
        )}

        {/* Search input */}
        <input
          ref={searchRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          placeholder="Search behaviors…"
          style={{
            ...panelStyles.input,
            width: '100%',
            boxSizing: 'border-box',
          }}
        />

        {/* Behavior list — always visible */}
        <ul
          ref={listRef}
          role="listbox"
          aria-label="Available behaviors"
          style={{
            listStyle: 'none',
            margin: 0,
            padding: '2px 0',
            maxHeight: 180,
            overflowY: 'auto',
            border: `1px solid ${t.bgSurface1}`,
            borderRadius: 4,
            backgroundColor: t.bgSurface0,
          }}
        >
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
                  padding: '5px 10px',
                  fontSize: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  backgroundColor: isHighlighted ? t.bgSurface1 : 'transparent',
                  color: t.textPrimary,
                  borderLeft: isActive ? `2px solid ${t.accent}` : '2px solid transparent',
                }}
              >
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: b.kind === 'skill' ? t.green : t.blue,
                  minWidth: 34,
                  letterSpacing: '0.04em',
                }}>
                  {b.kind === 'skill' ? 'SKILL' : 'AGENT'}
                </span>
                <span style={{ flex: 1 }}>{b.name}</span>
                {isActive && <span style={{ color: t.accent, fontSize: 11 }}>✓</span>}
              </li>
            )
          })}
        </ul>
      </div>

      {/* Required artifacts */}
      {requiredArtifacts !== null && (
        <div>
          <div style={panelStyles.label}>Required artifacts</div>
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
        <div style={panelStyles.label}>Outgoing transitions</div>
        {outgoing.length === 0 ? (
          <div style={{ fontSize: 12, color: t.textMuted }}>None</div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {outgoing.map((target) => (
              <li key={target} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                <span style={{ color: t.textMuted }}>→</span>
                <span style={{ color: t.blue }}>{target}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Validation issues */}
      {nodeIssues.length > 0 && (
        <div role="alert" aria-live="polite">
          <div style={panelStyles.label}>Validation</div>
          {nodeIssues.map((issue, i) => (
            <div key={i} style={{ fontSize: 11, color: issue.level === 'error' ? t.red : t.yellow, padding: '3px 0' }}>
              {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
