import React, { useRef } from 'react'
import { useStore } from '../../store'
import { publish, onPublishOutput } from '../../services/pathlyApi'
import { Tooltip } from '../ui'
import styles from './TopBar.module.css'

interface Props {
  onShowLog: () => void
}

export function PublishControl({ onShowLog }: Props): JSX.Element {
  const { projectPath, publishing, setPublishing, appendPublishLog, clearPublishLog } = useStore()
  const removeListenerRef = useRef<(() => void) | null>(null)

  async function handlePublish(): Promise<void> {
    clearPublishLog()
    onShowLog()
    setPublishing(true)
    if (removeListenerRef.current) removeListenerRef.current()
    removeListenerRef.current = onPublishOutput((line) => appendPublishLog(line))
    try {
      await publish(projectPath)
    } finally {
      setPublishing(false)
      removeListenerRef.current?.()
      removeListenerRef.current = null
    }
  }

  return (
    <Tooltip label="Push hooks to server" placement="bottom">
      <button className={styles.publishBtn} onClick={() => void handlePublish()} disabled={publishing}>
        {publishing ? '…' : 'Publish'}
      </button>
    </Tooltip>
  )
}
