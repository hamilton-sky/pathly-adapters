import { RotateCw } from 'lucide-react'
import ActionPill from '../../../../../shared/ActionPill/ActionPill'
import { SummaryTargetPopover } from './SummaryTargetPopover/SummaryTargetPopover'
import { useResummarize } from '../../../hooks/useResummarize'

interface Props {
  /** The artifact message id (resolves to its comms_artifacts row + saved target). */
  messageId: string
}

// Compact [↻|⚙↔■] ActionPill on artifact cards. The gear opens a per-artifact
// AiTargetSelector; while running ⚙ becomes ■ (stop). Full-label variant lives
// in ArtifactSummarizePill (ArtifactModal footer).
export function ResummarizeButton({ messageId }: Props): JSX.Element {
  const r = useResummarize(messageId)
  return (
    <>
      <ActionPill
        state={r.pillState}
        progress={r.progress}
        hasPath
        title="Summarize"
        runningVerb="Summarizing"
        mainIcon={<RotateCw size={12} />}
        idleTip="Re-summarize this artifact"
        runningTip="Running the AI summary…"
        ariaName="Re-summarize"
        onRun={r.run}
        onStop={r.stop}
        configTip="Choose AI target for this artifact"
        onToggleConfig={() => r.setConfigOpen((v) => !v)}
        gearRef={r.gearRef}
        compact
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
