import React from 'react';
import type { MessageType } from './types';
import { Icon } from './Icon';

// Notebook-cell-style type chip — a tinted mono badge that carries the message
// type (the card frame itself stays a neutral hairline). Colours come from CSS:
// `.msg-card[data-type="…"] .msg-type` in command-center.css.
export function MessageTypeBadge({ type }: { type: MessageType }) {
  const lead = type === 'decision' ? 'star' : type === 'artifact' ? 'file-text' : null;
  return (
    <div className="msg-type">
      {lead && <Icon name={lead} size={10} />}
      {type}
    </div>
  );
}
