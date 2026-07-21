import { useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Columns3, Rows3, Sparkles, X } from 'lucide-react'
import { PromptBanner } from '../PromptPreview/PromptPreview'
import SkillSplitModal, { cellsToMarkdown } from '../SkillSplitModal/SkillSplitModal'
import { headingLayers } from '../../../services/skillCompose'
import { FlowGateStepper } from './FlowGateStepper/FlowGateStepper'
import { useFlowGateStages } from './useFlowGateStages'
import { useFlowGateState } from './useFlowGateState'
import { PromptCostMeter } from '../PromptCostMeter/PromptCostMeter'
import { estimateInputCost, estimateTokens } from '../PromptCostMeter/promptCost'
import styles from './FlowGatePreview.module.css'

interface Props {
  /** Flow key/name this gate previews and, on confirm, runs — e.g. 'team'. */
  flow: string
  /** Board key the flow runs on — shown in the meta row. */
  boardKey: string
  /** Run mode — shown in the meta row (interactive terminal vs. headless). */
  interactive: boolean
  /** Confirm — receives the {state: prompt} override map for sectionsUsed stages only. */
  onConfirm: (overrides: Record<string, string>) => void
  onCancel: () => void
  /** Optional controls rendered in the footer above the buttons — e.g. the board-updates
   *  verbosity picker the consultation gates carry (mirrors SendPreviewModal's footerSlot). */
  footerSlot?: ReactNode
}

/**
 * Flow-specific gate preview — the multi-stage analogue of SendPreviewModal. A vertical
 * stepper on top selects which stage's composed prompt the banner + Sections below show;
 * confirming collects only the Sections-confirmed stages into a transient override map
 * (DESIGN.md ss2) and hands it to onConfirm. Run-agnostic — it never starts a run itself,
 * so later entry points (goal-executor, consultation-in-Evaluate) can reuse it with their
 * own onConfirm.
 */
export function FlowGatePreview({ flow, boardKey, interactive, onConfirm, onCancel, footerSlot }: Props): JSX.Element {
  const { steps, stageOf, loading } = useFlowGateStages(flow)
  const gate = useFlowGateState(steps, stageOf)
  const [splitOpen, setSplitOpen] = useState(false)
  // Stepper layout — remembered across opens so it stays how you left it.
  const [orientation, setOrientation] = useState<'vertical' | 'horizontal'>(
    () => (localStorage.getItem('pathly:flowGateOrientation') === 'horizontal' ? 'horizontal' : 'vertical'),
  )
  function toggleOrientation(): void {
    setOrientation((o) => {
      const next = o === 'vertical' ? 'horizontal' : 'vertical'
      try { localStorage.setItem('pathly:flowGateOrientation', next) } catch { /* localStorage may be unavailable */ }
      return next
    })
  }

  const selected = gate.selectedState
  const selectedStage = stageOf(selected)
  const selectedText = gate.text[selected] ?? ''

  // Estimated input cost of the WHOLE flow — every stage's effective (possibly-trimmed) prompt,
  // each priced at its own role's model rate. Recomputed each render off gate.text so trims/edits
  // update it live. Cheap (sum of char lengths over a handful of stages) → no memo needed.
  let flowTokens = 0
  let flowCost = 0
  for (const step of steps) {
    const t = gate.text[step.state] ?? ''
    flowTokens += estimateTokens(t)
    flowCost += estimateInputCost(t, { role: step.role })
  }

  return createPortal(
    <div className={styles.backdrop} onClick={onCancel}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="flow-gate-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.titleWrap}>
            <span id="flow-gate-title" className={styles.title}>{flow}</span>
            <span className={styles.meta}>
              <span className={styles.metaItem}>Board: {boardKey}</span>
              <span className={styles.metaItem}>{interactive ? 'Interactive' : 'Headless'}</span>
            </span>
          </div>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={toggleOrientation}
            aria-label={orientation === 'vertical' ? 'Switch to horizontal layout' : 'Switch to vertical layout'}
            title={orientation === 'vertical' ? 'Horizontal layout' : 'Vertical layout'}
          >
            {orientation === 'vertical' ? <Columns3 size={15} /> : <Rows3 size={15} />}
          </button>
          <button type="button" className={styles.closeBtn} onClick={onCancel} aria-label="Cancel">
            <X size={15} />
          </button>
        </div>

        <div className={styles.stepperRegion}>
          {loading ? (
            <p className={styles.loading}>Composing stages…</p>
          ) : (
            <FlowGateStepper steps={steps} selectedState={selected} onSelect={gate.selectStage} orientation={orientation} />
          )}
        </div>

        <div className={styles.bannerWrap}>
          <PromptBanner
            key={selected}
            editable
            editValue={selectedText}
            onEditChange={(v) => gate.editText(selected, v)}
          />
        </div>

        {footerSlot && <div className={styles.footerSlot}>{footerSlot}</div>}
        <div className={styles.footer}>
          {!loading && steps.length > 0 && (
            <PromptCostMeter tokens={flowTokens} cost={flowCost} prefix="flow" />
          )}
          <button
            type="button"
            className={styles.quietBtn}
            onClick={() => setSplitOpen(true)}
            disabled={!selected}
            title="Include or exclude prompt sections for this stage, this run only"
          >
            <Rows3 size={13} /> Sections
          </button>
          <button type="button" className={styles.quietBtn} onClick={onCancel}>Cancel</button>
          <button type="button" className={styles.runBtn} onClick={() => onConfirm(gate.buildOverrides())}>
            <Sparkles size={14} /> Run flow
          </button>
        </div>
      </div>

      {splitOpen && selectedStage && (
        <SkillSplitModal
          rawContent={selectedText}
          title={`Configure sections — ${selected}`}
          subtitle="Include/exclude sections and add abilities or system-prompts for THIS stage, this run only. Create reusable ones in the Library."
          confirmLabel="Use these sections"
          hideInsertOne
          assemble
          costCtx={{ role: selectedStage.role }}
          headingLayers={headingLayers(selectedStage.segments)}
          onConfirm={(cells) => { gate.applySections(selected, cellsToMarkdown(cells)); setSplitOpen(false) }}
          onInsertOne={() => setSplitOpen(false)}
          onClose={() => setSplitOpen(false)}
        />
      )}
    </div>,
    document.body,
  )
}
