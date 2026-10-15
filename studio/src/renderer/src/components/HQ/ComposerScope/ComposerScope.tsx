import { useCallback, useRef } from 'react'
import { Layers, Zap } from 'lucide-react'
import { useHqComposerStore, type HqScopeTab } from '../../../store/hqComposerStore'
import { useHqContextStore } from '../../../store/hqContextStore'
import { ScopeChip } from './ScopeChip/ScopeChip'
import { ScopePopover, type ScopeTabDef } from './ScopePopover/ScopePopover'
import { TokenMeter } from './TokenMeter/TokenMeter'
import { ContextTab } from './ContextTab/ContextTab'
import { ActionsTab } from './ActionsTab/ActionsTab'
import { useActionSelection } from './hooks/useActionSelection'
import { useLatestManifest } from './hooks/useLatestManifest'
import { useScopeDismiss } from './hooks/useScopeDismiss'
import { MAX_HQ_ACTIONS } from '../../../store/hqActionsStore'
import { contextCount, estimateContext } from './scopeUtils'
import styles from './ComposerScope.module.css'

const POPOVER_ID = 'hq-composer-scope'
const TABS: ScopeTabDef[] = [{ id: 'context', label: 'Context' }, { id: 'actions', label: 'Actions' }]

/** The chip row above the HQ input: what the NEXT question carries. Each chip
 *  opens the one shared popover on its own tab. Answers keep a read-only record
 *  of what they used (ContextManifest), whose "Adjust" link opens this. */
export function ComposerScope(): JSX.Element {
  const openTab = useHqComposerStore((s) => s.openTab)
  const openScope = useHqComposerStore((s) => s.openScope)
  const closeScope = useHqComposerStore((s) => s.closeScope)
  const enabled = useHqContextStore((s) => s.enabled)
  const manifest = useLatestManifest()
  const actions = useActionSelection(openTab !== null)

  const rowRef = useRef<HTMLDivElement>(null)
  const chipRefs = useRef<Partial<Record<HqScopeTab, HTMLButtonElement | null>>>({})
  const returnFocus = useCallback(() => {
    const tab = useHqComposerStore.getState().openTab ?? 'context'
    chipRefs.current[tab]?.focus()
  }, [])
  useScopeDismiss(openTab !== null, rowRef, closeScope, returnFocus)

  const toggle = (tab: HqScopeTab): void => (openTab === tab ? closeScope() : openScope(tab))
  const ctx = contextCount(enabled)
  const estimate = estimateContext(enabled, manifest)

  return (
    <div ref={rowRef} className={styles.row}>
      <div className={styles.chips}>
        <ScopeChip
          ref={(el) => { chipRefs.current.context = el }}
          icon={<Layers size={11} />}
          label="Context"
          count={`${ctx.on}/${ctx.total}`}
          ariaLabel={`Context: ${ctx.on} of ${ctx.total} board sections`}
          open={openTab === 'context'}
          controls={POPOVER_ID}
          onToggle={() => toggle('context')}
        />
        <ScopeChip
          ref={(el) => { chipRefs.current.actions = el }}
          icon={<Zap size={11} />}
          label="Actions"
          count={`${actions.enabledCount}/${MAX_HQ_ACTIONS}`}
          ariaLabel={`Actions: ${actions.enabledCount} of ${MAX_HQ_ACTIONS} enabled`}
          open={openTab === 'actions'}
          controls={POPOVER_ID}
          onToggle={() => toggle('actions')}
        />
      </div>
      {openTab && (
        <ScopePopover
          id={POPOVER_ID}
          tabs={TABS}
          active={openTab}
          onSelect={openScope}
          meter={
            <TokenMeter
              contextTokens={estimate.tokens}
              actionTokens={actions.builtIn ? actions.schemaTokens : 0}
              unmeasured={estimate.unmeasured}
              budget={estimate.budget}
            />
          }
        >
          {openTab === 'context' ? <ContextTab manifest={manifest} /> : <ActionsTab sel={actions} />}
        </ScopePopover>
      )}
    </div>
  )
}
