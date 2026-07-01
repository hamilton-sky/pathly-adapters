import React from 'react';
import type { BoardScope, Preset, Direction } from './types';
import { SCOPES } from './agents';
import { CommsPanel } from './CommsPanel';
import { Icon } from './Icon';

export interface BoardSectionProps {
  scope: BoardScope;
  mainFeature: string;
  preset: Preset;
  direction: Direction;
  size?: number;
  onClose: (scope: BoardScope) => void;
}

const NAME: Record<BoardScope, (mainFeature: string) => string> = {
  feature: (f) => f,
  project: () => 'pathly-adapters',
  global: () => 'all projects · all features',
};

// Board-view default asymmetric widths: Feature 50 · Project 30 · Global 20.
const BOARD_WEIGHT: Record<BoardScope, number> = { feature: 50, project: 30, global: 20 };

function flexStyle({ scope, preset, direction, size }: BoardSectionProps): React.CSSProperties {
  if (size) return { flex: `0 0 ${size}px` };
  if (preset === 'board' && direction === 'row') return { flex: `${BOARD_WEIGHT[scope]} 1 0` };
  return { flex: '1 1 0' };
}

// A full-area section hosting one CommsPanel at a board scope (the workspace's
// content primitive — replaces SPEC §19's equal-panel slot).
export function BoardSection(props: BoardSectionProps) {
  const { scope, mainFeature, onClose } = props;
  const sc = SCOPES[scope];
  return (
    <div className="board" data-board={scope} style={flexStyle(props)}>
      <div className="bs-head">
        <span className="bs-icon" style={{ color: 'var(--accent)' }}><Icon name={sc.icon} size={15} /></span>
        <span className="bs-scope">{sc.title}</span>
        <span className="bs-sep">—</span>
        <span className="bs-name">{NAME[scope](mainFeature)}</span>
        <div className="bs-head-acts">
          <button className="bs-iconbtn" title="Attach artifact"><Icon name="plus" size={15} /></button>
          <button className="bs-iconbtn close" title="Hide section" onClick={() => onClose(scope)}><Icon name="x" size={15} /></button>
        </div>
      </div>
      <CommsPanel scope={scope} mainFeature={mainFeature} />
    </div>
  );
}
