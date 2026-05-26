import { useTheme } from '../../useTheme'
import styles from './MatchCard.module.css'

export interface MatchResult {
  skill: string
  confidence: number
  command: string
}

interface MatchCardProps {
  match: MatchResult
  alts: MatchResult[]
  onRun: () => void
  onReject: () => void
  onSelectAlt: (skill: string) => void
}

export function MatchCard({ match, alts, onRun, onReject, onSelectAlt }: MatchCardProps): JSX.Element {
  const t = useTheme()
  const matched = match.confidence >= 0.65
  const pct = Math.round(match.confidence * 100)

  return (
    <div
      className={`${styles.card} ${matched ? styles.cardMatched : styles.cardUnsure}`}
      style={{ background: t.bgSurface0, color: t.textPrimary }}
    >
      <div className={styles.header}>
        <span className={styles.skillName} style={{ color: t.textPrimary }}>
          {match.skill}
        </span>
        <span className={`${styles.badge} ${matched ? styles.badgeMatched : styles.badgeUnsure}`}>
          {matched ? '✓ MATCHED' : '~ UNSURE'}
        </span>
      </div>

      <div className={styles.confidence}>{pct}% confidence</div>

      <div className={styles.barTrack}>
        <div
          className={`${styles.barFill} ${matched ? styles.barFillMatched : styles.barFillUnsure}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className={styles.actions}>
        <button className={styles.btnRun} onClick={onRun}>
          Run
        </button>
        <button
          className={styles.btnReject}
          style={{ color: t.textPrimary, borderColor: t.borderSubtle }}
          onClick={onReject}
        >
          Not this
        </button>
      </div>

      {alts.length > 0 && (
        <div className={styles.alts}>
          <span className={styles.altLabel}>Try instead:</span>
          {alts.map((a) => (
            <span key={a.skill} className={styles.altChip} onClick={() => onSelectAlt(a.skill)}>
              {a.skill}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
