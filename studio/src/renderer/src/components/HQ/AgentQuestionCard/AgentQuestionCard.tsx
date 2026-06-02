import type { AgentQuestion } from '../../../store/runnerStore'
import styles from './AgentQuestionCard.module.css'

interface AgentQuestionCardProps {
  question: AgentQuestion
  onAnswer: (answer: string) => void
}

export function AgentQuestionCard({ question, onAnswer }: AgentQuestionCardProps): JSX.Element {
  return (
    <div className={styles.card} role="group" aria-label="Agent question">
      <div className={styles.header}>
        <span className={styles.icon}>?</span>
        <span className={styles.title}>Agent question</span>
      </div>
      <p className={styles.question}>{question.question}</p>
      <div className={styles.options}>
        {question.options.map((opt) => (
          <button
            type="button"
            key={opt.label}
            className={styles.option}
            onClick={() => onAnswer(opt.label)}
          >
            <span className={styles.optLabel}>{opt.label}</span>
            {opt.description && (
              <span className={styles.optDesc}>{opt.description}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
