import React, { useCallback, useEffect, useRef, useState } from 'react'
import { SendHorizonal, Loader2, Square, Eye, EyeOff, ChevronRight, Trash2, GitCompare } from 'lucide-react'
import { Tooltip } from '../../ui'
import { useToastStore } from '../../../store/toastStore'
import { useTerminalStore } from '../../../store/terminalStore'
import type { Comment } from '../useComments'
import { buildSendPrompt, getSpawnCwd, describeAgentFailure } from '../commentUtils'
import {
  CLI_KEY_COMMENT,
  PRESET_KEY_COMMENT,
  COMMENT_EXTRA_KEY,
  COMMENT_PROMPT_KEY,
  loadEditorCli,
  loadPreset,
  buildCliArgv,
  cliLabel,
  type EditorCli,
} from '../../MarkdownEditor/EditorHeader/editorCli'
import { effectiveModel } from '../../../services/spawnPolicy'
import { featureFromPath } from '../../../utils/featureFromPath'
import { COMMENT_VERBS } from '../commentVerbs'
import { attachProgress, fmtElapsed, useElapsedProgress } from '../../shared/RunPill/progress'
import { CommentItem } from './CommentItem/CommentItem'
import { CommentConfigButton } from './CommentConfigButton/CommentConfigButton'
import SendPreviewModal from '../../shared/SendPreviewModal/SendPreviewModal'
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
  /** Path of the pending comment-revision draft, or null. Lights up the Diff button. */
  commentDraftPath: string | null
  /** Open the comment-revision diff viewer. */
  onReviewDraft: () => void
}

