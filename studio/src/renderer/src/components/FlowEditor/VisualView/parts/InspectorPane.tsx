import type { Theme } from '../../../../theme'
import type { FlowYaml } from '../../../../types'
import type { FlowValidationIssue } from '../../utils/validateFlow'
import type { PanelDetail } from '../constants'
import { makeVisualViewStyles } from '../VisualView.styles'
import { NodePanel } from '../NodePanel'
import { EdgePanel } from '../EdgePanel'

interface Props {
  detail: PanelDetail
  data: FlowYaml
  onAgentChange: (stateId: string, value: string) => void
  onAdapterChange: (stateId: string, value: string) => void
  onSkillChange: (stateId: string, value: string) => void
  onRename: (oldId: string, newId: string) => void
  onClose: () => void
  onRemoveNode: (stateId: string) => void
  onRemoveEdge: (source: string, target: string) => void
  onAddAction: (source: string, target: string) => void
  onDataChange: (updated: FlowYaml) => void
  onSelectEdge?: (source: string, target: string) => void
  validationIssues: FlowValidationIssue[]
  t: Theme
}

export function InspectorPane({
  detail,
  data,
  onAgentChange,
  onAdapterChange,
  onSkillChange,
  onRename,
  onClose,
  onRemoveNode,
  onRemoveEdge,
  onAddAction,
  onDataChange,
  onSelectEdge,
  validationIssues,
  t,
}: Props): JSX.Element | null {
  const s = makeVisualViewStyles(t)
  if (!detail) return null

  return (
    <div style={s.inspectorPane}>
      {detail.type === 'node' && (
        <NodePanel
          stateId={detail.stateId}
          data={data}
          onAgentChange={onAgentChange}
          onAdapterChange={onAdapterChange}
          onSkillChange={onSkillChange}
          onRename={onRename}
          onClose={onClose}
          onRemove={() => { onRemoveNode(detail.stateId); onClose() }}
          onSelectEdge={onSelectEdge}
          issues={validationIssues}
        />
      )}
      {detail.type === 'edge' && (
        <EdgePanel
          source={detail.source}
          target={detail.target}
          data={data}
          onAddAction={onAddAction}
          onClose={onClose}
          onRemove={() => { onRemoveEdge(detail.source, detail.target); onClose() }}
          onDataChange={onDataChange}
          issues={validationIssues}
        />
      )}
    </div>
  )
}
