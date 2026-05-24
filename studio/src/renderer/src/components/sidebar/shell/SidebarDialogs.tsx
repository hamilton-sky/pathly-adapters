import { FlowWizard } from '../../FlowWizard'
import { NewItemDialog } from '../../NewItemDialog'
import { DeleteConfirmModal } from '../shared/DeleteConfirmModal'
import type { PathlyItem } from '../../../types'

interface SidebarDialogsProps {
  showFlowWizard: boolean
  showNewItemDialog: boolean
  newItemTarget: { type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null
  confirmDelete: PathlyItem | null
  confirmDeleteFolder: string | null
  confirmDeleteSection: { dir: string; name: string } | null
  onFlowWizardClose: () => void
  onFlowWizardCreated: (filePath: string | undefined) => void
  onNewItemDialogClose: () => void
  onNewItemDialogCreated: (item: PathlyItem) => void
  onConfirmDeleteCancel: () => void
  onConfirmDeleteConfirm: (item: PathlyItem) => void
  onConfirmDeleteFolderCancel: () => void
  onConfirmDeleteFolderConfirm: (folderPath: string) => void
  onConfirmDeleteSectionCancel: () => void
  onConfirmDeleteSectionConfirm: (dir: string) => void
}

export function SidebarDialogs({
  showFlowWizard,
  showNewItemDialog,
  newItemTarget,
  confirmDelete,
  confirmDeleteFolder,
  confirmDeleteSection,
  onFlowWizardClose,
  onFlowWizardCreated,
  onNewItemDialogClose,
  onNewItemDialogCreated,
  onConfirmDeleteCancel,
  onConfirmDeleteConfirm,
  onConfirmDeleteFolderCancel,
  onConfirmDeleteFolderConfirm,
  onConfirmDeleteSectionCancel,
  onConfirmDeleteSectionConfirm,
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

      {confirmDelete && (
        <DeleteConfirmModal
          item={confirmDelete}
          onCancel={onConfirmDeleteCancel}
          onConfirm={() => onConfirmDeleteConfirm(confirmDelete)}
        />
      )}
      {confirmDeleteFolder && (
        <DeleteConfirmModal
          item={{ name: confirmDeleteFolder.split('/').pop() ?? confirmDeleteFolder, path: confirmDeleteFolder, type: 'explore' }}
          onCancel={onConfirmDeleteFolderCancel}
          onConfirm={() => onConfirmDeleteFolderConfirm(confirmDeleteFolder)}
        />
      )}
      {confirmDeleteSection && (
        <DeleteConfirmModal
          item={{ name: confirmDeleteSection.name, path: confirmDeleteSection.dir, type: 'explore' }}
          onCancel={onConfirmDeleteSectionCancel}
          onConfirm={() => onConfirmDeleteSectionConfirm(confirmDeleteSection.dir)}
        />
      )}
    </>
  )
}
