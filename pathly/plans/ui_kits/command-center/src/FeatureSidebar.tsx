import React from 'react';
import type { Feature } from './types';
import { FeatureCard } from './FeatureCard';
import { Icon } from './Icon';

export interface FeatureSidebarProps {
  features: Feature[];
  openFeature: string | null;
  mainFeature: string;
  collapsed: boolean;
  pendingCount: (id: string) => number;
  onToggleSidebar: () => void;
  onToggleFeature: (id: string) => void;
  onSetMain: (id: string) => void;
  onRailOpen: (id: string) => void;
  onStatus: (id: string, status: 'running' | 'idle', stage?: 'BUILDING' | 'TESTING') => void;
}

// Left navigation — "All Features". Resizable/collapsible (VS Code / Notion
// file-tree pattern). Collapsed → icon strip with badges; expanded → an
// accordion of feature cards (one open at a time).
export function FeatureSidebar(p: FeatureSidebarProps) {
  if (p.collapsed) {
    return (
      <div className="cc-sidebar collapsed">
        <div className="cc-sb-head">
          <button className="cc-sb-collapse" title="Expand" onClick={p.onToggleSidebar}><Icon name="panel-left" size={15} /></button>
        </div>
        <div className="cc-sb-rail">
          {p.features.map((f) => {
            const pend = p.pendingCount(f.id);
            const blocked = f.status === 'blocked';
            return (
              <button key={f.id} className="cc-railbtn" title={f.id} onClick={() => p.onRailOpen(f.id)}>
                <span className={`feat-stdot st-${f.status}`} />
                {(pend > 0 || blocked) && (
                  <span className={`rail-badge${blocked ? ' blk' : ''}`}>{blocked ? '!' : pend}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="cc-sidebar">
      <div className="cc-sb-head">
        <span className="cc-sb-title">All Features</span>
        <span className="cc-sb-count">{p.features.length}</span>
        <button className="cc-sb-collapse" title="Collapse" onClick={p.onToggleSidebar}><Icon name="panel-left" size={15} /></button>
      </div>
      <div className="cc-sb-list">
        {p.features.map((f) => (
          <FeatureCard
            key={f.id}
            feature={f}
            open={p.openFeature === f.id}
            isMain={p.mainFeature === f.id}
            pending={p.pendingCount(f.id)}
            onToggle={p.onToggleFeature}
            onSetMain={p.onSetMain}
            onStatus={p.onStatus}
          />
        ))}
      </div>
    </div>
  );
}
