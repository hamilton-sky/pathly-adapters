import { IconArrow } from '../icons'
import { timeAgo } from '../utils'
import styles from './CardFooter.module.css'

interface CardFooterProps {
  topicCount: number
  lastOpened: number
  onOpen: (evt: React.MouseEvent) => void
}

export function CardFooter({ topicCount, lastOpened, onOpen }: CardFooterProps): JSX.Element {
  return (
    <div className={styles.footer}>
      <span className={styles.meta}>
        {topicCount} topic{topicCount !== 1 ? 's' : ''} · {timeAgo(lastOpened)}
      </span>
      <button
        type="button"
        data-testid="homescreen-open-btn"
        className={styles.openBtn}
        onClick={onOpen}
        title="Open project"
      >
        <IconArrow />
        Open
      </button>
    </div>
  )
}
