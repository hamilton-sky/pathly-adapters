import { RotateCw } from 'lucide-react'
import ActionPill from '../../../../../shared/ActionPill/ActionPill'
import SendPreviewModal from '../../../../../shared/SendPreviewModal/SendPreviewModal'
import { cliLabel, type EditorCli } from '../../../../../MarkdownEditor/EditorHeader/editorCli'
import { SummaryTargetPopover } from './SummaryTargetPopover/SummaryTargetPopover'
import { useResummarize } from '../../../hooks/useResummarize'

const STYLE_LABEL: Record<string, string> = {
  gist: 'Gist',
  'topic-map': 'Topic map',
  detailed: 'Detailed',
}

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
  const engineLabel = r.selection.type === 'engine'
    ? cliLabel(r.selection.id as EditorCli)
    : r.selection.id
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
        onRun={r.prepareRun}
        onStop={r.stop}
        configTip="Choose summary depth + AI target"
        onToggleConfig={() => r.setConfigOpen((v) => !v)}
        gearRef={r.gearRef}
      />
      {r.configOpen && (
        <SummaryTargetPopover
          anchorEl={r.gearRef.current}
          value={r.selection}
          onChange={(sel) => { r.setSelection(sel); r.setConfigOpen(false) }}
          style={r.style}
          onStyleChange={r.setStyle}
          note={r.note}
          onNoteChange={r.setNote}
          onClose={() => r.setConfigOpen(false)}
        />
      )}
      {r.confirmOpen && r.preview && (
        <SendPreviewModal
          title="Summarize"
          engineLabel={engineLabel}
          fileName={r.preview.fileName}
          prompt={r.preview.prompt}
          readOnly
          meta={[{ label: 'Depth', value: STYLE_LABEL[r.style] ?? r.style }]}
          submitLabel="Run summary"
          onSubmit={() => { r.setConfirmOpen(false); r.run() }}
          onCancel={() => r.setConfirmOpen(false)}
        />
      )}
    </>
  )
}
