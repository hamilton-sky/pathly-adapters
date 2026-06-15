import React from 'react';
import type { Message } from './types';
import { AGENTS, STAGE_COLOR } from './agents';
import { Avatar } from './Avatar';
import { MessageTypeBadge } from './MessageTypeBadge';
import { Icon } from './Icon';

// Renders the inner body of `<div className="msg-text" />` (message text may
// carry inline <code>/<b>; in production this is sanitised markdown).
const html = (s: string) => ({ __html: s });

export interface CommsMsgCardProps {
  message: Message;
  flash?: boolean;
  onAnswer?: (messageId: string, optionId: string) => void;
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void;
}

export function CommsMsgCard({ message: m, flash, onAnswer, onResolve }: CommsMsgCardProps) {
  const agent = AGENTS[m.from];
  return (
    <div className={`msg${flash ? ' flash' : ''}`} data-msg={m.id}>
      <div className="msg-meta">
        <Avatar from={m.from} />
        <span className="msg-author">{agent.label}</span>
        {m.stage && (
          <span className="msg-stage" style={{ color: STAGE_COLOR[m.stage] || 'var(--text-muted)' }}>{m.stage}</span>
        )}
        {m.ack && <span className="msg-ack"><Icon name="check" size={11} />acknowledged</span>}
        <span className="msg-time">{m.time} ago</span>
      </div>

      <div className="msg-card" data-type={m.type}>
        <MessageTypeBadge type={m.type} />
        <CardBody message={m} onAnswer={onAnswer} onResolve={onResolve} />
      </div>
    </div>
  );
}

function CardBody({ message: m, onAnswer, onResolve }: CommsMsgCardProps) {
  if (m.type === 'artifact') {
    return (
      <>
        <div className="art">
          <span className="art-ico"><Icon name="file-text" size={15} /></span>
          <span className="art-name">{m.artifact}</span>
        </div>
        <div className="art-excerpt" dangerouslySetInnerHTML={html(m.text)} />
        <div className="art-q"><Icon name="search" size={11} />agents can query this by content</div>
      </>
    );
  }

  if (m.type === 'question') {
    return (
      <>
        <div className="msg-text" dangerouslySetInnerHTML={html(m.text)} />
        <div className="opts">
          {(m.options || []).map((o) => (
            <button
              key={o.id}
              className={`opt${m.answer === o.id ? ' chosen' : ''}`}
              onClick={() => onAnswer?.(m.id, o.id)}
            >
              <span className="ring" />
              <span>{o.label}</span>
              {o.desc && <span className="odesc">{o.desc}</span>}
            </button>
          ))}
        </div>
        <div className="q-foot">
          {m.status === 'answered'
            ? <span className="q-status answered"><Icon name="check" size={11} />answered · injected at next /next_action</span>
            : <span className="q-status pending"><span className="q-spin" />awaiting answer · non-blocking</span>}
        </div>
      </>
    );
  }

  if (m.type === 'warning' || m.type === 'escalation') {
    return (
      <>
        <div className="msg-text" dangerouslySetInnerHTML={html(m.text)} />
        {m.status === 'resolved'
          ? <div className="msg-resolved"><Icon name="check" size={11} />{m.resolution || 'resolved'}</div>
          : (
            <div className="msg-acts">
              <button className="msg-act danger" onClick={() => onResolve?.(m.id, 'block')}><Icon name="history" size={12} />Block stage</button>
              <button className="msg-act go" onClick={() => onResolve?.(m.id, 'note')}><Icon name="check" size={12} />Note as future work</button>
              <button className="msg-act" onClick={() => onResolve?.(m.id, 'ignore')}><Icon name="eye-off" size={12} />Ignore</button>
            </div>
          )}
      </>
    );
  }

  return <div className="msg-text" dangerouslySetInnerHTML={html(m.text)} />;
}
