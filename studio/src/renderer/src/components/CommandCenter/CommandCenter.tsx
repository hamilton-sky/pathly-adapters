import React, { useEffect, useState, useCallback } from 'react'
import { LayoutGrid } from 'lucide-react'
import { MAX_SECTIONS } from './types'
import { useCommsStore, type GlobalSearchHit } from '../../store/commsStore'
import { useCommandCenterStore } from '../../store/commandCenterStore'
import { useProjectStore } from '../../store/projectStore'
import { apiHydrateBoards } from '../../store/commsApi'
import { listDirs } from '../../services/pathlyApi'
import { useToastStore } from '../../store/toastStore'
import { useSectionResize } from './hooks/useSectionResize'
import { CommandCenterHeader } from './CommandCenterHeader/CommandCenterHeader'
import { FeatureSidebar } from './FeatureSidebar/FeatureSidebar'
import { BoardSection } from './BoardSection/BoardSection'
import { ConfirmModal } from '../shared/ConfirmModal/ConfirmModal'
import s from './CommandCenter.module.css'

export function CommandCenter() {
  const store = useCommsStore()
  const cc = useCommandCenterStore()
  const projectPath = useProjectStore((s) => s.projectPath)
  const activeTopic = useProjectStore((s) => s.activeTopic)
  const onResize = useSectionResize(cc.setSize)

  const [archivePending, setArchivePending] = useState<string | null>(null)
  // Opt-in: also commit the archived board's frozen BOARD.json (gitignored by default).
  const [commitSnapshot, setCommitSnapshot] = useState(false)

  const handleArchiveRequest = useCallback((id: string) => {
    setArchivePending(id)
  }, [])

  const handleArchiveConfirm = useCallback(async () => {
    const topic = archivePending
    const withSnapshot = commitSnapshot
    setArchivePending(null)
    setCommitSnapshot(false)
    if (!topic || !projectPath) return

    const push = useToastStore.getState().push
    try {
      // Detect whether this is a new-style (pathly/<topic>/) or feature-centric (pathly/features/<topic>/)
      // feature via container listings — never a STATE.json mirror probe (state-one-authority).
      // Feature-centric wins when both dirs exist, matching resolveFeaturePath's precedence.
      const featureNames = await listDirs(`${projectPath}/pathly/features`).catch(() => [] as string[])
      const topLevelNames = await listDirs(`${projectPath}/pathly`).catch(() => [] as string[])
      const isNewStyle = !featureNames.includes(topic) && topLevelNames.includes(topic)

      const src = isNewStyle
        ? `${projectPath}/pathly/${topic}`
        : `${projectPath}/pathly/features/${topic}`
      const dest = isNewStyle
        ? `${projectPath}/pathly/.archive/${topic}`
        : `${projectPath}/pathly/features/.archive/${topic}`

      // Close the feature's board tab/section first, then release the filesystem
      // watchers that hold handles under the feature folder — on Windows an open
      // watcher handle anywhere below a directory blocks renaming it (the EPERM that
      // made archive silently no-op). The workspace watcher is always re-armed in the
      // finally, even if the move fails.
      cc.removeFeatureTab(topic)
      await window.pathly.watch.stopFeature?.(topic)
      await window.pathly.watch.pauseWorkspace?.()
      try {
        await window.pathly.fs.move(src, dest)
      } finally {
        await window.pathly.watch.resumeWorkspace?.(projectPath)
      }
      await store.loadFeatures(projectPath)
      push(`Archived ${topic}`, 'success')

      // Opt-in: commit the now-frozen board so it travels with the repo. BOARD.json is
      // gitignored by default; this force-adds JUST this one file (local commit, no push).
      if (withSnapshot) {
        const boardRel = `${dest.slice(projectPath.length).replace(/^[\\/]/, '')}/BOARD.json`.replace(/\\/g, '/')
        const res = await window.pathly.git.commitBoard(projectPath, boardRel, `board: archive ${topic} snapshot`)
        if (res.ok && res.committed) push(`Committed ${topic} board snapshot · ${res.hash}`, 'success')
        else if (res.ok) push(`Nothing to commit${res.error ? ` — ${res.error}` : ''}`, 'info')
        else push(`Board commit failed${res.error ? ` — ${res.error}` : ''}`, 'error')
      }
    } catch (err: unknown) {
      // Without this, a failed move (Windows dir lock on an open descendant file, an
      // existing archive dest, a permission error) was swallowed as an unhandled
      // rejection — the modal had already closed and the feature silently stayed in the
      // sidebar. Surface the real reason so the user can act on it.
      // eslint-disable-next-line no-console
      console.error('[archive] failed to archive', topic, err)
      const msg = err instanceof Error ? err.message : String(err)
      push(`Couldn't archive ${topic} — ${msg}`, 'error')
    }
  }, [archivePending, commitSnapshot, projectPath, store, cc])

  const handleCreate = useCallback(async (topic: string, description: string) => {
    if (!projectPath) return

    // 1. Create the feature root at pathly/features/<topic>/ by writing a .keep sentinel
    //    file — the canonical feature-centric home (mirrors the FSM's default storage
    //    template `pathly/features/{topic}/`). fs.write mkdir -p's the parent.
    await window.pathly.fs.write(`${projectPath}/pathly/features/${topic}/.keep`, '')

    // 2. Reload the feature list so the new folder shows up in the sidebar.
    await store.loadFeatures(projectPath)

    // 3. Open the new feature's board. If already at cap, evict the right-most
    //    feature-scoped tab to make room (global/project tabs are preserved).
    cc.openNewFeature(topic)

    // 4. Post the description as the first board message if one was given.
    if (description) {
      store.post(topic, 'nudge', description, null)
    }
  }, [projectPath, store, cc])

  // Jump to a global-search hit: open/focus its board, then flash the matched message.
  // For features, openFeatureFromRail surfaces the board (tab + section + sidebar);
  // for project/global, show the section if it isn't already open.
  const handleOpenSearchResult = useCallback((hit: GlobalSearchHit) => {
    if (hit.boardScope === 'feature') {
      cc.openFeatureFromRail(hit.boardKey)
    } else if (!cc.sections.some((sec) => sec.scope === hit.boardScope)) {
      cc.toggleSection(hit.boardScope as 'project' | 'global')
    }
    store.flashMessage(hit.boardKey, hit.message.id)
  }, [cc, store])

  useEffect(() => {
    if (!projectPath) return
    // Board disk-mirror P2: hydrate any on-disk BOARD.json mirrors into the DB (fresh
    // clone). Best-effort + DB-authoritative (no-ops when a board already has rows), so
    // it's safe once per project open; boards pick up hydrated rows on their next poll.
    void apiHydrateBoards(projectPath.replace(/\\/g, '/').replace(/\/$/, ''))
    void store.loadFeatures(projectPath)
    // Rehydrate any still-running board/goal/flow run pills for this project from the
    // PERSISTED run registry (each re-verified against the backend), so a run in flight
    // before a reload reappears instead of vanishing with the in-memory pill maps. Once on mount.
    void store.rehydrateActiveRuns(projectPath.replace(/\\/g, '/').replace(/\/$/, ''))
    // The features list (stages, blocked status, newly-created features) has no live
    // push channel — refresh it periodically so the sidebar/cards don't go stale
    // until a manual action or remount.
    const id = window.setInterval(() => { void store.loadFeatures(projectPath) }, 10000)
    return () => window.clearInterval(id)
  }, [projectPath, store.loadFeatures, store.rehydrateActiveRuns])

  // Reconcile the open board layout whenever the active project's feature set
  // changes — critically on a project switch, so feature tabs/sections from the
  // previous project don't linger (they'd keep showing that project's board while a
  // different project is selected). Prunes to valid features and re-seeds mainFeature
  // (preferring activeTopic), or clears the feature area when the project has none.
  useEffect(() => {
    cc.syncToFeatures(store.features.map((f) => f.id), activeTopic ?? undefined)
  }, [store.features, activeTopic, cc.syncToFeatures])

  return (
    <div className={s.cc}>
      <CommandCenterHeader
        sections={cc.sections}
        featureTabs={cc.featureTabs}
        preset={cc.preset}
        mainFeature={cc.mainFeature}
        featurePending={store.pendingCount(cc.mainFeature)}
        atCap={cc.sections.length >= MAX_SECTIONS}
        onToggleSection={cc.toggleSection}
        onToggleFeatureSection={cc.toggleFeatureSection}
        onRemoveFeatureTab={cc.removeFeatureTab}
        onAddSection={cc.addAnySection}
        onApplyPreset={cc.applyPreset}
        onCreateFeature={handleCreate}
        onOpenSearchResult={handleOpenSearchResult}
      />

      {archivePending && (
        <ConfirmModal
          title={<>Archive <b>{archivePending}</b>?</>}
          message="Moves the feature folder to .archive/ — recoverable by moving it back."
          confirmLabel="Archive"
          footerSlot={
            <label className={s.archiveSnapshot}>
              <input
                type="checkbox"
                checked={commitSnapshot}
                onChange={(e) => setCommitSnapshot(e.target.checked)}
              />
              Also commit this board&apos;s snapshot to git
            </label>
          }
          onCancel={() => { setArchivePending(null); setCommitSnapshot(false) }}
          onConfirm={handleArchiveConfirm}
        />
      )}

      <div className={s.body}>
        <FeatureSidebar
          features={store.features}
          openFeature={cc.openFeature}
          mainFeature={cc.mainFeature}
          collapsed={cc.sidebarCollapsed}
          pendingCount={store.pendingCount}
          openBoards={cc.featureTabs}
          atCap={cc.featureTabs.length >= MAX_SECTIONS}
          onToggleSidebar={cc.toggleSidebar}
          onToggleFeature={cc.toggleOpenFeature}
          onSetMain={cc.setMainFeature}
          onRailOpen={cc.openFeatureFromRail}
          onOpenBoard={cc.addFeatureSection}
          onStatus={store.setFeatureStatus}
          onArchive={handleArchiveRequest}
        />

        {cc.sections.length === 0 ? (
          <div className={s.sections}>
            <div className={s.empty}>
              <LayoutGrid size={30} className={s.emptyIcon} />
              <p>No board sections open. Use the tabs above to show the <b>Feature</b>, <b>Project</b>, or <b>Global</b> board.</p>
            </div>
          </div>
        ) : (
          <div className={s.sections}>
            {cc.sections.map((sec, i) => (
              <React.Fragment key={sec.id}>
                {i > 0 && (
                  <div
                    className={s.resize}
                    role="separator"
                    aria-orientation="vertical"
                    onMouseDown={(e) => onResize(e, cc.sections[i - 1].id, sec.id)}
                  />
                )}
                <BoardSection
                  section={sec}
                  mainFeature={cc.mainFeature}
                  preset={cc.preset}
                  size={cc.sizes[sec.id]}
                  onClose={() => {
                    if (sec.scope === 'feature') cc.toggleFeatureSection(sec.featureId)
                    else cc.toggleSection(sec.scope as 'project' | 'global')
                  }}
                />
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
