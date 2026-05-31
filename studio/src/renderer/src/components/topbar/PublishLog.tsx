import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useStore } from '../../store'
import { IconButton } from '../ui'
import styles from './TopBar.module.css'

interface Props {
  onClose: () => void
}

export function PublishLog({ onClose }: Props): JSX.Element {
  const { publishLog } = useStore()
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [publishLog])

  return (
    <div className={styles.logPanel}>
      <div className={styles.logHeader}>
        <span>Publish output</span>
        <IconButton onClick={onClose} title="Close publish log">
          <X size={12} />
        </IconButton>
      </div>
      <div className={styles.logBody}>
        {publishLog.map((line, i) => <div key={i} className={styles.logLine}>{line}</div>)}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
