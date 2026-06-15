import React, { useState, useEffect } from 'react';
import type { BoardScope, Direction, Preset } from './types';
import { SCOPES } from './agents';
import { Icon } from './Icon';

export interface CommandCenterHeaderProps {
  sections: BoardScope[];
  preset: Preset;
  direction: Direction;
  featurePending: number;
  onToggleSection: (scope: BoardScope) => void;
  onAddSection: () => void;
  onToggleDirection: () => void;
  onApplyPreset: (preset: 'board' | 'pipeline' | 'focus') => void;
}

const PRESET_ITEMS: Array<{ id: 'board' | 'pipeline' | 'focus'; name: string; desc: string }> = [
  { id: 'board', name: 'Board view', desc: 'Global · Project · Feature' },
  { id: 'pipeline', name: 'Pipeline view', desc: 'Feature + features rail' },
  { id: 'focus', name: 'Focus', desc: 'Feature board, full width' },
];

// Workspace header: section tabs (multi-select), layout direction toggle,
// presets menu, exit.
export function CommandCenterHeader(p: CommandCenterHeaderProps) {
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menu]);

  return (
    <div className="cc-head">
      <div className="cc-brand"><span className="dot">◈</span>Command Center</div>

      <div className="cc-tabs">
        {(['feature', 'project', 'global'] as BoardScope[]).map((s) => {
          const on = p.sections.indexOf(s) > -1;
          const pend = s === 'feature' ? p.featurePending : 0;
          return (
            <button key={s} className="cc-tab" data-on={on ? '' : undefined} onClick={() => p.onToggleSection(s)}>
              <Icon name={SCOPES[s].icon} size={13} />
              <span>{SCOPES[s].label}</span>
              <span className="st">{on ? '●' : '○'}</span>
              {pend > 0 && <span className="feat-badge msg">{pend}</span>}
            </button>
          );
        })}
        <button className="cc-tab add" title="Toggle a board section" onClick={p.onAddSection}>
          <Icon name="plus" size={13} />Add
        </button>
      </div>

      <div className="cc-head-right">
        {p.sections.length >= 2 && (
          <button className="cc-ctl" onClick={p.onToggleDirection}>
            <Icon name={p.direction === 'row' ? 'columns-2' : 'list'} size={13} />
            {p.direction === 'row' ? 'side by side' : 'stacked'}
          </button>
        )}
        <div className="cc-menu-wrap">
          <button className="cc-ctl" onClick={(e) => { e.stopPropagation(); setMenu((m) => !m); }}>
            <Icon name="layout-grid" size={13} />Presets<Icon name="chevron-down" size={12} />
          </button>
          <div className="cc-menu" data-open={menu ? '' : undefined}>
            {PRESET_ITEMS.map((it) => (
              <button key={it.id} className="cc-menu-item" data-active={p.preset === it.id ? '' : undefined} onClick={() => p.onApplyPreset(it.id)}>
                {p.preset === it.id ? <Icon name="check" size={13} /> : <span style={{ width: 13 }} />}
                <span>{it.name}</span><span className="desc">{it.desc}</span>
              </button>
            ))}
          </div>
        </div>
        <button className="cc-ctl cc-exit" title="Exit Command Center"><Icon name="x" size={15} /></button>
      </div>
    </div>
  );
}
