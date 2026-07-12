import React, { useEffect, useState, useCallback } from 'react'
import { LayoutGrid } from 'lucide-react'
import { MAX_SECTIONS } from './types'
import { useCommsStore, type GlobalSearchHit } from '../../store/commsStore'
import { useCommandCenterStore } from '../../store/commandCenterStore'
import { useProjectStore } from '../../store/projectStore'
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

  const handleArchiveRequest = useCallback((id: string) => {
    setArchivePending(id)
  }, [])

  const handleArchiveConfirm = useCallback(async () => {
    const topic = archivePending
    setArchivePending(null)
    if (!topic || !projectPath) return

    // Detect whether this is a new-style (pathly/<topic>/) or feature-centric (pathly/features/<topic>/) feature.
    // Mirror the resolveFeaturePath logic: check for .keep sentinel, then STATE.json.
    const newStyleBase = `${projectPath}/pathly/${topic}`
    const keep = await window.pathly.fs.read(`${newStyleBase}/.keep`)
    const stateJson = keep === null ? await window.pathly.fs.read(`${newStyleBase}/STATE.json`) : null
    const isNewStyle = keep !== null || stateJson !== null

    const src = isNewStyle
      ? `${projectPath}/pathly/${topic}`
      : `${projectPath}/pathly/features/${topic}`
    const dest = isNewStyle
      ? `${projectPath}/pathly/.archive/${topic}`
      : `${projectPath}/pathly/features/.archive/${topic}`

    await window.pathly.fs.move(src, dest)
    await store.loadFeatures(projectPath)

    // Evict the feature's tab and section from the board.
    cc.removeFeatureTab(topic)
  }, [archivePending, projectPath, store, cc])

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
    void store.loadFeatures(projectPath)
    // The features list (stages, blocked status, newly-created features) has no live
    // push channel — refresh it periodically so the sidebar/cards don't go stale
    // until a manual action or remount.
    const id = window.setInterval(() => { void store.loadFeatures(projectPath) }, 10000)
    return () => window.clearInterval(id)
  }, [projectPath, store.loadFeatures])

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
          onCancel={() => setArchivePending(null)}
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
