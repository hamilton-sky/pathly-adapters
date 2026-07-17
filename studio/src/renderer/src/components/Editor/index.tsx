import { useCallback, useEffect, useRef, useState } from 'react'
import { GitCompare, Replace } from 'lucide-react'
import { useStore } from '../../store'
import { useUiStore, selectMdEditorSplitDraftPath } from '../../store/uiStore'
import { useTerminalStore } from '../../store/terminalStore'
import { useMarkdownEditorStore } from '../../store/markdownEditorStore'
import { readFile, writeFile } from '../../services/pathlyApi'
import { buildCliArgv } from '../MarkdownEditor/EditorHeader/editorCli'
import type { EditorCli } from '../MarkdownEditor/EditorHeader/editorCli'
import type { FrontmatterValues } from '../../types'
import { Tooltip } from '../ui'
import { ConfigForm } from './ConfigForm'
import { MarkdownEditor } from './MarkdownEditor'
import type { MarkdownEditorHandle } from './MarkdownEditor'
import { MarkdownPreview } from './MarkdownPreview'
import { FindReplaceBar } from './FindReplaceBar/FindReplaceBar'
import { useFindReplace } from './useFindReplace'
import { CommentsPanel } from './CommentsPanel/CommentsPanel'
import { CommentsPanelRail } from './CommentsPanel/CommentsPanelRail/CommentsPanelRail'
import { CommentablePreview } from './CommentablePreview/CommentablePreview'
import { DraftDiffViewer } from './DraftDiffViewer'
import type { CommentablePreviewHandle } from './CommentablePreview/CommentablePreview'
import { CommentModal } from './CommentModal/CommentModal'
import { useComments } from './useComments'
import type { CommentColor } from './useComments'
import { deriveLineNumber, buildSendPrompt, getSpawnCwd } from './commentUtils'
import { COMMENT_VERBS } from './commentVerbs'
import { useMergedPresets } from '../shared/PromptActionConfig/useMergedPresets'
import { useProjectStore } from '../../store/projectStore'
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