export function CommentsPanel({
  filePath, body, comments, showHighlights, orphanedIds, commentDraftPath, onReviewDraft, onToggleHighlights, onCollapse, onClearAll, onResolve, onReopen, onRemove, onEdit, onScrollTo, onDraftReady,
}: Props): JSX.Element {
  const pushToast = useToastStore((s) => s.push)
  // Holds the running send's tab id (null when idle). Drives the elapsed timer + stop button,
  // mirroring the toolbar's Analyze pill. isWorking is derived from it.
  const [activeTabId, setActiveTabId] = useState<string | null>(null)
  const isWorking = activeTabId !== null
  const [defaultCli, setDefaultCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_COMMENT))
  const [defaultPreset, setDefaultPreset] = useState(() => loadPreset(PRESET_KEY_COMMENT))
  // Confirm-before-send: holds the engine while the modal is open; sendSel tracks which
  // comments are included (the prompt is rebuilt from the selected subset).
  const [pendingSend, setPendingSend] = useState<{ cli: EditorCli } | null>(null)
  const [sendSel, setSendSel] = useState<Set<string>>(new Set())

  const panelRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)
  const initialWidth = useRef(getStoredWidth())
  const exitUnsubRef = useRef<(() => void) | null>(null)

  // Elapsed timer derives from the running tab's startedAt — survives re-render for free,
  // same pattern as the EditorHeader Analyze pill.
  const sendStartedAt = useTerminalStore((s) => s.tabs.find((t) => t.id === activeTabId)?.startedAt)
  const sendProgress = useElapsedProgress(isWorking ? sendStartedAt : undefined)

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

  // Build the prompt from a chosen subset of comments. Panel-default framing: an edited
  // prompt override wins, else the selected verb; extra instructions are appended.
  function buildSelectedPrompt(selIds: Set<string>): string {
    const override = loadPreset(COMMENT_PROMPT_KEY)
    const extra = loadPreset(COMMENT_EXTRA_KEY)
    const verb = override.trim()
      ? { name: 'custom', label: '', hint: '', prompt: override.trim() }
      : COMMENT_VERBS.find((v) => v.name === defaultPreset)
    return buildSendPrompt(filePath, body, unresolved.filter((c) => selIds.has(c.id)), verb, extra)
  }

  // Open the confirm-preview with every comment selected; the spawn fires only on submit.
  function prepareSend(): void {
    if (!unresolved.length || isWorking) return
    setSendSel(new Set(unresolved.map((c) => c.id)))
    setPendingSend({ cli: defaultCli })
  }

  async function runSend(prompt: string, cli: EditorCli): Promise<void> {
    const norm = filePath.replace(/\\/g, '/')
    const cwd = getSpawnCwd(filePath)
    const draftPath = norm + '.comments.draft'
    const fileName = norm.split('/').pop() ?? 'file'
    const tabId = `review-${Date.now().toString(36)}`

    setActiveTabId(tabId)
    // Visible terminal tab (like AI Split/Analyze) so the spawning CLI engine is on screen.
    // Tab kind is display-only ('claude'); the real engine is applied via buildCliArgv(cli) below.
    useTerminalStore.getState().addTab(tabId, `Comments · ${fileName}`, 'left', 'claude', undefined, undefined, prompt)
    // Stamp 'running' BEFORE the spawn await so startedAt is set at t0 — the elapsed timer
    // derives from tab.startedAt (same trick as the toolbar's Analyze pill).
    useTerminalStore.getState().updateTabStatus(tabId, 'running')
    useTerminalStore.getState().openTab(tabId)
    pushToast(`Comments sent · ${fileName} (${cliLabel(cli)})`, 'info', { category: 'phase_summary' })
    // attachProgress drives the milestone toasts; the pill's timer is derived from tab.startedAt,
    // so we discard the per-tick progress payload.
    const stopProgress = attachProgress(tabId, () => {}, (line) => pushToast(`Comments: ${line}`, 'info', { category: 'phase_summary' }))
    exitUnsubRef.current?.()
    exitUnsubRef.current = window.pathly.terminal.onExit((exitedTabId, exitCode, tail) => {
      if (exitedTabId !== tabId) return
      exitUnsubRef.current = null
      stopProgress()
      let attempt = 0
      const check = (): void => {
        attempt++
        void window.pathly.fs.read(draftPath).then((content) => {
          if (content !== null && content.trim().length > 0) {
            useTerminalStore.getState().updateTabStatus(tabId, 'done')
            useTerminalStore.getState().closeTab(tabId)
            setActiveTabId(null)
            pushToast(`Comment revisions ready · ${fileName} — review the diff`, 'success', { category: 'agent_done' })
            onDraftReady(draftPath)
          } else if (attempt < 5) {
            setTimeout(check, 600)
          } else {
            useTerminalStore.getState().updateTabStatus(tabId, 'error')
            useTerminalStore.getState().closeTab(tabId)
            setActiveTabId(null)
            pushToast(describeAgentFailure('Send', fileName, exitCode, tail), 'error', { category: 'agent_done' })
          }
        })
      }
      check()
    })

    try {
      const feature = featureFromPath(filePath)
      await window.pathly.terminal.spawn(tabId, cwd, undefined, buildCliArgv(cli, prompt, effectiveModel('comment', cli)), undefined, {
        telemetry: { scopeTier: feature ? 'feature' : 'project', label: 'ai-comment', role: 'commenter', ...(feature ? { feature } : {}) },
      })
    } catch (e) {
      // Spawn rejected (e.g. queue cancel / over cap) — onExit will never fire, so clean up here.
      exitUnsubRef.current?.()
      exitUnsubRef.current = null
      stopProgress()
      useTerminalStore.getState().closeTab(tabId)
      setActiveTabId(null)
      if (!(e instanceof Error && /cancelled/i.test(e.message))) {
        pushToast(`Send failed · ${fileName} — could not launch ${cliLabel(cli)}`, 'error', { category: 'agent_done' })
      }
    }
  }

  // Stop closes the tab immediately (a force-killed PTY may never deliver a clean exit) and
  // unsubscribes onExit so the draft poll can't fire after cancel.
  function stopSend(): void {
    const tabId = activeTabId
    if (!tabId) return
    exitUnsubRef.current?.()
    exitUnsubRef.current = null
    void window.pathly.terminal.kill(tabId)
    useTerminalStore.getState().updateTabStatus(tabId, 'done')
    useTerminalStore.getState().closeTab(tabId)
    setActiveTabId(null)
    const fileName = filePath.replace(/\\/g, '/').split('/').pop() ?? 'file'
    pushToast(`Send stopped · ${fileName}`, 'info', { category: 'phase_summary' })
  }

  // Live prompt for the modal — rebuilt whenever the comment selection changes.
  const sendPrompt = pendingSend ? buildSelectedPrompt(sendSel) : ''

  return (
    <div ref={panelRef} className={styles.panel} style={{ '--panel-width': `${initialWidth.current}px` } as React.CSSProperties}>
      <div className={styles.resizeHandle} onMouseDown={handleResizeMouseDown} />
      <div className={styles.header}>
        <span className={styles.title}>
          Comments
          {unresolved.length > 0 && <span className={styles.badge}>{unresolved.length}</span>}
        </span>
        <div className={styles.headerBtns}>
          <Tooltip
            label={commentDraftPath ? 'Comment revisions ready — review the diff' : 'No revisions yet — send comments to an agent first'}
            placement="bottom"
          >
            <button
              type="button"
              className={`${styles.toggleBtn} ${styles.diffBtn}`}
              data-has-draft={commentDraftPath ? 'true' : 'false'}
              disabled={!commentDraftPath}
              onClick={onReviewDraft}
              aria-label="Review comment revisions"
            >
              <GitCompare size={15} />
            </button>
          </Tooltip>
          <CommentConfigButton
            onCliChange={setDefaultCli}
            onPresetChange={setDefaultPreset}
          />
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
          {isWorking ? (
            <div className={styles.sendPill}>
              <span className={styles.sendBtnRunning}>
                <Loader2 size={15} className={styles.spinning} />
                {sendProgress ? `Sending… ${fmtElapsed(sendProgress.elapsedS)}` : 'Sending…'}
              </span>
              <Tooltip label="Stop the running engine" placement="top">
                <button
                  type="button"
                  className={styles.sendStop}
                  onClick={stopSend}
                  aria-label="Stop send"
                >
                  <Square size={12} />
                </button>
              </Tooltip>
            </div>
          ) : (
            <button
              type="button"
              className={styles.sendBtn}
              onClick={prepareSend}
              aria-label={`Send comments to ${cliLabel(defaultCli)}`}
            >
              <SendHorizonal size={15} />
              {`Send to ${cliLabel(defaultCli)}`}
            </button>
          )}
        </div>
      )}

      {pendingSend && (
        <SendPreviewModal
          title="Send comments to agent"
          engineLabel={cliLabel(pendingSend.cli)}
          fileName={filePath.split(/[\\/]/).pop() ?? 'file'}
          prompt={sendPrompt}
          costCtx={{ engine: pendingSend.cli }}
          itemsLabel="Comments to send"
          items={unresolved.map((c, i) => ({
            id: c.id,
            label: `${i + 1}. ${c.body || c.lineText}`,
            selected: sendSel.has(c.id),
            color: c.color,
          }))}
          onToggleItem={(id) => setSendSel((prev) => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id); else next.add(id)
            return next
          })}
          submitLabel={`Send to ${cliLabel(pendingSend.cli)}`}
          onSubmit={(prompt) => { const p = pendingSend; setPendingSend(null); if (p) void runSend(prompt, p.cli) }}
          onCancel={() => setPendingSend(null)}
        />
      )}
    </div>
  )
}
