import { ChevronDown, ChevronUp } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import { useTheme } from '../../useTheme'
import styles from './SkillsPanel.module.css'

const PIPELINE_SKILLS = ['plan', 'po', 'storm', 'build', 'review', 'test', 'retro', 'explore', 'debug', 'design', 'fix', 'status', 'log', 'end'] as const
const CONTROL_SKILLS  = ['start', 'go', 'pause', 'ff', 'help', 'team', 'end'] as const

interface SkillsPanelProps {
  onSkillClick: (command: string) => void
}

export function SkillsPanel({ onSkillClick }: SkillsPanelProps): JSX.Element {
  const skillsPanelOpen = useUiStore((s) => s.skillsPanelOpen)
  const toggleSkillsPanel = useUiStore((s) => s.toggleSkillsPanel)
  const t = useTheme()

  return (
    <div
      className={styles.panel}
      style={{ borderBottom: t.border, background: t.bgSurface0 }}
    >
      <button
        className={styles.header}
        onClick={toggleSkillsPanel}
        aria-expanded={skillsPanelOpen}
        style={{ color: t.textSecondary, fontFamily: t.fontFamilyBase }}
      >
        <span className={styles.title} style={{ color: t.textPrimary }}>Skills</span>
        {skillsPanelOpen
          ? <ChevronUp size={13} />
          : <ChevronDown size={13} />
        }
      </button>

      {skillsPanelOpen && (
        <div className={styles.sections}>
          {/* Pipeline skills */}
          <div className={styles.sectionLabel} style={{ color: t.textMuted, fontFamily: t.fontFamilyBase }}>
            Pipeline
          </div>
          <div className={styles.chips}>
            {PIPELINE_SKILLS.map((skill) => (
              <button
                key={skill}
                className={styles.chip}
                onClick={() => onSkillClick(`/pathly ${skill}`)}
                style={{
                  background: t.bgSurface1,
                  color: t.textSecondary,
                  fontFamily: t.fontFamilyMono,
                  border: `1px solid ${t.bgSurface1}`,
                }}
              >
                {skill}
              </button>
            ))}
          </div>

          {/* Control commands */}
          <div className={styles.sectionLabel} style={{ color: t.textMuted, fontFamily: t.fontFamilyBase }}>
            Control
          </div>
          <div className={styles.chips}>
            {CONTROL_SKILLS.map((skill) => (
              <button
                key={skill}
                className={styles.chip}
                onClick={() => onSkillClick(`/pathly ${skill}`)}
                style={{
                  background: t.bgSurface1,
                  color: t.textSecondary,
                  fontFamily: t.fontFamilyMono,
                  border: `1px solid ${t.bgSurface1}`,
                }}
              >
                {skill}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
