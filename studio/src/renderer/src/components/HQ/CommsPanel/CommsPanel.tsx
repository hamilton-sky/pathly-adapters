import React, { useState } from 'react'
import { Check } from 'lucide-react'
import type { BoardScope, MessageType } from '../CommandCenter/types'
import { CommsMsgList } from './CommsMsgList'
import { CommsInput } from './CommsInput'
import { TypePicker } from './TypePicker'
import { useCommsPanel } from './hooks/useCommsPanel'
import s from './CommsPanel.module.css'

const READ_SCOPES: BoardScope[] = ['feature', 'project', 'global']

// Reusable board-thread building block: message list + a controls row
// (feature-only read-scope toggles + message-type picker) above the compose
// input. Reused by every BoardSection and, in Phase 5, the ConsultPanel.
export function CommsPanel({ scope, mainFeature }: { scope: BoardScope; mainFeature: string }) {
  const { messages, feature, flashId, post, answer, resolve, toggleScope, del } = useCommsPanel(scope, mainFeature)
  const [type, setType] = useState<MessageType>(scope === 'feature' ? 'nudge' : 'decision')

  return (
    <>
      <CommsMsgList
        scope={scope}
        messages={messages}
        flashId={flashId}
        onAnswer={answer}
        onResolve={resolve}
        onDelete={del}
      />

      <div className={s.foot}>
        <div className={s.controls}>
          {scope === 'feature' && feature && (
            <div className={s.scopes}>
              <span className={s.lbl}>Reads:</span>
              {READ_SCOPES.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={s.scopeChk}
                  {...(feature.scope[k] ? { 'data-on': '' } : {})}
                  aria-pressed={feature.scope[k]}
                  onClick={() => toggleScope(k)}
                >
                  <span className={s.box}>
                    {feature.scope[k] && <Check size={8} />}
                  </span>
                  {k.charAt(0).toUpperCase() + k.slice(1)}
                </button>
              ))}
            </div>
          )}
          <TypePicker value={type} onChange={setType} />
        </div>
        <CommsInput scope={scope} mainFeature={mainFeature} onSend={(text) => post(type, text)} />
      </div>
    </>
  )
}
