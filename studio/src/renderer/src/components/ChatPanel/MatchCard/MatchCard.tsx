import type { MatchResult } from '../../../types/chat'
import styles from './MatchCard.module.css'

interface MatchCardProps {
  match: MatchResult
  alts: MatchResult[]
  onRun: () => void
  onReject: () => void
  onSelectAlt: (skill: string) => void
}

export function MatchCard({ match, alts, onRun, onReject, onSelectAlt }: MatchCardProps): JSX.Element {
  const matched = match.confidence >= 0.65
  const pct = Math.round(match.confidence * 100)

  return (
    <div className={`${styles.card} ${matched ? styles.cardMatched : styles.cardUnsure}`}>
      <div className={styles.header}>
        <span className={styles.skillName}>
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
        <button type="button" className={styles.btnRun} onClick={onRun} aria-label={`Run ${match.skill}`}>
          Run
        </button>
        <button
          type="button"
          className={styles.btnReject}
          onClick={onReject}
        >
          Not this
        </button>
      </div>

      {alts.length > 0 && (
        <div className={styles.alts}>
          <span className={styles.altLabel}>Try instead:</span>
          {alts.map((a) => (
            <button
              key={a.skill}
              type="button"
              className={styles.altChip}
              aria-label={`Select ${a.skill}`}
              onClick={() => onSelectAlt(a.skill)}
            >
              {a.skill}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
