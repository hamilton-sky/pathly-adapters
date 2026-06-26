import { RotateCw } from 'lucide-react'
import ActionPill from '../../../../../shared/ActionPill/ActionPill'
import { SummaryTargetPopover } from './SummaryTargetPopover/SummaryTargetPopover'
import { useResummarize } from '../../../hooks/useResummarize'

interface Props {
  /** The artifact message id (resolves to its comms_artifacts row + saved target). */
  messageId: string
  /** False when the artifact has no path — disables the run button. Defaults true
   *  (artifact cards always have a path; the modal passes the computed value). */
  hasPath?: boolean
}

// The one summarize pill used everywhere (artifact cards + ArtifactModal footer):
// a full [↻ Summarize · timer][⚙↔■] ActionPill, matching the Decompose/Evaluate
// pills for a single consistent style. The gear opens a per-artifact AiTargetSelector;
// while running ⚙ becomes ■ (stop). State + abort live in useResummarize.
export function ResummarizeButton({ messageId, hasPath = true }: Props): JSX.Element {
  const r = useResummarize(messageId)
  return (
    <>
      <ActionPill
        state={r.pillState}
        progress={r.progress}
        hasPath={hasPath}
        title="Summarize"
        runningVerb="Summarizing"
        mainIcon={<RotateCw size={13} />}
        idleTip="Re-summarize this artifact"
        runningTip="Running the AI summary…"
        ariaName="Re-summarize"
        onRun={r.run}
        onStop={r.stop}
        configTip="Choose AI target for this artifact"
        onToggleConfig={() => r.setConfigOpen((v) => !v)}
        gearRef={r.gearRef}
      />
      {r.configOpen && (
        <SummaryTargetPopover
          anchorEl={r.gearRef.current}
          value={r.selection}
          onChange={(sel) => { r.setSelection(sel); r.setConfigOpen(false) }}
          onClose={() => r.setConfigOpen(false)}
        />
      )}
    </>
  )
}
