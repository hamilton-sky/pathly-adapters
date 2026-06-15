import type { PathlyItem } from '../../../types'
import { ConfirmModal } from '../../shared/ConfirmModal/ConfirmModal'

interface Props {
  item: PathlyItem
  onCancel: () => void
  onConfirm: () => void
}

export function DeleteConfirmModal({ item, onCancel, onConfirm }: Props): JSX.Element {
  return (
    <ConfirmModal
      title={<>Delete <strong>{item.name}</strong>?</>}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  )
}
