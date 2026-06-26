import { Boxes } from 'lucide-react'
import ActionPill from '../../../shared/ActionPill/ActionPill'
import { cliLabel } from '../../../MarkdownEditor/EditorHeader/editorCli'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { DecomposeConfigPopover, MODE_OPTIONS } from './DecomposeConfigPopover/DecomposeConfigPopover'
import { useDecomposePreview } from './hooks/useDecomposePreview'
import { useGoalDecompose } from './hooks/useGoalDecompose'

interface Props {
  goalId: string
  /** Goal text — mirrored into the decompose-prompt preview. */
  goalText: string
}

// Shown on a goal that has no tasks yet — turns the goal into a task DAG via the planner
// (fast) or the consultation flow (deep). Mirrors EvaluateBoardButton: the shared ActionPill
// ([▣ Decompose… 0:03][⚙↔■]), a gear-anchored DecomposeConfigPopover (mode + engine), and a
// SendPreviewModal confirm gate before the run.
export function GoalDecomposeButton({ goalId, goalText }: Props): JSX.Element {
  const d = useGoalDecompose(goalId)

  const modeLabel = MODE_OPTIONS.find((m) => m.value === d.mode)?.label ?? 'Decompose'

  // Faithful preview of the server-assembled decompose directive (recomputed on mode change).
  const previewPrompt = useDecomposePreview(d.mode, goalText)

  return (
    <>
      <ActionPill
        state={d.runState}
        progress={d.progress}
        hasPath
        title={modeLabel}
        runningVerb="Decomposing"
        mainIcon={<Boxes size={13} />}
        idleTip={`Decompose goal — ${modeLabel.toLowerCase()} (${d.mode})`}
        runningTip="Decomposing the goal into a task DAG…"
        ariaName="Decompose"
        onRun={() => d.setConfirmOpen(true)}
        onStop={d.stop}
        configTip="Configure decompose"
        onToggleConfig={() => d.setConfigOpen((v) => !v)}
        gearRef={d.gearRef}
      />

      {d.configOpen && (
        <DecomposeConfigPopover
          anchorEl={d.gearRef.current}
          mode={d.mode}
          selectedCli={d.selectedCli}
          onModeChange={d.setMode}
          onCliChange={d.handleCliChange}
          onRun={() => { d.setConfigOpen(false); d.run() }}
          onClose={() => d.setConfigOpen(false)}
        />
      )}

      {d.confirmOpen && (
        <SendPreviewModal
          title="Decompose"
          engineLabel={cliLabel(d.selectedCli)}
          fileName={goalText.slice(0, 48) || goalId}
          prompt={previewPrompt}
          readOnly
          meta={[{ label: 'Mode', value: modeLabel }]}
          submitLabel="Run Decompose"
          onSubmit={() => { d.setConfirmOpen(false); d.run() }}
          onCancel={() => d.setConfirmOpen(false)}
        />
      )}
    </>
  )
}
