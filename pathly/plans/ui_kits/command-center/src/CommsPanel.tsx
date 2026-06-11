import React from 'react';
import type { BoardScope } from './types';
import { CommsMsgList } from './CommsMsgList';
import { CommsInput } from './CommsInput';
import { useCommsPanel } from './useCommsPanel';
import { Icon } from './Icon';

const READ_SCOPES: BoardScope[] = ['feature', 'project', 'global'];

// The reusable board-thread building block: message list + (feature-only)
// read-scope toggles + compose bar. Reused by every BoardSection and, in
// Phase 5, the ConsultPanel.
export function CommsPanel({ scope, mainFeature }: { scope: BoardScope; mainFeature: string }) {
  const { messages, feature, flashId, post, answer, resolve, toggleScope } = useCommsPanel(scope, mainFeature);

  return (
    <>
      <CommsMsgList scope={scope} messages={messages} flashId={flashId} onAnswer={answer} onResolve={resolve} />

      <div className="bs-foot">
        {scope === 'feature' && feature && (
          <div className="bs-scopes">
            <span className="lbl">Reads:</span>
            {READ_SCOPES.map((k) => (
              <button
                key={k}
                className="scope-chk"
                data-on={feature.scope[k] ? '' : undefined}
                onClick={() => toggleScope(k)}
              >
                <span className="box">{feature.scope[k] && <Icon name="check" size={8} />}</span>
                {k.charAt(0).toUpperCase() + k.slice(1)}
              </button>
            ))}
          </div>
        )}
        <CommsInput scope={scope} mainFeature={mainFeature} onSend={post} />
      </div>
    </>
  );
}
