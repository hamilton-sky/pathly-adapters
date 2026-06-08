import { useEffect, useRef } from 'react'
import type { DotSegment } from './dbExplorerData'
import styles from './StageDots.module.css'

interface StageDotsProps {
  dots: DotSegment[]
  compact?: boolean
}

export function StageDots({ dots, compact }: StageDotsProps): JSX.Element {
  const refs = useRef<(HTMLSpanElement | null)[]>([])

  useEffect(() => {
    dots.forEach((dot, i) => {
      const el = refs.current[i]
      if (el) {
        el.style.setProperty('--seg-flex', (dot.flex ?? 1).toString())
      }
    })
  }, [dots])

  return (
    <div className={`${styles.dots} ${compact ? styles.compact : ''}`}>
      {dots.map((dot, i) => (
        <span
          key={i}
          ref={(el) => { refs.current[i] = el }}
          className={styles.segment}
          data-state={dot.state}
        />
      ))}
    </div>
  )
}
