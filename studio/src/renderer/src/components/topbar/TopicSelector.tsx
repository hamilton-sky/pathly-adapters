import React, { useEffect, useRef, useState } from 'react'
import { ChevronDown, Check, FolderOpen } from 'lucide-react'
import { useStore } from '../../store'
import { listDirs } from '../../services/pathlyApi'
import styles from './TopicSelector.module.css'
import topBarStyles from './TopBar.module.css'

interface TopicSelectorProps {
  compact?: boolean
}

export function TopicSelector({ compact }: TopicSelectorProps): JSX.Element {
  const { projectPath, activeTopic, setActiveTopic } = useStore()
  const [activeTopics, setActiveTopics] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false
    async function loadTopics(): Promise<void> {
      try {
        const plansBase = projectPath + '/pathly/plans'
        const [planActive, debugTopics, exploreTopics] = await Promise.all([
          listDirs(plansBase).catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/debugs').catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/explorations').catch(() => [] as string[]),
        ])
        if (!cancelled) {
          const planNames = planActive.filter((e) => e !== '.archive')
          const extra = [...debugTopics, ...exploreTopics].filter((t) => !planNames.includes(t))
          setActiveTopics([...planNames, ...extra])
        }
      } catch { /* directory may not exist yet */ }
    }
    loadTopics()
    const interval = setInterval(loadTopics, 5000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [projectPath])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const selectValue = activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')

  if (compact) {
    return (
      <div
        className={topBarStyles.selectWrapCompact}
        title={activeTopic ?? 'Select topic'}
        aria-label="Active topic"
      >
        <FolderOpen size={14} />
        <select
          className={topBarStyles.topicSelectOverlay}
          aria-label="Active topic"
          value={selectValue}
          onChange={(e) => { setActiveTopic(e.target.value || null) }}
        >
          <option value="">— active topic —</option>
          {activeTopics.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
    )
  }

  const displayLabel = selectValue || '— active topic —'

  return (
    <div className={styles.wrap} ref={ref}>
      <button
        type="button"
        className={styles.trigger}
        aria-haspopup="listbox"
        aria-label="Active topic"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}
      >
        <FolderOpen size={13} />
        <span className={styles.triggerLabel}>{displayLabel}</span>
        <ChevronDown size={12} className={styles.chev} />
      </button>

      {open && (
        <div className={styles.menu} role="listbox" aria-label="Active topic">
          <button
            key="__clear__"
            type="button"
            role="option"
            aria-selected={!selectValue}
            className={styles.item}
            {...(!selectValue ? { 'data-active': '' } : {})}
            onClick={() => { setActiveTopic(null); setOpen(false) }}
          >
            <span className={styles.check}>{!selectValue && <Check size={12} />}</span>
            <span className={styles.itemLabel}>— active topic —</span>
          </button>

          {activeTopics.map((t) => (
            <button
              key={t}
              type="button"
              role="option"
              aria-selected={t === selectValue}
              className={styles.item}
              {...(t === selectValue ? { 'data-active': '' } : {})}
              onClick={() => { setActiveTopic(t); setOpen(false) }}
            >
              <span className={styles.check}>{t === selectValue && <Check size={12} />}</span>
              <span className={styles.itemLabel}>{t}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
