import { RotateCw } from 'lucide-react'
import ActionPill from '../../../shared/ActionPill/ActionPill'
import { SummaryTargetPopover } from '../cards/MsgCard/ResummarizeButton/SummaryTargetPopover/SummaryTargetPopover'
import { useResummarize } from '../hooks/useResummarize'

interface Props {
  messageId: string
  /** False when the artifact has no path — disables the run button. */
  hasPath: boolean
}

// Full (non-compact) re-summarize ActionPill for the ArtifactModal footer.
// Compact variant lives on artifact cards (ResummarizeButton). Both share
// useResummarize for state + abort handling.
export function ArtifactSummarizePill({ messageId, hasPath }: Props): JSX.Element {
  const r = useResummarize(messageId)
  return (
    <>
      <ActionPill
        state={r.pillState}
        progress={r.progress}
        hasPath={hasPath}
        title="Re-summarize"
        runningVerb="Summarizing"
        mainIcon={<RotateCw size={13} />}
        idleTip="Re-run the AI summary for this artifact"
        runningTip="Summarizing the artifact…"
        ariaName="Re-summarize artifact"
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
