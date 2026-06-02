import { ChevronDown, ChevronUp } from 'lucide-react'
import { useUiStore } from '../../../store/uiStore'
import styles from './SkillsPanel.module.css'

const PIPELINE_SKILLS = ['plan', 'po', 'storm', 'build', 'review', 'test', 'retro', 'explore', 'debug', 'design', 'fix', 'quick-fix', 'status', 'log', 'end'] as const
const CONTROL_SKILLS  = ['start', 'go', 'pause', 'ff', 'help', 'team', 'end'] as const

interface SkillsPanelProps {
  onSkillClick: (command: string) => void
}

export function SkillsPanel({ onSkillClick }: SkillsPanelProps): JSX.Element {
  const skillsPanelOpen = useUiStore((s) => s.skillsPanelOpen)
  const toggleSkillsPanel = useUiStore((s) => s.toggleSkillsPanel)

  return (
    <div className={styles.panel}>
      <button
        type="button"
        className={styles.header}
        onClick={toggleSkillsPanel}
        {...(skillsPanelOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <span className={styles.title}>/pathly</span>
        {skillsPanelOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      <div className={skillsPanelOpen ? styles.chips : styles.chipsCompact}>
        {CONTROL_SKILLS.map((skill) => (
          <button type="button" key={skill} className={styles.chip} onClick={() => onSkillClick(`/pathly ${skill}`)}>
            {skill}
          </button>
        ))}
      </div>

      {skillsPanelOpen && (
        <>
          <div className={styles.sectionLabel}>Pipeline</div>
          <div className={styles.chips}>
            {PIPELINE_SKILLS.map((skill) => (
              <button type="button" key={skill} className={styles.chip} onClick={() => onSkillClick(`/pathly ${skill}`)}>
                {skill}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
