import React, { useEffect, useState } from 'react'
import { FolderOpen } from 'lucide-react'
import { useStore } from '../../store'
import { listDirs } from '../../services/pathlyApi'
import styles from './TopBar.module.css'

interface TopicSelectorProps {
  compact?: boolean
}

export function TopicSelector({ compact }: TopicSelectorProps): JSX.Element {
  const { projectPath, activeTopic, setActiveTopic } = useStore()
  const [activeTopics, setActiveTopics] = useState<string[]>([])

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

  const selectValue = activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')

  if (compact) {
    return (
      <div
        className={styles.selectWrapCompact}
        title={activeTopic ?? 'Select topic'}
        aria-label="Active topic"
      >
        <FolderOpen size={14} />
        <select
          className={styles.topicSelectOverlay}
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

  return (
    <div className={styles.selectWrap}>
      <select
        className={styles.topicSelect}
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
