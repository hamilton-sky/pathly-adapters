import React from 'react'
import { SendHorizonal } from 'lucide-react'
import { useTerminalStore } from '../../../store/terminalStore'
import type { Comment } from '../useComments'
import { buildSendPrompt, getSpawnCwd } from '../commentUtils'
import { CommentItem } from './CommentItem/CommentItem'
import styles from './CommentsPanel.module.css'

interface Props {
  filePath: string
  body: string
  comments: Comment[]
  onResolve: (id: string) => void
  onRemove: (id: string) => void
}

export function CommentsPanel({ filePath, body, comments, onResolve, onRemove }: Props): JSX.Element {
  const addTab = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)

  const unresolved = comments.filter((c) => !c.resolved)
  const resolved = comments.filter((c) => c.resolved)

  async function handleSendToAgent(): Promise<void> {
    if (!unresolved.length) return
    const norm = filePath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'file'
    const cwd = getSpawnCwd(filePath)
    const prompt = buildSendPrompt(filePath, body, unresolved)
    const tabId = `review-${Date.now().toString(36)}`
    addTab(tabId, `Review · ${fileName}`)
    openTab(tabId)
    await window.pathly.terminal.spawn(tabId, cwd, undefined, [
      'claude', '-p', prompt, '--print', '--dangerously-skip-permissions',
    ])
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>
          Comments
          {unresolved.length > 0 && <span className={styles.badge}>{unresolved.length}</span>}
        </span>
      </div>

      <div className={styles.list}>
        {comments.length === 0 && (
          <p className={styles.empty}>Select text in the preview to add a comment</p>
        )}
        {unresolved.map((c) => (
          <CommentItem key={c.id} comment={c} onResolve={onResolve} onRemove={onRemove} />
        ))}
        {resolved.length > 0 && (
          <>
            <p className={styles.resolvedLabel}>Resolved</p>
            {resolved.map((c) => (
              <CommentItem key={c.id} comment={c} onResolve={onResolve} onRemove={onRemove} />
            ))}
          </>
        )}
      </div>

      {unresolved.length > 0 && (
        <div className={styles.footer}>
          <button
            type="button"
            className={styles.sendBtn}
            onClick={() => void handleSendToAgent()}
            aria-label="Send comments to agent"
          >
            <SendHorizonal size={13} />
            Send to Agent
          </button>
        </div>
      )}
    </div>
  )
}
