import { useCallback, useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { readFile, writeFile } from '../../services/pathlyApi'
import type { FrontmatterValues } from '../../types'
import { Tooltip } from '../ui'
import { ConfigForm } from './ConfigForm'
import { MarkdownEditor } from './MarkdownEditor'
import { MarkdownPreview } from './MarkdownPreview'
import { CommentsPanel } from './CommentsPanel/CommentsPanel'
import { CommentsPanelRail } from './CommentsPanel/CommentsPanelRail/CommentsPanelRail'
import { CommentablePreview } from './CommentablePreview/CommentablePreview'
import type { CommentablePreviewHandle } from './CommentablePreview/CommentablePreview'
import { CommentModal } from './CommentModal/CommentModal'
import { useComments } from './useComments'
import type { CommentColor } from './useComments'
import { deriveLineNumber, buildSendPrompt, getSpawnCwd } from './commentUtils'
import styles from './index.module.css'

type TabMode = 'edit' | 'preview' | 'split'

// ── Frontmatter parsing / serialization ────────────────────────────────────

function parseFrontmatter(raw: string): { config: FrontmatterValues; body: string } {
  if (!raw.startsWith('---')) return { config: {} as FrontmatterValues, body: raw }
  const end = raw.indexOf('\n---', 3)
  if (end === -1) return { config: {} as FrontmatterValues, body: raw }
  const config = parseSimpleYaml(raw.slice(4, end).trim())
  const body = raw.slice(end + 4).replace(/^\n/, '')
  return { config, body }
}

function parseSimpleYaml(text: string): FrontmatterValues {
  const result: Record<string, unknown> = {}
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length) {
    const keyMatch = lines[i].match(/^(\w[\w-]*):\s*(.*)$/)
    if (!keyMatch) { i++; continue }
    const [, key, rest] = keyMatch
    const trimmed = rest.trim()
    if (trimmed === '' || trimmed === '|' || trimmed === '>') {
      const items: string[] = []
      i++
      while (i < lines.length && /^\s+-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s+-\s+/, '').trim())
        i++
      }
      result[key] = items.length > 0 ? items : ''
      continue
    }
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      result[key] = trimmed.slice(1, -1).split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean)
    } else {
      result[key] = trimmed.replace(/^['"]|['"]$/g, '')
    }
    i++
  }
  return result as unknown as FrontmatterValues
}

function serializeFrontmatter(config: FrontmatterValues): string {
  return Object.entries(config)
    .flatMap(([key, value]) => {
      if (value === undefined || value === null) return []
      if (Array.isArray(value)) {
        return value.length === 0
          ? [`${key}: []`]
          : [`${key}:`, ...value.map((v) => `  - ${v}`)]
      }
      return [`${key}: ${String(value)}`]
    })
    .join('\n')
}

// ── Component ──────────────────────────────────────────────────────────────

function typeFromPath(p: string): 'skill' | 'agent' | 'template' | 'other' {
  const norm = p.replace(/\\/g, '/')
  if (norm.includes('/agents/')) return 'agent'
  if (norm.includes('/templates/')) return 'template'
  if (norm.includes('/skills/')) return 'skill'
  return 'other'
}

