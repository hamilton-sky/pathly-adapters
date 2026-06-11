import React from 'react'
import { LayoutGrid } from 'lucide-react'
import type { BoardScope } from './types'
import { useCommsStore } from '../../../store/commsStore'
import { useCommandCenterStore } from '../../../store/commandCenterStore'
import { useSectionResize } from './hooks/useSectionResize'
import { CommandCenterHeader } from './CommandCenterHeader'
import { FeatureSidebar } from './FeatureSidebar'
import { BoardSection } from './BoardSection'
import s from './CommandCenter.module.css'

// The full-screen workspace shell (UI-DIRECTION §2):
// header tabs + presets, a resizable All-Features sidebar, and one or more
// full-area board sections. Not yet wired into HQ navigation — see remaining steps.
export function CommandCenter() {
  const store = useCommsStore()
  const cc = useCommandCenterStore()
  const onResize = useSectionResize(cc.direction, cc.setSize)

  return (
    <div className={s.cc}>
      <CommandCenterHeader
        sections={cc.sections}
        preset={cc.preset}
        direction={cc.direction}
        featurePending={store.pendingCount(cc.mainFeature)}
        onToggleSection={cc.toggleSection}
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
          onToggleSidebar={cc.toggleSidebar}
          onToggleFeature={cc.toggleOpenFeature}
          onSetMain={cc.setMainFeature}
          onRailOpen={cc.openFeatureFromRail}
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
            {cc.sections.map((scope, i) => (
              <React.Fragment key={scope}>
                {i > 0 && (
                  <div
                    className={s.resize}
                    role="separator"
                    aria-orientation={cc.direction === 'row' ? 'vertical' : 'horizontal'}
                    onMouseDown={(e) => onResize(e, cc.sections[i - 1], scope as BoardScope)}
                  />
                )}
                <BoardSection
                  scope={scope}
                  mainFeature={cc.mainFeature}
                  preset={cc.preset}
                  direction={cc.direction}
                  size={cc.sizes[scope]}
                  onClose={cc.toggleSection}
                />
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
