import type { SkillCompositionEntry } from '../integration'
import { SkillList } from '../SkillList/SkillList'
import styles from './SkillSidebar.module.css'

interface Props {
  skills: Record<string, SkillCompositionEntry>
  selectedSkill: string | null
  onSelect: (skill: string) => void
  loading: boolean
  collapsed: boolean
  onToggleCollapse: () => void
}

/**
 * Left skill picker that swaps between two states:
 *  - expanded: a "Skills" banner (with collapse control) over the grouped SkillList
 *  - collapsed: a thin rail with an expand control + vertical label, giving the panel full width.
 */
export function SkillSidebar({
  skills, selectedSkill, onSelect, loading, collapsed, onToggleCollapse,
}: Props): JSX.Element {
  if (collapsed) {
    return (
      <div className={styles.rail}>
        <button type="button" className={styles.iconBtn} title="Expand skills" aria-expanded="false" onClick={onToggleCollapse}>
          <PanelOpen />
        </button>
        <span className={styles.railLabel}>Skills</span>
      </div>
    )
  }
  return (
    <div className={styles.sidebar}>
      <div className={styles.banner}>
        <span className={styles.bannerLabel}>Skills</span>
        <span className={styles.spacer} />
        <span className={styles.count}>{Object.keys(skills).length}</span>
        <button type="button" className={styles.iconBtn} title="Collapse skills" aria-expanded="true" onClick={onToggleCollapse}>
          <PanelClose />
        </button>
      </div>
      <SkillList skills={skills} selectedSkill={selectedSkill} onSelect={onSelect} loading={loading} />
    </div>
  )
}

/* Inline lucide-style glyphs (panel-left). Swap for lucide-react in the app if preferred. */
function PanelClose(): JSX.Element {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" /><path d="m16 15-3-3 3-3" />
    </svg>
  )
}
function PanelOpen(): JSX.Element {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" /><path d="m14 9 3 3-3 3" />
    </svg>
  )
}
