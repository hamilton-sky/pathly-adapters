import React, { useEffect, useState, useCallback } from 'react'
import { LayoutGrid } from 'lucide-react'
import { MAX_SECTIONS } from './types'
import { useCommsStore } from '../../store/commsStore'
import { useCommandCenterStore } from '../../store/commandCenterStore'
import { useProjectStore } from '../../store/projectStore'
import { useSectionResize } from './hooks/useSectionResize'
import { CommandCenterHeader } from './CommandCenterHeader/CommandCenterHeader'
import { FeatureSidebar } from './FeatureSidebar/FeatureSidebar'
import { BoardSection } from './BoardSection/BoardSection'
import { NewFeatureModal } from './NewFeatureModal/NewFeatureModal'
import type { DefaultExecutor } from './NewFeatureModal/NewFeatureModal'
import s from './CommandCenter.module.css'

export function CommandCenter() {
  const store = useCommsStore()
  const cc = useCommandCenterStore()
  const projectPath = useProjectStore((s) => s.projectPath)
  const activeTopic = useProjectStore((s) => s.activeTopic)
  const onResize = useSectionResize(cc.direction, cc.setSize)

  const [showNewFeature, setShowNewFeature] = useState(false)

  const handleCreate = useCallback(async (topic: string, description: string, _executor: DefaultExecutor) => {
    setShowNewFeature(false)
    if (!projectPath) return

    // 1. Create the feature root at pathly/<topic>/ by writing a .keep sentinel file.
    //    fs.write calls mkdirSync(..., { recursive: true }) in the main process.
    await window.pathly.fs.write(`${projectPath}/pathly/${topic}/.keep`, '')

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

  useEffect(() => {
    if (projectPath) void store.loadFeatures(projectPath)
  }, [projectPath, store.loadFeatures])

  useEffect(() => {
    if (store.features.length === 0) return
    if (store.features.some((f) => f.id === cc.mainFeature)) return
    const next = activeTopic && store.features.some((f) => f.id === activeTopic)
      ? activeTopic
      : store.features[0].id
    cc.setMainFeature(next)
  }, [store.features, cc.mainFeature, activeTopic, cc.setMainFeature])

  return (
    <div className={s.cc}>
      <CommandCenterHeader
        sections={cc.sections}
        featureTabs={cc.featureTabs}
        preset={cc.preset}
        direction={cc.direction}
        mainFeature={cc.mainFeature}
        featurePending={store.pendingCount(cc.mainFeature)}
        atCap={cc.sections.length >= MAX_SECTIONS}
        onToggleSection={cc.toggleSection}
        onToggleFeatureSection={cc.toggleFeatureSection}
        onRemoveFeatureTab={cc.removeFeatureTab}
        onAddSection={cc.addAnySection}
        onToggleDirection={cc.toggleDirection}
        onApplyPreset={cc.applyPreset}
        onNewFeature={() => setShowNewFeature(true)}
      />

      {showNewFeature && (
        <NewFeatureModal
          onCancel={() => setShowNewFeature(false)}
          onCreate={handleCreate}
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
        />

        {cc.sections.length === 0 ? (
          <div className={s.sections}>
            <div className={s.empty}>
              <LayoutGrid size={30} className={s.emptyIcon} />
              <p>No board sections open. Use the tabs above to show the <b>Feature</b>, <b>Project</b>, or <b>Global</b> board.</p>
            </div>
          </div>
        ) : (
          <div className={`${s.sections}${cc.direction === 'column' ? ` ${s.stacked}` : ''}`}>
            {cc.sections.map((sec, i) => (
              <React.Fragment key={sec.id}>
                {i > 0 && (
                  <div
                    className={s.resize}
                    role="separator"
                    {...(cc.direction === 'row' ? { 'aria-orientation': 'vertical' } : { 'aria-orientation': 'horizontal' })}
                    onMouseDown={(e) => onResize(e, cc.sections[i - 1].id, sec.id)}
                  />
                )}
                <BoardSection
                  section={sec}
                  mainFeature={cc.mainFeature}
                  preset={cc.preset}
                  direction={cc.direction}
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
