import type React from 'react'
import { Plus } from 'lucide-react'
import type { ConvRow } from '../../types'
import { IconButton } from '../ui'
import { SectionHeader } from './SectionHeader'
import styles from './Sidebar.module.css'

function convStatusClass(status: string): string {
  if (status === 'DONE') return styles.statusDone
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return styles.statusActive
  if (status === 'BLOCKED') return styles.statusBlocked
  return styles.statusDefault
}

function convIcon(status: string): string {
  if (status === 'DONE') return '✓'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '●'
  return '○'
}

interface Props {
  planConvs: ConvRow[]
  open: boolean
  activeTopic: string | null
  onToggle: () => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
}

export function PlanSection({ planConvs, open, activeTopic, onToggle, onNewPlan, onActivePanel }: Props): JSX.Element {
  return (
    <>
      <SectionHeader
        label="Plan"
        open={open}
        onToggle={onToggle}
        sub={`[${activeTopic ?? 'no topic'}]`}
        actions={
          <IconButton onClick={onNewPlan} title="New plan">
            <Plus size={12} />
          </IconButton>
        }
      />
      {open && (
        <div>
          {planConvs.length === 0 ? (
            <div className={styles.convEmpty}>No conversations</div>
          ) : (
            planConvs.map((conv) => {
              const cls = convStatusClass(conv.status)
              return (
                <button key={conv.num} className={styles.convRow} onClick={() => onActivePanel('plan')}>
                  <span className={`${cls} ${styles.convStatus}`} style={{ marginRight: 6, flexShrink: 0 }}>
                    {convIcon(conv.status)}
                  </span>
                  <span className={styles.convLabel}>Conv {conv.num} — {conv.title}</span>
                  <span className={`${styles.convStatus} ${cls}`}>{conv.status}</span>
                </button>
              )
            })
          )}
        </div>
      )}
    </>
  )
}