export function Editor({ path: pathOverride, embedded }: { path?: string | null; embedded?: boolean } = {}): JSX.Element {
  const { selectedItem, markDirty, clearDirty, dirtyItems } = useStore()
  // Merge the user's DB-backed 'comment' verbs so a saved verb picked in the modal resolves
  // to its prompt on send (fail-soft: just the built-ins when the library is empty/unreachable).
  const commentProjectRoot = useProjectStore((s) => s.projectPath)
  const { presets: mergedCommentVerbs } = useMergedPresets(COMMENT_VERBS, {
    kind: 'preset',
    category: 'comment',
    projectRoot: commentProjectRoot,
  })
  const resetLastAppliedPath = useMarkdownEditorStore((s) => s.resetLastAppliedPath)
  const setMdEditorSplitDraftPath = useUiStore(s => s.setMdEditorSplitDraftPath)
  const splitDraftPath            = useUiStore(selectMdEditorSplitDraftPath)
  const mdEditorSaveRequested = useUiStore(s => s.mdEditorSaveRequested)
  const mdEditorOpenDraftReq  = useUiStore(s => s.mdEditorOpenDraftRequested)
  const mdEditorUndoReq       = useUiStore(s => s.mdEditorUndoRequested)
  const mdEditorRedoReq       = useUiStore(s => s.mdEditorRedoRequested)
  const markdownEditorRef     = useRef<MarkdownEditorHandle>(null)

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
  // Two independent draft slots so AI Split and comment-revisions never overwrite each other.
  // Split drafts cross into the toolbar, so they live in the store; comment drafts are reviewed
  // from the comments panel inside this subtree, so they stay local.
  const [commentDraftPath, setCommentDraftPath] = useState<string | null>(null)
  const [diffOpen, setDiffOpen]     = useState(false)
  const [diffSource, setDiffSource] = useState<'split' | 'comments'>('comments')
  const activeDraftPath = diffSource === 'split' ? (embedded ? splitDraftPath : null) : commentDraftPath

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

  const findEnabled = (tab === 'edit' || tab === 'split') && !diffOpen
  const find = useFindReplace(markdownEditorRef, findEnabled, effectivePath)

  useEffect(() => {
    if (!effectivePath) return
    setCommentDraftPath(null)
    setDiffOpen(false)
    setTab('preview')
    setPendingAnchor(null)
    setAnchorPos(null)
    setModalOpen(false)
    setPendingBody('')
    setLoading(true)
    setSaveError(null)
    // Restore any drafts left on disk so a pending review survives reloads.
    const commentDraft = effectivePath + '.comments.draft'
    void window.pathly.fs.read(commentDraft).then((d) => {
      if (d != null && d !== '') setCommentDraftPath(commentDraft)
    })
    if (embedded) {
      const splitDraft = effectivePath + '.split.draft'
      void window.pathly.fs.read(splitDraft).then((d) => {
        if (d != null && d !== '') setMdEditorSplitDraftPath(splitDraft, effectivePath)
      })
    }
    readFile(effectivePath)
      .then((content) => {
        const parsed = parseFrontmatter(content ?? '')
        setConfig(parsed.config)
        setBody(parsed.body)
      })
      .catch(() => { setConfig({} as FrontmatterValues); setBody('') })
      .finally(() => setLoading(false))
  }, [effectivePath, embedded])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); void performSave(body, config) }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  })

  const performSave = useCallback(async (currentBody: string, currentConfig: FrontmatterValues): Promise<void> => {
    if (!effectivePath) return
    setSaveError(null)
    const merged = `---\n${serializeFrontmatter(currentConfig)}\n---\n${currentBody}`
    try {
      await writeFile(effectivePath, merged)
      clearDirty(effectivePath)
      // Allow cells view to reload fresh content after a source edit
      resetLastAppliedPath()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }, [effectivePath, clearDirty, resetLastAppliedPath])

  // ── Refs so embedded coordination effects always see the latest body/config ─
  const bodyRef   = useRef(body)
  const configRef = useRef(config)
  bodyRef.current   = body
  configRef.current = config

  // ── Embedded: save when EditorHeader's Save button is pressed ───────────
  const prevSaveReqRef = useRef(mdEditorSaveRequested)
  useEffect(() => {
    if (!embedded) return
    if (mdEditorSaveRequested === prevSaveReqRef.current) return
    prevSaveReqRef.current = mdEditorSaveRequested
    void performSave(bodyRef.current, configRef.current)
  }, [embedded, mdEditorSaveRequested, performSave])

  // ── Embedded: open the SPLIT diff viewer when EditorHeader's Diff chip is pressed.
  //    Comment drafts are reviewed from the comments panel, not via this signal.
  const pendingOpenSplitRef = useRef(false)
  const prevOpenDraftReqRef = useRef(mdEditorOpenDraftReq)
  useEffect(() => {
    if (!embedded) return
    if (mdEditorOpenDraftReq === prevOpenDraftReqRef.current) return
    prevOpenDraftReqRef.current = mdEditorOpenDraftReq
    setDiffSource('split')
    if (splitDraftPath) { setDiffOpen(true) } else { pendingOpenSplitRef.current = true }
  }, [embedded, mdEditorOpenDraftReq, splitDraftPath])

  useEffect(() => {
    if (pendingOpenSplitRef.current && splitDraftPath) {
      setDiffSource('split')
      setDiffOpen(true)
      pendingOpenSplitRef.current = false
    }
  }, [splitDraftPath])

  // ── Embedded: undo/redo via CodeMirror when EditorHeader buttons pressed ─
  const prevUndoReqRef = useRef(mdEditorUndoReq)
  useEffect(() => {
    if (!embedded) return
    if (mdEditorUndoReq === prevUndoReqRef.current) return
    prevUndoReqRef.current = mdEditorUndoReq
    markdownEditorRef.current?.undo()
  }, [embedded, mdEditorUndoReq])

  const prevRedoReqRef = useRef(mdEditorRedoReq)
  useEffect(() => {
    if (!embedded) return
    if (mdEditorRedoReq === prevRedoReqRef.current) return
    prevRedoReqRef.current = mdEditorRedoReq
    markdownEditorRef.current?.redo()
  }, [embedded, mdEditorRedoReq])

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

  async function handleModalSendNow(commentBody: string, color: CommentColor, cli: EditorCli, verbName: string, extra: string): Promise<void> {
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
    const verb = mergedCommentVerbs.find((v) => v.name === verbName)
    const prompt = buildSendPrompt(effectivePath, body, allUnresolved, verb, extra)
    const tabId = `review-${Date.now().toString(36)}`
    addTab(tabId, `Review · ${fileName}`)
    openTab(tabId)
    // Surface the revision draft once the engine exits, so the comments panel's Diff lights up.
    const draftFile = norm + '.comments.draft'
    const unsub = window.pathly.terminal.onExit((exitedTabId) => {
      if (exitedTabId !== tabId) return
      unsub()
      let attempt = 0
      const check = (): void => {
        attempt++
        void window.pathly.fs.read(draftFile).then((content) => {
          if (content !== null && content.trim().length > 0) setCommentDraftPath(draftFile)
          else if (attempt < 5) setTimeout(check, 600)
        })
      }
      check()
    })
    await window.pathly.terminal.spawn(tabId, getSpawnCwd(effectivePath), undefined, buildCliArgv(cli, prompt), undefined, {
      telemetry: { scopeTier: 'project', label: 'ai-editor', role: 'editor' },
    })
  }

  const draftFileFor = (src: 'split' | 'comments'): string =>
    (effectivePath ?? '') + (src === 'split' ? '.split.draft' : '.comments.draft')

  const clearDraftSlot = (src: 'split' | 'comments'): void => {
    if (src === 'split') setMdEditorSplitDraftPath(null, effectivePath ?? undefined)
    else setCommentDraftPath(null)
  }

  const openCommentDiff = useCallback(() => {
    setDiffSource('comments')
    setDiffOpen(true)
  }, [])

  async function handleDiffApply(newContent: string): Promise<void> {
    if (!effectivePath) return
    await window.pathly.fs.write(effectivePath, newContent)
    await window.pathly.fs.delete(draftFileFor(diffSource))
    clearDraftSlot(diffSource)
    setDiffOpen(false)
    const parsed = parseFrontmatter(newContent)
    setConfig(parsed.config)
    setBody(parsed.body)
    clearDirty(effectivePath)
  }

  async function handleDiffDiscard(): Promise<void> {
    if (!effectivePath) return
    await window.pathly.fs.delete(draftFileFor(diffSource))
    clearDraftSlot(diffSource)
    setDiffOpen(false)
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
      <div className={styles.toolbar} {...(embedded ? { 'data-embedded': 'true' } : {})}>
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
                  type="button"
                  className={tab === t_ ? styles.tabActive : styles.tab}
                  onClick={() => setTab(t_)}
                >
                  {t_ === 'split' ? '⊟ Split' : t_.charAt(0).toUpperCase() + t_.slice(1)}
                </button>
              </Tooltip>
            )
          })}
          {findEnabled && (
            <Tooltip label="Find & replace" shortcut="Ctrl+F" placement="bottom">
              <button
                type="button"
                className={find.open ? styles.iconTabActive : styles.iconTab}
                onClick={() => find.toggle('find')}
                aria-label="Find and replace"
                {...(find.open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
              >
                <Replace size={14} />
              </button>
            </Tooltip>
          )}
        </div>
        {!embedded && <span className={styles.breadcrumb}>{breadcrumb}</span>}
        {!embedded && (
          <div className={styles.actions}>
            {saveError && <span className={styles.error}>{saveError}</span>}
            {commentDraftPath && (
              <Tooltip label="Comment revisions ready — click to review changes" placement="bottom">
                <button
                  type="button"
                  className={styles.draftReadyBtn}
                  onClick={openCommentDiff}
                >
                  <GitCompare size={13} />
                  Review draft
                </button>
              </Tooltip>
            )}
            {tab === 'preview' && (
              <Tooltip label="Edit raw source" placement="bottom">
                <button type="button" className={styles.tab} onClick={() => setTab('edit')}>
                  Edit source
                </button>
              </Tooltip>
            )}
            <Tooltip label="Save file" shortcut="Ctrl+S" placement="bottom">
              <button
                type="button"
                className={`${styles.saveBtn} ${isDirty ? '' : styles.saveBtnClean}`}
                onClick={() => void performSave(body, config)}
              >
                {isDirty ? 'Save ●' : 'Saved'}
              </button>
            </Tooltip>
          </div>
        )}
      </div>

      {isPreviewDefault && (
        <ConfigForm
          values={config}
          onChange={handleConfigChange}
          compact={tab !== 'edit'}
        />
      )}

      <div className={styles.editorArea}>
        {findEnabled && find.open && (
          <FindReplaceBar
            mode={find.mode}
            query={find.query}
            replaceText={find.replaceText}
            info={find.info}
            onQueryChange={find.onQueryChange}
            onReplaceChange={find.onReplaceChange}
            onNext={find.next}
            onPrev={find.prev}
            onReplaceOne={find.replaceOne}
            onReplaceAll={find.replaceAll}
            onClose={find.close}
          />
        )}
        {tab === 'edit' && (
          <div className={styles.full}>
            <MarkdownEditor ref={markdownEditorRef} value={body} onChange={handleBodyChange} />
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
                    hasDraft={!!commentDraftPath}
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
                    commentDraftPath={commentDraftPath}
                    onReviewDraft={openCommentDiff}
                    onToggleHighlights={() => setShowHighlights((v) => !v)}
                    onCollapse={() => setShowPanel(false)}
                    onClearAll={clearAllComments}
                    onResolve={resolveComment}
                    onReopen={reopenComment}
                    onRemove={removeComment}
                    onEdit={editComment}
                    onScrollTo={(id) => previewRef.current?.scrollToComment(id)}
                    onDraftReady={setCommentDraftPath}
                  />
                )}
              </>
            )}
          </div>
        )}
        {tab === 'split' && (
          <div className={styles.splitRow}>
            <div className={styles.half}>
              <MarkdownEditor ref={markdownEditorRef} value={body} onChange={handleBodyChange} />
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
          onSendNow={(b, color, cli, verbName, extra) => void handleModalSendNow(b, color, cli, verbName, extra)}
          onDraftChange={setPendingBody}
          onClose={() => setModalOpen(false)}
          onCancel={() => { setModalOpen(false); setPendingAnchor(null); setAnchorPos(null); setPendingBody('') }}
        />
      )}

      {activeDraftPath && effectivePath && diffOpen && (
        <DraftDiffViewer
          originalPath={effectivePath}
          draftPath={activeDraftPath}
          source={diffSource}
          comments={diffSource === 'comments' ? comments.filter((c) => !c.resolved) : []}
          onApply={(content) => void handleDiffApply(content)}
          onClose={() => setDiffOpen(false)}
          onDiscard={() => void handleDiffDiscard()}
        />
      )}
    </div>
  )
}
