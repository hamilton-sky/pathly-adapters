import React from 'react';
import type { Feature } from './types';
import { STAGE_COLOR } from './agents';
import { Icon } from './Icon';

export interface FeatureCardProps {
  feature: Feature;
  open: boolean;
  isMain: boolean;
  pending: number;
  onToggle: (id: string) => void;
  onSetMain: (id: string) => void;
  onStatus: (id: string, status: 'running' | 'idle', stage?: 'BUILDING' | 'TESTING') => void;
}

// One accordion card in the All-Features sidebar. Carries the "Set as main
// feature ↗" bridge action and quick status controls.
export function FeatureCard({ feature: f, open, isMain, pending, onToggle, onSetMain, onStatus }: FeatureCardProps) {
  return (
    <div className={`feat${open ? ' open' : ''}${isMain ? ' main' : ''}`} data-fcard={f.id}>
      <button className="feat-bar" onClick={() => onToggle(f.id)}>
        <span className={`feat-stdot st-${f.status}`} />
        <span className="feat-name">{f.id}</span>
        <span className="feat-badges">
          {f.status === 'blocked'
            ? <span className="feat-badge blk"><Icon name="history" size={9} />blocked</span>
            : pending > 0 && <span className="feat-badge msg"><Icon name="message-square" size={9} />{pending}</span>}
        </span>
        <span className="feat-chev"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} /></span>
      </button>

      <div className="feat-body">
        <div className="feat-stage">
          <span className="stg" style={{ color: STAGE_COLOR[f.stage] || 'var(--text-muted)' }}>{f.stage}</span>
          <span className="feat-conv">conv {f.conv} · {f.status}</span>
        </div>
        <div className="feat-last" dangerouslySetInnerHTML={{ __html: f.last }} />
        <div className="feat-acts">
          {isMain
            ? <span className="feat-act" style={{ cursor: 'default', color: 'var(--accent)', borderColor: 'var(--accent-border)' }}><Icon name="check" size={12} />Main feature</span>
            : <button className="feat-act primary" onClick={() => onSetMain(f.id)}><Icon name="external-link" size={12} />Set as main</button>}
          {f.status === 'blocked' && (
            <>
              <button className="feat-act warn" onClick={() => onStatus(f.id, 'running', 'BUILDING')}><Icon name="play" size={12} />Unblock</button>
              <button className="feat-act" onClick={() => onStatus(f.id, 'running', 'TESTING')}><Icon name="skip-forward" size={12} />Skip</button>
            </>
          )}
          {f.status === 'running' && (
            <button className="feat-act" onClick={() => onStatus(f.id, 'idle')}><Icon name="pause" size={12} />Pause</button>
          )}
        </div>
      </div>
    </div>
  );
}
