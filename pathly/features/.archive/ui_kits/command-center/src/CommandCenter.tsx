import React from 'react';
import type { BoardScope } from './types';
import { useCommsStore } from './useCommsStore';
import { useCommandCenter } from './useCommandCenter';
import { useSectionResize } from './useSectionResize';
import { CommandCenterHeader } from './CommandCenterHeader';
import { FeatureSidebar } from './FeatureSidebar';
import { BoardSection } from './BoardSection';
import { Icon } from './Icon';

// ── CommandCenter ───────────────────────────────────────────────────
// The full-screen workspace shell (UI-DIRECTION §2): header tabs + presets,
// a resizable All-Features sidebar, and one or more full-area board sections.
export function CommandCenter() {
  const store = useCommsStore();
  const cc = useCommandCenter();
  const { state } = cc;
  const onResize = useSectionResize(state.direction, cc.setSize);

  return (
    <div className="cc">
      <CommandCenterHeader
        sections={state.sections}
        preset={state.preset}
        direction={state.direction}
        featurePending={store.pendingCount(state.mainFeature)}
        onToggleSection={cc.toggleSection}
        onAddSection={cc.addAnySection}
        onToggleDirection={cc.toggleDirection}
        onApplyPreset={cc.applyPreset}
      />

      <div className="cc-body">
        <FeatureSidebar
          features={store.features}
          openFeature={state.openFeature}
          mainFeature={state.mainFeature}
          collapsed={state.sidebarCollapsed}
          pendingCount={store.pendingCount}
          onToggleSidebar={cc.toggleSidebar}
          onToggleFeature={cc.toggleOpenFeature}
          onSetMain={cc.setMainFeature}
          onRailOpen={cc.openFeatureFromRail}
          onStatus={store.setFeatureStatus}
        />

        {state.sections.length === 0 ? (
          <div className="cc-sections">
            <div className="cc-empty">
              <Icon name="layout-grid" size={30} />
              <p>No board sections open. Use the tabs above to show the <b>Feature</b>, <b>Project</b>, or <b>Global</b> board.</p>
            </div>
          </div>
        ) : (
          <div className={`cc-sections${state.direction === 'column' ? ' stacked' : ''}`}>
            {state.sections.map((scope, i) => (
              <React.Fragment key={scope}>
                {i > 0 && (
                  <div className="cc-resize" onMouseDown={(e) => onResize(e, state.sections[i - 1], scope as BoardScope)} />
                )}
                <BoardSection
                  scope={scope}
                  mainFeature={state.mainFeature}
                  preset={state.preset}
                  direction={state.direction}
                  size={state.sizes[scope]}
                  onClose={cc.toggleSection}
                />
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
