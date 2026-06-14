import React, { useEffect } from 'react'
import { LayoutGrid } from 'lucide-react'
import { MAX_SECTIONS } from './types'
import { useCommsStore } from '../../store/commsStore'
import { useCommandCenterStore } from '../../store/commandCenterStore'
import { useProjectStore } from '../../store/projectStore'
import { useSectionResize } from './hooks/useSectionResize'
import { CommandCenterHeader } from './CommandCenterHeader'
import { FeatureSidebar } from './FeatureSidebar'
import { BoardSection } from './BoardSection'
import s from './CommandCenter.module.css'

export function CommandCenter() {
  const store = useCommsStore()
  const cc = useCommandCenterStore()
  const projectPath = useProjectStore((s) => s.projectPath)
  const activeTopic = useProjectStore((s) => s.activeTopic)
  const onResize = useSectionResize(cc.direction, cc.setSize)

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
      />

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
                    aria-orientation={cc.direction === 'row' ? 'vertical' : 'horizontal'}
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
