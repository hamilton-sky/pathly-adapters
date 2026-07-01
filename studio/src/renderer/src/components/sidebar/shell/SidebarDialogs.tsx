import { FlowWizard } from '../../FlowWizard'
import { NewItemDialog } from '../../NewItemDialog'
import type { PathlyItem } from '../../../types'

interface SidebarDialogsProps {
  showFlowWizard: boolean
  showNewItemDialog: boolean
  newItemTarget: { type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null
  onFlowWizardClose: () => void
  onFlowWizardCreated: (filePath: string | undefined) => void
  onNewItemDialogClose: () => void
  onNewItemDialogCreated: (item: PathlyItem) => void
}

/** Library-tab dialogs: the flow wizard and the new-item (skill/agent/…) dialog. */
export function SidebarDialogs({
  showFlowWizard,
  showNewItemDialog,
  newItemTarget,
  onFlowWizardClose,
  onFlowWizardCreated,
  onNewItemDialogClose,
  onNewItemDialogCreated,
}: SidebarDialogsProps): JSX.Element {
  return (
    <>
      {showFlowWizard && (
        <FlowWizard
          onClose={onFlowWizardClose}
          onCreated={(filePath) => onFlowWizardCreated(filePath)}
        />
      )}
      {showNewItemDialog && newItemTarget && (
        <NewItemDialog
          type={newItemTarget.type}
          dir={newItemTarget.dir}
          onClose={onNewItemDialogClose}
          onCreated={(item) => onNewItemDialogCreated(item)}
        />
      )}
    </>
  )
}
