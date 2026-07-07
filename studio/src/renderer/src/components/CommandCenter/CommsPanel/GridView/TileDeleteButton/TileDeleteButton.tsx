import { Trash2 } from 'lucide-react'
import s from './TileDeleteButton.module.css'

interface Props {
  /** Ask to remove this tile. The click is already stopped from reaching the tile
   *  (which would open the detail modal); the caller opens the confirm step. */
  onDelete: () => void
}

// Hover-revealed trash pinned to a tile's top-right corner — the same "remove from
// board" affordance the Messages / Goals / Artifacts cards carry. Shared by every
// grid tile so the markup + styling live in one place; each tile only adds the
// `.tile:hover [data-tile-del]` reveal rule (data attribute, stable across modules).
export function TileDeleteButton({ onDelete }: Props): JSX.Element {
  return (
    <button
      type="button"
      data-tile-del
      className={s.del}
      aria-label="Remove from board"
      title="Remove from board"
      onClick={(e) => {
        e.stopPropagation()
        onDelete()
      }}
    >
      <Trash2 size={12} />
    </button>
  )
}
