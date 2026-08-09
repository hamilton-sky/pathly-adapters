import { type KeyboardEvent } from 'react'
import { Palette, Rocket, Bot, BrainCircuit, SlidersHorizontal, type LucideIcon } from 'lucide-react'
import s from './SettingsNav.module.css'

export type SettingsGroup = 'appearance' | 'runs' | 'agents' | 'intelligence' | 'system'

const ITEMS: { id: SettingsGroup; label: string; Icon: LucideIcon }[] = [
  { id: 'appearance', label: 'Appearance', Icon: Palette },
  { id: 'runs', label: 'Runs', Icon: Rocket },
  { id: 'agents', label: 'Agents', Icon: Bot },
  { id: 'intelligence', label: 'Intelligence', Icon: BrainCircuit },
  { id: 'system', label: 'System', Icon: SlidersHorizontal },
]

interface Props {
  active: SettingsGroup
  onSelect: (g: SettingsGroup) => void
}

// Left rail — the ARIA vertical tabs pattern: roving tabIndex (only the active tab is
// tabbable), Arrow Up/Down moves + activates. The content panel is the matching tabpanel.
export function SettingsNav({ active, onSelect }: Props): JSX.Element {
  function onKeyDown(e: KeyboardEvent): void {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    e.preventDefault()
    const idx = ITEMS.findIndex((i) => i.id === active)
    const delta = e.key === 'ArrowDown' ? 1 : -1
    onSelect(ITEMS[(idx + delta + ITEMS.length) % ITEMS.length].id)
  }

  return (
    <nav className={s.rail} role="tablist" aria-label="Settings sections" aria-orientation="vertical">
      {ITEMS.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          role="tab"
          id={`settings-tab-${id}`}
          aria-controls="settings-content-panel"
          aria-selected={active === id ? 'true' : 'false'}
          tabIndex={active === id ? 0 : -1}
          className={s.item}
          {...(active === id ? { 'data-active': '' } : {})}
          onClick={() => onSelect(id)}
          onKeyDown={onKeyDown}
        >
          <Icon size={15} aria-hidden="true" />
          <span className={s.label}>{label}</span>
        </button>
      ))}
    </nav>
  )
}