export function Editor({ path: pathOverride }: { path?: string | null } = {}): JSX.Element {
  const { selectedItem, markDirty, clearDirty, dirtyItems } = useStore()

  const effectivePath = pathOverride ?? selectedItem?.path ?? null

  const isDirty = effectivePath ? dirtyItems.has(effectivePath) : false
  const derivedType = effectivePath && !selectedItem ? typeFromPath(effectivePath) : (selectedItem?.type ?? 'other')
  const isSkillOrAgent = derivedType === 'skill' || derivedType === 'agent'
  const isPreviewDefault = isSkillOrAgent || derivedType === 'template'

  const { comments, add: addComment, edit: editComment, resolve: resolveComment, reopen: reopenComment, remove: removeComment, clearAll: clearAllComments } = useComments(effectivePath)
  const [pendingAnchor, setPendingAnchor] = useState<string | null>(null)
  const [anchorPos, setAnchorPos]         = useState<{ x: number; y: number } | null>(null)
  const [modalOpen, setModalOpen]         = useState(false)
  const [pendingBody, setPendingBody]     = useState('')
  const [showHighlights, setShowHighlights] = useState(true)
  const [showPanel, setShowPanel] = useState(true)
  const [draftPath, setDraftPath] = useState<string | null>(null)

  const previewRef = useRef<CommentablePreviewHandle>(null)
  const [orphanedIds, setOrphanedIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    const timer = setTimeout(() => {
      setOrphanedIds(previewRef.current?.getOrphanedIds() ?? new Set())
    }, 200)
    return () => clearTimeout(timer)
  }, [comments])

  const addTab = useTerminalStore((s) => s.addTab)
  const openTab = useTerminalStore((s) => s.openTab)

  const [config, setConfig] = useState<FrontmatterValues>({} as FrontmatterValues)
  const [body, setBody]     = useState('')
  const [tab, setTab]       = useState<TabMode>('preview')
  const [loading, setLoading]     = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const breadcrumb = selectedItem && !pathOverride
    ? `${selectedItem.type.charAt(0).toUpperCase() + selectedItem.type.slice(1)}s / ${selectedItem.name}`
    : effectivePath
      ? effectivePath.replace(/\\/g, '/').split('/').slice(-2).join(' › ').replace('.md', '')
      : ''

  useEffect(() => {
    if (!effectivePath) return
    setDraftPath(null)
    setTab('preview')
    setPendingAnchor(null)
    setAnchorPos(null)
    setModalOpen(false)
    setPendingBody('')
    setLoading(true)
    setSaveError(null)
    readFile(effectivePath)
      .then((content) => {
        const parsed = parseFrontmatter(content ?? '')
        setConfig(parsed.config)
        setBody(parsed.body)
      })
      .catch(() => { setConfig({} as FrontmatterValues); setBody('') })
      .finally(() => setLoading(false))
  }, [effectivePath])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); void performSave(body, config) }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  })

  async function performSave(currentBody: string, currentConfig: FrontmatterValues): Promise<void> {
    if (!effectivePath) return
    setSaveError(null)
    const merged = `---\n${serializeFrontmatter(currentConfig)}\n---\n${currentBody}`
    try {
      await writeFile(effectivePath, merged)
      clearDirty(effectivePath)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleConfigChange(v: FrontmatterValues): void {
    setConfig(v)
    if (effectivePath) markDirty(effectivePath)
  }

  function handleBodyChange(v: string): void {
    setBody(v)
    if (effectivePath) markDirty(effectivePath)
    if (tab === 'preview') return
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current)
    autoSaveRef.current = setTimeout(() => void performSave(v, config), 2000)
  }

  function handleModalAdd(commentBody: string, color: CommentColor): void {
    if (!pendingAnchor || !effectivePath) return
    const newId = addComment(deriveLineNumber(body, pendingAnchor), pendingAnchor, commentBody, color)
    previewRef.current?.captureRange(newId)   // pin the live Range so submitted highlight = draft highlight
    setPendingAnchor(null)
    setAnchorPos(null)
    setModalOpen(false)
    setPendingBody('')
  }

  async function handleModalSendNow(commentBody: string, color: CommentColor): Promise<void> {
    if (!pendingAnchor || !effectivePath) return
    const lineNumber = deriveLineNumber(body, pendingAnchor)
    const newId = addComment(lineNumber, pendingAnchor, commentBody, color)
    previewRef.current?.captureRange(newId)   // same fix for Send-to-Agent path
    setPendingAnchor(null)
    setAnchorPos(null)
    setModalOpen(false)
    setPendingBody('')
    const newItem = {
      id: 'send-now', lineNumber, lineText: pendingAnchor.slice(0, 120),
      body: commentBody, resolved: false, createdAt: '', color,
    }
    const allUnresolved = [...comments.filter((c) => !c.resolved), newItem]
    const norm = effectivePath.replace(/\\/g, '/')
    const fileName = norm.split('/').pop() ?? 'file'
    const prompt = buildSendPrompt(effectivePath, body, allUnresolved)
    const tabId = `review-${Date.now().toString(36)}`
    addTab(tabId, `Review · ${fileName}`)
    openTab(tabId)
    await window.pathly.terminal.spawn(tabId, getSpawnCwd(effectivePath), undefined, [
      'claude', '-p', prompt, '--print', '--dangerously-skip-permissions',
    ])
  }

  const handleSelectionComment = useCallback((text: string, x: number, y: number) => {
    setPendingAnchor(text)
    setAnchorPos({ x, y })
    setModalOpen(true)
    setPendingBody('')
  }, [])

  const handleResume = useCallback((x: number, y: number) => {
    setAnchorPos({ x, y })
    setModalOpen(true)
  }, [])

  if (loading) {
    return <div className={styles.panel}><div className={styles.message}>Loading…</div></div>
  }

  const tabs: TabMode[] = ['preview', 'edit', 'split']

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <div className={styles.tabs}>
          {tabs.map((t_) => {
            const tabLabels: Record<TabMode, { label: string; shortcut?: string }> = {
              edit:    { label: 'Edit source' },
              preview: { label: 'Preview markdown' },
              split:   { label: 'Side-by-side view' },
            }
            const { label, shortcut } = tabLabels[t_]
            return (
              <Tooltip key={t_} label={label} shortcut={shortcut} placement="bottom">
                <button
                  className={tab === t_ ? styles.tabActive : styles.tab}
                  onClick={() => setTab(t_)}
                >
                  {t_ === 'split' ? '⊟ Split' : t_.charAt(0).toUpperCase() + t_.slice(1)}
                </button>
              </Tooltip>
            )
          })}
        </div>
        <span className={styles.breadcrumb}>{breadcrumb}</span>
        <div className={styles.actions}>
          {saveError && <span className={styles.error}>{saveError}</span>}
          {tab === 'preview' && (
            <Tooltip label="Edit raw source" placement="bottom">
              <button className={styles.tab} onClick={() => setTab('edit')}>
                Edit source
              </button>
            </Tooltip>
          )}
          <Tooltip label="Save file" shortcut="Ctrl+S" placement="bottom">
            <button
              className={`${styles.saveBtn} ${isDirty ? '' : styles.saveBtnClean}`}
              onClick={() => void performSave(body, config)}
            >
              {isDirty ? 'Save ●' : 'Saved'}
            </button>
          </Tooltip>
        </div>
      </div>

      {isPreviewDefault && (
        <ConfigForm
          values={config}
          onChange={handleConfigChange}
          compact={tab !== 'edit'}
        />
      )}

      <div className={styles.editorArea}>
        {tab === 'edit' && (
          <div className={styles.full}>
            <MarkdownEditor value={body} onChange={handleBodyChange} />
          </div>
        )}
        {tab === 'preview' && (
          <div className={styles.previewWithComments}>
            <div className={styles.previewContent}>
              <CommentablePreview
                ref={previewRef}
                content={body}
                pendingAnchor={pendingAnchor}
                modalOpen={modalOpen}
                comments={comments}
                showHighlights={showHighlights}
                onSelectionComment={handleSelectionComment}
                onResume={handleResume}
              />
            </div>
            {effectivePath && (
              <>
                {!showPanel && (
                  <CommentsPanelRail
                    comments={comments}
                    onExpand={() => setShowPanel(true)}
                  />
                )}
                {showPanel && (
                  <CommentsPanel
                    filePath={effectivePath}
                    body={body}
                    comments={comments}
                    showHighlights={showHighlights}
                    orphanedIds={orphanedIds}
                    onToggleHighlights={() => setShowHighlights((v) => !v)}
                    onCollapse={() => setShowPanel(false)}
                    onClearAll={clearAllComments}
                    onResolve={resolveComment}
                    onReopen={reopenComment}
                    onRemove={removeComment}
                    onEdit={editComment}
                    onScrollTo={(id) => previewRef.current?.scrollToComment(id)}
                    onDraftReady={setDraftPath}
                  />
                )}
              </>
            )}
          </div>
        )}
        {tab === 'split' && (
          <div className={styles.splitRow}>
            <div className={styles.half}>
              <MarkdownEditor value={body} onChange={handleBodyChange} />
            </div>
            <div className={styles.splitDivider} />
            <div className={styles.half}>
              <MarkdownPreview content={body} />
            </div>
          </div>
        )}
      </div>

      {modalOpen && pendingAnchor && anchorPos && (
        <CommentModal
          anchorText={pendingAnchor}
          x={anchorPos.x}
          y={anchorPos.y}
          initialBody={pendingBody}
          onAdd={handleModalAdd}
          onSendNow={(b, color) => void handleModalSendNow(b, color)}
          onDraftChange={setPendingBody}
          onClose={() => setModalOpen(false)}
          onCancel={() => { setModalOpen(false); setPendingAnchor(null); setAnchorPos(null); setPendingBody('') }}
        />
      )}
    </div>
  )
}
