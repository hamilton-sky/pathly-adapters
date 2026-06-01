import { useState, useEffect } from 'react'
import type { DecisionMenuItem } from '../../../store/runnerStore'
import { useRunnerStore } from '../../../store/runnerStore'
import styles from './PathlyMenuCard.module.css'

interface DecisionButtonProps {
  item: DecisionMenuItem
  onError: (msg: string) => void
  onDone: () => void
  onRevert: () => void
}

export function DecisionButton({ item, onError, onDone, onRevert }: DecisionButtonProps): JSX.Element {
  const [disabled, setDisabled] = useState(false)
  const [displayText, setDisplayText] = useState('')

  useEffect(() => {
    let idx = 0
    const interval = setInterval(() => {
      idx += 1
      setDisplayText(item.label.slice(0, idx))
      if (idx >= item.label.length) clearInterval(interval)
    }, 20)
    return () => clearInterval(interval)
  }, [item.label])

  async function handleClick(): Promise<void> {
    setDisabled(true)
    onDone()
    const { topic } = useRunnerStore.getState()
    try {
      const res = await fetch('http://127.0.0.1:8765/runner/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, decision: item.id }),
      })
      if (!res.ok) {
        onRevert()
        setDisabled(false)
        onError(`decision failed: ${res.status}`)
      }
    } catch {
      onRevert()
      setDisabled(false)
      onError('decision failed: network error')
    }
  }

  return (
    <button
      type="button"
      className={`${styles.decisionBtn} ${disabled ? styles.decisionBtnDisabled : ''}`}
      aria-label={item.label}
      disabled={disabled}
      {...(disabled ? { 'aria-disabled': 'true' } : { 'aria-disabled': 'false' })}
      onClick={() => { void handleClick() }}
    >
      {displayText}
    </button>
  )
}
