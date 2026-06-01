import { useState, useEffect } from 'react'
import type { DecisionMenuItem } from '../../../store/runnerStore'
import styles from './PathlyMenuCard.module.css'

interface DecisionButtonProps {
  item: DecisionMenuItem
  onError: (msg: string) => void
  onDone: () => void
}

export function DecisionButton({ item, onError, onDone }: DecisionButtonProps): JSX.Element {
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
    try {
      const res = await fetch('http://127.0.0.1:8765/runner/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ choice: item.id }),
      })
      if (res.ok) {
        onDone()
      } else {
        setDisabled(false)
        onError(`decision failed: ${res.status}`)
      }
    } catch {
      setDisabled(false)
      onError('decision failed: network error')
    }
  }

  return (
    <button
      type="button"
      className={`${styles.decisionBtn} ${disabled ? styles.decisionBtnDisabled : ''}`}
      aria-label={item.label}
      aria-disabled={disabled}
      disabled={disabled}
      onClick={() => { void handleClick() }}
    >
      {displayText}
    </button>
  )
}
