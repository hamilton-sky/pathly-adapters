import React from 'react';
import type { AgentId } from './types';
import { AGENTS } from './agents';
import { Icon } from './Icon';

// Agent avatar — gradient "YOU" chip for the human, a stage-coloured lucide
// glyph for each agent role.
export function Avatar({ from }: { from: AgentId }) {
  const a = AGENTS[from];
  if (from === 'you') return <span className="avatar you">YOU</span>;
  return (
    <span className="avatar" style={{ background: a.color }}>
      <Icon name={a.icon || 'circle'} size={13} />
    </span>
  );
}
