import { Sparkles } from 'lucide-react'
import ActionPill from '../../../shared/ActionPill/ActionPill'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { FlowGatePreview } from '../../../shared/FlowGatePreview/FlowGatePreview'
import { ProgressSelect } from '../../../shared/ProgressSelect/ProgressSelect'
import { cliLabel } from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { headingLayers } from '../../../../services/skillCompose'
import type { BoardScope } from '../../types'
import { EvalConfigPopover } from './EvalConfigPopover'
import { useDecomposePreview } from './useDecomposePreview'
import { useEvaluateBoardButton } from './hooks/useEvaluateBoardButton'

export interface GoalStub {
  id: string
  text: string
}

interface Props {
  boardKey: string
  /** Goals on this board — used to populate the Target selector in the popover. */
  goals?: GoalStub[]
  /** This board's scope — 'project' routes whole-board decompose into sibling
   *  FEATURES instead of sibling goals. */
  boardScope?: BoardScope
}

// Evaluate the board → propose tasks. Also dispatches per-goal decompose when the
// user picks a specific goal as the target. Uses the shared ActionPill, the same
// run+gear+stop control as the editor's AI Split/Analyze. The gear opens
// EvalConfigPopover (rigor, target, lens, engine). All state + handlers live in
// useEvaluateBoardButton; this component is the JSX shell.
export function EvaluateBoardButton({ boardKey, goals = [], boardScope }: Props): JSX.Element {
  const e = useEvaluateBoardButton(boardKey, boardScope)

  // Decompose-planner preview (goal target): the REAL composed planner prompt (skill + fragments
  // + the decompose task directive), so a Sections trim is meaningful and sent verbatim as
  // prompt_override. Abilities + system-prompts are added in that Sections modal now.
  const goalText = goals.find((g) => g.id === e.targetGoalId)?.text ?? ''
  const decompose = useDecomposePreview(
    e.confirmOpen && e.isGoalTarget,
    e.rigorMode,
    goalText,
    e.targetGoalId,
  )

  return (
    <>
      <ActionPill
        state={e.runState}
        progress={e.progress}
        hasPath
        title={e.activeLabel}
        runningVerb={e.targetGoalId ? 'Planning' : e.activeLabel}
        mainIcon={<Sparkles size={13} />}
        idleTip={e.lensLabel
          ? `Suggest tasks — ${e.lensLabel}`
          : 'Suggest tasks — analyze the whole board and propose concrete tasks'}
        runningTip={e.targetGoalId ? 'Planning goal…' : 'Analyzing the board…'}
        ariaName="Suggest tasks"
        onRun={e.onPillRun}
        onStop={e.handleStop}
        configTip="Configure evaluator"
        onToggleConfig={() => e.setConfigOpen((v) => !v)}
        gearRef={e.gearRef}
      />

      {e.configOpen && (
        <EvalConfigPopover
          anchorEl={e.gearRef.current}
          selectedLens={e.selectedLens}
          lensText={e.lensText}
          extraPrompt={e.extraPrompt}
          selectedCli={e.selectedCli}
          running={e.running}
          goals={goals}
          targetGoalId={e.targetGoalId}
          isProjectBoard={e.isProjectBoard}
          rigorMode={e.rigorMode}
          onSelectLens={e.pickLens}
          onLensTextChange={e.setLensText}
          onExtraPromptChange={e.setExtraPrompt}
          onCliChange={e.handleCliChange}
          onTargetChange={e.setTargetGoalId}
          onRigorChange={e.setRigorMode}
          featureRigor={e.featureRigor}
          onFeatureRigorChange={e.setFeatureRigor}
          onFeatureDecompose={e.requestFeatureDecompose}
          onReset={e.handleReset}
          onRun={e.onConfigRun}
          onClose={() => e.setConfigOpen(false)}
        />
      )}

      {e.confirmOpen && (
        <SendPreviewModal
          title={e.isGoalTarget ? 'Decompose goal' : e.activeLabel}
          engineLabel={cliLabel(e.selectedCli)}
          fileName={boardKey}
          prompt={e.isGoalTarget ? decompose.prompt : e.previewPrompt}
          readOnly
          headingLayers={headingLayers(e.isGoalTarget ? decompose.segments : e.previewSegments)}
          meta={e.isGoalTarget
            ? [{ label: 'Rigor', value: e.rigorMode }]
            : [{ label: 'Lens', value: e.lensLabel ?? 'Built-in evaluator' }]}
          submitLabel={e.isGoalTarget ? 'Run decompose' : 'Suggest tasks'}
          footerSlot={<ProgressSelect value={e.verbosity} onChange={e.setVerbosity} allowInherit label="Board updates" id="eval-progress" />}
          onSubmit={(finalPrompt, sectionsUsed) => e.confirmWholeBoard(finalPrompt, sectionsUsed)}
          onCancel={e.cancelWholeBoard}
        />
      )}

      {e.confirmGoalOpen && e.isGoalTarget && (
        <FlowGatePreview
          flow="consultation"
          boardKey={boardKey}
          interactive={false}
          footerSlot={<ProgressSelect value={e.verbosity} onChange={e.setVerbosity} allowInherit label="Board updates" id="consult-progress" />}
          onConfirm={e.confirmGoal}
          onCancel={e.cancelGoal}
        />
      )}

      {e.confirmFeatureOpen && e.isDecomposeTarget && (
        <FlowGatePreview
          flow={e.isProjectBoard ? 'project-consultation' : 'feature-consultation'}
          boardKey={boardKey}
          interactive={false}
          footerSlot={<ProgressSelect value={e.verbosity} onChange={e.setVerbosity} allowInherit label="Board updates" id="feature-consult-progress" />}
          onConfirm={e.confirmFeature}
          onCancel={e.cancelFeature}
        />
      )}
    </>
  )
}
