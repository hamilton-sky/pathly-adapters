import { Star } from 'lucide-react'
import { IconClose } from '../icons'
import type { ProjectEntry } from '../../../types'
import styles from './CardHeader.module.css'

interface CardHeaderProps {
  project: ProjectEntry
  hasBorder: boolean
  isCardHovered: boolean
  onPin: () => void
  onRemove: () => void
}

export function CardHeader({ project, hasBorder, isCardHovered, onPin, onRemove }: CardHeaderProps): JSX.Element {
  return (
    <div className={`${styles.header} ${hasBorder ? styles.withBorder : ''}`}>
      <div className={styles.titleGroup}>
        <span className={styles.name}>{project.name}</span>
        <span className={styles.path}>{project.path}</span>
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          aria-label={project.pinned ? 'Unpin project' : 'Pin project'}
          className={`${styles.pinBtn} ${project.pinned ? styles.pinned : ''} ${(isCardHovered || project.pinned) ? styles.visible : ''}`}
          onClick={(e) => { e.stopPropagation(); onPin() }}
        >
          <Star size={12} fill={project.pinned ? 'currentColor' : 'none'} />
        </button>
        <button
          type="button"
          className={`${styles.removeBtn} ${isCardHovered ? styles.visible : ''}`}
          onClick={onRemove}
          aria-label={`Remove ${project.name} from list`}
          title="Remove from list"
        >
          <IconClose />
        </button>
      </div>
    </div>
  )
}
