import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import type { SkillCompositionEntry } from '../../../services/skillComposition'
import { IconButton } from '../../ui'
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
 * The left skill picker with a collapse banner. Expanded: a "Skills" banner (collapse
 * control) over the grouped `SkillList`. Collapsed: a thin rail with an expand control and a
 * vertical label, so the fragment panel gets the full width.
 */
export function SkillSidebar({
  skills,
  selectedSkill,
  onSelect,
  loading,
  collapsed,
  onToggleCollapse,
}: Props): JSX.Element {
  if (collapsed) {
    return (
      <div className={styles.rail}>
        <IconButton
          title="Expand skills"
          onClick={onToggleCollapse}
          aria-expanded="false"
        >
          <PanelLeftOpen size={16} />
        </IconButton>
        <span className={styles.railLabel}>Skills</span>
      </div>
    )
  }

  return (
    <div className={styles.sidebar}>
      <div className={styles.banner}>
        <span className={styles.bannerLabel}>Skills</span>
        <span className={styles.spacer} />
        <IconButton
          title="Collapse skills"
          onClick={onToggleCollapse}
          aria-expanded="true"
        >
          <PanelLeftClose size={16} />
        </IconButton>
      </div>
      <SkillList skills={skills} selectedSkill={selectedSkill} onSelect={onSelect} loading={loading} />
    </div>
  )
}
