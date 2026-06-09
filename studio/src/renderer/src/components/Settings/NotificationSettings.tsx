import React from 'react'
import { useNotificationStore } from '../../store/notificationStore'
import type { NotifCategory, ToastPosition, ToastStyle } from '../../store/notificationStore'
import { RadioCard } from './RadioCard'
import s from './NotificationSettings.module.css'
import ss from './Settings.module.css'

const COLOR_SWATCHES = ['#4ade80', '#60a5fa', '#c084fc', '#f472b6', '#fb923c', '#fbbf24', '#94a3b8', '#f87171']

const POSITIONS: Array<{ value: ToastPosition; label: string }> = [
  { value: 'bottom-right', label: '↙ Bottom right' },
  { value: 'bottom-left',  label: '↘ Bottom left' },
  { value: 'top-right',    label: '↖ Top right' },
  { value: 'top-left',     label: '↗ Top left' },
]

const CATEGORIES: Array<{ key: NotifCategory; label: string; description: string; alwaysOn?: boolean }> = [
  { key: 'db_crud',       label: 'Database operations', description: 'Skill saves, catalog create / delete / rename', alwaysOn: true },
  { key: 'runner_state',  label: 'Runner state',         description: 'Run started, completed, aborted, warnings' },
  { key: 'phase_changes', label: 'Phase changes',        description: 'Stage transitions (BUILDING → REVIEWING)' },
  { key: 'events_log',    label: 'Event log entries',    description: 'Individual EVENTS.jsonl entries (high volume)' },
  { key: 'agent_done',    label: 'Agent done',           description: 'Agent completes a pipeline stage' },
]

export function NotificationSettings(): JSX.Element {
  const position = useNotificationStore((s) => s.position)
  const style = useNotificationStore((s) => s.style)
  const categories = useNotificationStore((s) => s.categories)
  const setPosition = useNotificationStore((s) => s.setPosition)
  const setStyle = useNotificationStore((s) => s.setStyle)
  const setCategoryEnabled = useNotificationStore((s) => s.setCategoryEnabled)
  const setCategoryColor = useNotificationStore((s) => s.setCategoryColor)

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Notifications</div>

      <div className={s.subLabel}>Position</div>
      <div className={s.positionRow}>
        {POSITIONS.map((p) => (
          <button
            key={p.value}
            type="button"
            className={`${s.posBtn} ${position === p.value ? s.posBtnActive : ''}`}
            onClick={() => setPosition(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className={s.subLabel}>Style</div>
      <div className={ss.radioGroup}>
        <RadioCard active={style === 'default'} label="Default" description="Border accent" onClick={() => setStyle('default')} />
        <RadioCard active={style === 'card'}    label="Card"    description="Elevated border" onClick={() => setStyle('card')} />
        <RadioCard active={style === 'minimal'} label="Minimal" description="Glass effect"   onClick={() => setStyle('minimal')} />
        <RadioCard active={style === 'banner'}  label="Banner"  description="Full-width strip" onClick={() => setStyle('banner')} />
      </div>

      <div className={s.subLabel}>Event categories</div>
      <div className={s.categoryList}>
        {CATEGORIES.map((cat) => {
          const prefs = categories[cat.key]
          return (
            <div key={cat.key} className={s.categoryRow}>
              <div className={s.categoryLeft}>
                {cat.alwaysOn ? (
                  <span className={s.alwaysBadge}>Always</span>
                ) : (
                  <button
                    type="button"
                    className={`${s.toggle} ${prefs.enabled ? s.toggleOn : ''}`}
                    onClick={() => setCategoryEnabled(cat.key, !prefs.enabled)}
                    aria-label={prefs.enabled ? 'Disable' : 'Enable'}
                  />
                )}
                <div className={s.categoryText}>
                  <span className={s.categoryLabel}>{cat.label}</span>
                  <span className={s.categoryDesc}>{cat.description}</span>
                </div>
              </div>
              <div className={s.swatches}>
                {COLOR_SWATCHES.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`${s.swatch} ${prefs.color === c ? s.swatchActive : ''}`}
                    style={{ '--swatch-color': c } as React.CSSProperties}
                    onClick={() => setCategoryColor(cat.key, c)}
                    aria-label={`Set color ${c}`}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
