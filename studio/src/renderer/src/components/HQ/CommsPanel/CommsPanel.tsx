import React from 'react'
import { Check } from 'lucide-react'
import type { BoardScope } from '../CommandCenter/types'
import { CommsMsgList } from './CommsMsgList'
import { CommsInput } from './CommsInput'
import { useCommsPanel } from './hooks/useCommsPanel'
import s from './CommsPanel.module.css'

const READ_SCOPES: BoardScope[] = ['feature', 'project', 'global']

// Reusable board-thread building block: message list + (feature-only)
// read-scope toggles + compose bar. Reused by every BoardSection and,
// in Phase 5, the ConsultPanel.
export function CommsPanel({ scope, mainFeature }: { scope: BoardScope; mainFeature: string }) {
  const { messages, feature, flashId, post, answer, resolve, toggleScope } = useCommsPanel(scope, mainFeature)

  return (
    <>
      <CommsMsgList
        scope={scope}
        messages={messages}
        flashId={flashId}
        onAnswer={answer}
        onResolve={resolve}
      />

      <div className={s.foot}>
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
        <CommsInput scope={scope} mainFeature={mainFeature} onSend={post} />
      </div>
    </>
  )
}
