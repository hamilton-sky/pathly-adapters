import { useCallback, useEffect, useRef, useState } from 'react'
import type { Theme } from '../../../theme'
import type { FlowYaml } from '../../../types'
import type { FlowValidationIssue } from '../utils/validateFlow'
import { makePanelStyles } from '../shared/panelStyles'
import { PanelHeader } from '../shared/PanelHeader'
import { Z } from '../zIndex'
import { useProjectFiles } from '../../../hooks/useProjectFiles'

interface NodePanelProps {
  stateId: string
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onAddRule: (source: string) => void
  onClose: () => void
  t: Theme
  issues?: FlowValidationIssue[]
}

interface BehaviorItem {
  name: string
  kind: 'skill' | 'agent'
}

export function NodePanel({ stateId, data, onAgentChange, onClose, t, issues }: NodePanelProps): JSX.Element {
  const panelStyles = makePanelStyles(t)
  const { sections } = useProjectFiles()

  const currentAgent = data.agent_map[stateId] ?? ''

  // Build behavior list from skills + agents
  const behaviors: BehaviorItem[] = [
    ...sections.Skills.items.map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'skill' as const })),
    ...sections.Agents.items.map((item) => ({ name: item.name.replace(/\.[^.]+$/, ''), kind: 'agent' as const })),
  ]

  // Outgoing transitions for this state
  const outgoing = data.transitions[stateId] ?? []

  // Popover state
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)

  const triggerRef = useRef<HTMLButtonElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const filtered = behaviors.filter((b) =>
    b.name.toLowerCase().includes(query.toLowerCase())
  )

  // Missing-on-disk check
  const currentInLibrary = !currentAgent || behaviors.some((b) => b.name === currentAgent)

  function openPopover(): void {
    setQuery('')
    setActiveIndex(0)
    setPopoverOpen(true)
  }

  function closePopover(): void {
    setPopoverOpen(false)
    triggerRef.current?.focus()
  }

  function selectBehavior(name: string): void {
    onAgentChange(stateId, name)
    closePopover()
  }

  // Focus search input when popover opens
  useEffect(() => {
    if (popoverOpen) {
      searchRef.current?.focus()
    }
  }, [popoverOpen])

  // Reset active index when filtered list changes
  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  const handlePopoverKeyDown = useCallback((e: React.KeyboardEvent): void => {
    if (e.key === 'Escape') {
      e.preventDefault()
      closePopover()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter' && filtered[activeIndex]) {
      e.preventDefault()
      selectBehavior(filtered[activeIndex].name)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, activeIndex])

  // Scroll active item into view
  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const item = list.children[activeIndex] as HTMLElement | undefined
    item?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  const nodeIssues = issues?.filter((i) => i.scope === 'node' && i.key === stateId) ?? []

  return (
    <div style={panelStyles.panel}>
      <PanelHeader title={stateId} onClose={onClose} t={t} />

      {/* Identity — read-only */}
      <div>
        <div style={panelStyles.label}>State ID</div>
        <div style={{ fontSize: '12px', color: t.textSecondary, padding: '4px 0' }}>
          {stateId}
        </div>
        <div style={{ fontSize: '11px', color: t.textMuted, fontStyle: 'italic' }}>
          Rename in YAML view for now.
        </div>
      </div>

      {/* Assigned behavior */}
      <div style={{ position: 'relative' }}>
        <div style={panelStyles.label}>Assigned behavior</div>
        <button
          ref={triggerRef}
          onClick={openPopover}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: t.bgSurface0,
            border: currentInLibrary ? t.border : `1px solid ${t.yellow}`,
            borderRadius: '12px',
            color: currentAgent ? t.textPrimary : t.textMuted,
            cursor: 'pointer',
            fontSize: '12px',
            padding: '4px 10px',
            marginTop: '4px'
          }}
        >
          {currentAgent || 'Assign behavior…'}
          {!currentInLibrary && (
            <span style={{ color: t.yellow, fontSize: '10px' }} title="Not found in library">⚠</span>
          )}
        </button>

        {popoverOpen && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              zIndex: Z.popover,
              backgroundColor: t.bgSurface0,
              border: t.border,
              borderRadius: '6px',
              width: '260px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
              overflow: 'hidden',
              marginTop: '4px'
            }}
            onKeyDown={handlePopoverKeyDown}
          >
            <div style={{ padding: '6px 8px', borderBottom: `1px solid ${t.bgSurface1}` }}>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search behaviors…"
                style={{
                  width: '100%',
                  backgroundColor: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: t.textPrimary,
                  fontSize: '12px'
                }}
              />
            </div>
            <ul
              ref={listRef}
              role="listbox"
              style={{
                listStyle: 'none',
                margin: 0,
                padding: '4px 0',
                maxHeight: '200px',
                overflowY: 'auto'
              }}
            >
              {filtered.length === 0 && (
                <li style={{ padding: '8px 12px', fontSize: '12px', color: t.textMuted }}>
                  No matches
                </li>
              )}
              {filtered.map((b, idx) => (
                <li
                  key={b.name}
                  role="option"
                  aria-selected={idx === activeIndex}
                  onClick={() => selectBehavior(b.name)}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: idx === activeIndex ? t.bgSurface1 : 'transparent',
                    color: t.textPrimary
                  }}
                >
                  <span style={{ fontSize: '10px', color: b.kind === 'skill' ? t.green : t.blue }}>
                    {b.kind === 'skill' ? 'SKILL' : 'AGENT'}
                  </span>
                  {b.name}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Transition summary */}
      <div>
        <div style={panelStyles.label}>Outgoing transitions</div>
        {outgoing.length === 0 ? (
          <div style={{ fontSize: '12px', color: t.textMuted, padding: '4px 0' }}>None</div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: '4px 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {outgoing.map((target) => (
              <li
                key={target}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
              >
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
            <div
              key={i}
              style={{
                fontSize: '11px',
                color: issue.severity === 'error' ? t.red : t.yellow,
                padding: '3px 0'
              }}
            >
              {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
