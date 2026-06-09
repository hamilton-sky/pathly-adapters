import React from 'react'
import { SendHorizonal, Eye, EyeOff, ChevronRight, Trash2 } from 'lucide-react'
import { Tooltip } from '../../ui'
import { useTerminalStore } from '../../../store/terminalStore'
import type { Comment } from '../useComments'
import { buildSendPrompt, getSpawnCwd } from '../commentUtils'
import { CommentItem } from './CommentItem/CommentItem'
import styles from './CommentsPanel.module.css'

interface Props {
  filePath: string
  body: string
  comments: Comment[]
  showHighlights: boolean
  orphanedIds: Set<string>
  onToggleHighlights: () => void
  onCollapse: () => void
  onClearAll: () => void
  onResolve: (id: string) => void
  onReopen: (id: string) => void
  onRemove: (id: string) => void
  onEdit: (id: string, body: string) => void
  onScrollTo: (id: string) => void
}

export function CommentsPanel({
  filePath, body, comments, showHighlights, orphanedIds, onToggleHighlights, onCollapse, onClearAll, onResolve, onReopen, onRemove, onEdit, onScrollTo,
}: Props): JSX.Element {
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
        <div className={styles.headerBtns}>
          <Tooltip label={showHighlights ? 'Hide highlights' : 'Show highlights'} placement="bottom">
            <button
              type="button"
              className={styles.toggleBtn}
              onClick={onToggleHighlights}
              aria-label={showHighlights ? 'Hide highlights in preview' : 'Show highlights in preview'}
            >
              {showHighlights ? <Eye size={13} /> : <EyeOff size={13} />}
            </button>
          </Tooltip>
          <Tooltip label="Clear all comments" placement="bottom">
            <button
              type="button"
              className={`${styles.toggleBtn} ${styles.clearBtn}`}
              onClick={onClearAll}
              disabled={comments.length === 0}
              aria-label="Clear all comments"
            >
              <Trash2 size={13} />
            </button>
          </Tooltip>
          <Tooltip label="Collapse panel" placement="bottom">
            <button
              type="button"
              className={styles.toggleBtn}
              onClick={onCollapse}
              aria-label="Hide comments panel"
            >
              <ChevronRight size={13} />
            </button>
          </Tooltip>
        </div>
      </div>

      <div className={styles.list}>
        {comments.length === 0 && (
          <p className={styles.empty}>Select text in the preview to add a comment</p>
        )}
        {unresolved.map((c, idx) => (
          <CommentItem
            key={c.id}
            comment={c}
            index={idx + 1}
            isOrphaned={orphanedIds.has(c.id)}
            onResolve={onResolve}
            onReopen={onReopen}
            onRemove={onRemove}
            onEdit={onEdit}
            onScrollTo={onScrollTo}
          />
        ))}
        {resolved.length > 0 && (
          <>
            <p className={styles.resolvedLabel}>Resolved</p>
            {resolved.map((c, idx) => (
              <CommentItem
                key={c.id}
                comment={c}
                index={idx + 1}
                isOrphaned={false}
                onResolve={onResolve}
                onReopen={onReopen}
                onRemove={onRemove}
                onEdit={onEdit}
                onScrollTo={onScrollTo}
              />
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
