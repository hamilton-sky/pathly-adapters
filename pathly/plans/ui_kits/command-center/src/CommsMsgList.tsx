import React from 'react';
import type { BoardScope, Message } from './types';
import { AGENTS } from './agents';
import { CommsMsgCard } from './CommsMsgCard';
import { Icon } from './Icon';

export interface CommsMsgListProps {
  scope: BoardScope;
  messages: Message[];
  flashId?: string | null;
  onAnswer?: (messageId: string, optionId: string) => void;
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void;
}

// Pinned decisions tray + the message thread.
export function CommsMsgList({ scope, messages, flashId, onAnswer, onResolve }: CommsMsgListProps) {
  const pins = messages.filter((m) => m.pinned);
  const thread = messages.filter((m) => !m.pinned);

  return (
    <div className="bs-thread">
      {pins.length > 0 && (
        <div className="bs-pins">
          {pins.map((m) => (
            <div key={m.id} className={`pin${flashId === m.id ? ' flash' : ''}`}>
              <Icon name="star" size={14} />
              <div>
                <div className="pin-txt" dangerouslySetInnerHTML={{ __html: m.text }} />
                <div className="pin-meta">
                  {AGENTS[m.from].label}{m.stage ? ` · ${m.stage}` : ''} · {m.time} ago ·{' '}
                  <span className="pin-scope">{scope} scope</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {thread.length > 0
        ? thread.map((m) => (
            <CommsMsgCard key={m.id} message={m} flash={flashId === m.id} onAnswer={onAnswer} onResolve={onResolve} />
          ))
        : (
          <div className="cc-empty" style={{ padding: '24px' }}>
            <Icon name="message-square" size={22} />
            <p>No messages on this board yet.</p>
          </div>
        )}
    </div>
  );
}
