import React, { useRef, useState } from 'react'
import { useStore } from '../../store'
import { upgrade, onPublishOutput } from '../../services/pathlyApi'
import { Tooltip } from '../ui'
import styles from './TopBar.module.css'

interface Props {
  onShowLog: () => void
}

export function PublishControl({ onShowLog }: Props): JSX.Element {
  const { publishing, setPublishing, appendPublishLog, clearPublishLog } = useStore()
  const removeListenerRef = useRef<(() => void) | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleUpgrade(): Promise<void> {
    clearPublishLog()
    setError(null)
    onShowLog()
    setPublishing(true)
    if (removeListenerRef.current) removeListenerRef.current()
    removeListenerRef.current = onPublishOutput((line) => appendPublishLog(line))
    try {
      await upgrade()
    } catch (err) {
      setError(String(err))
      appendPublishLog(`Error: ${String(err)}`)
    } finally {
      setPublishing(false)
      removeListenerRef.current?.()
      removeListenerRef.current = null
    }
  }

  return (
    <Tooltip label={error ?? 'Install latest Pathly update from PyPI'} placement="bottom">
      <button type="button" className={styles.publishBtn} onClick={() => void handleUpgrade()} disabled={publishing}>
        {publishing ? '…' : error ? 'Retry' : 'Update'}
      </button>
    </Tooltip>
  )
}
