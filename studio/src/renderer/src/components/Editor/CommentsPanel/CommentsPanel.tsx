import React, { useCallback, useEffect, useRef, useState } from 'react'
import { SendHorizonal, Loader2, Eye, EyeOff, ChevronRight, Trash2 } from 'lucide-react'
import { Tooltip } from '../../ui'
import { useToastStore } from '../../../store/toastStore'
import type { Comment } from '../useComments'
import { buildSendPrompt, getSpawnCwd } from '../commentUtils'
import { CommentItem } from './CommentItem/CommentItem'
import styles from './CommentsPanel.module.css'

const MIN_WIDTH = 200
const MAX_WIDTH = 380
const STORAGE_KEY = 'comments-panel-width'

function getStoredWidth(): number {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    const n = parseInt(stored, 10)
    if (!isNaN(n)) return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, n))
  }
  return 290
}

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
  onDraftReady: (draftPath: string) => void
}

export function CommentsPanel({
  filePath, body, comments, showHighlights, orphanedIds, onToggleHighlights, onCollapse, onClearAll, onResolve, onReopen, onRemove, onEdit, onScrollTo, onDraftReady,
}: Props): JSX.Element {
  const pushToast = useToastStore((s) => s.push)
  const [isWorking, setIsWorking] = useState(false)

  const panelRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)
  const initialWidth = useRef(getStoredWidth())
  const exitUnsubRef = useRef<(() => void) | null>(null)

  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startWidth = panelRef.current?.getBoundingClientRect().width ?? initialWidth.current
    dragRef.current = { startX: e.clientX, startWidth }

    function onMouseMove(ev: MouseEvent): void {
      if (!dragRef.current || !panelRef.current) return
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, dragRef.current.startWidth + dragRef.current.startX - ev.clientX))
      panelRef.current.style.setProperty('--panel-width', `${newWidth}px`)
    }

    function onMouseUp(): void {
      if (panelRef.current) {
        const w = Math.round(panelRef.current.getBoundingClientRect().width)
        localStorage.setItem(STORAGE_KEY, String(w))
        initialWidth.current = w
      }
      dragRef.current = null
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  useEffect(() => {
    return () => {
      exitUnsubRef.current?.()
    }
  }, [])

  const unresolved = comments.filter((c) => !c.resolved)
  const resolved = comments.filter((c) => c.resolved)

  async function handleSendToAgent(): Promise<void> {
    if (!unresolved.length || isWorking) return
    const norm = filePath.replace(/\\/g, '/')
    const cwd = getSpawnCwd(filePath)
    const prompt = buildSendPrompt(filePath, body, unresolved)
    const tabId = `review-${Date.now().toString(36)}`

    setIsWorking(true)
    exitUnsubRef.current?.()
    exitUnsubRef.current = window.pathly.terminal.onExit((exitedTabId) => {
      if (exitedTabId !== tabId) return
      exitUnsubRef.current = null
      // Retry up to 5 times with 600 ms gaps — agent may still be flushing the file
      // to disk when the PTY exit event arrives.
      let attempt = 0
      const check = (): void => {
        attempt++
        void window.pathly.fs.read(norm + '.draft').then((content) => {
          if (content !== null && content.trim().length > 0) {
            setIsWorking(false)
            onDraftReady(norm + '.draft')
          } else if (attempt < 5) {
            setTimeout(check, 600)
          } else {
            setIsWorking(false)
            pushToast('Agent finished but wrote no draft — check the terminal for errors', 'error')
          }
        })
      }
      check()
    })

    await window.pathly.terminal.spawn(tabId, cwd, undefined, [
      'claude', '-p', prompt, '--print', '--dangerously-skip-permissions',
    ])
  }

  return (
    <div ref={panelRef} className={styles.panel} style={{ '--panel-width': `${initialWidth.current}px` } as React.CSSProperties}>
      <div className={styles.resizeHandle} onMouseDown={handleResizeMouseDown} />
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
              {showHighlights ? <Eye size={15} /> : <EyeOff size={15} />}
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
              <Trash2 size={15} />
            </button>
          </Tooltip>
          <Tooltip label="Collapse panel" placement="bottom">
            <button
              type="button"
              className={styles.toggleBtn}
              onClick={onCollapse}
              aria-label="Hide comments panel"
            >
              <ChevronRight size={15} />
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
            disabled={isWorking}
            aria-label={isWorking ? 'Agent is working…' : 'Send comments to agent'}
          >
            {isWorking
              ? <Loader2 size={15} className={styles.spinning} />
              : <SendHorizonal size={15} />}
            {isWorking ? 'Working…' : 'Send to Agent'}
          </button>
        </div>
      )}
    </div>
  )
}
