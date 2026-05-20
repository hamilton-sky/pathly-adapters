import { ReactFlowProvider } from 'reactflow'
import type { FlowYaml } from '../../../types'
import { VisualViewInner } from './VisualViewInner'

export interface VisualViewProps {
  data: FlowYaml
  onChange: (updated: FlowYaml) => void
  onSave: () => void
  tab: 'visual' | 'yaml'
  onTabClick: (t: 'visual' | 'yaml') => void
}

export function VisualView(props: VisualViewProps): JSX.Element {
  return (
    <ReactFlowProvider>
      <VisualViewInner {...props} />
    </ReactFlowProvider>
  )
}
