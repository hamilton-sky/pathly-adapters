import { useChatStore } from '../../../../store/chatStore'
import styles from './RouterStatus.module.css'

/** The MiniLM skill router's state — moved here from the composer footer to
 *  free room for the scope chips. The first-load download bar stays above the input. */
export function RouterStatus(): JSX.Element {
  const isEmbedding = useChatStore((s) => s.isEmbedding)
  const embedReady = useChatStore((s) => s.embedReady)
  const embedProgress = useChatStore((s) => s.embedProgress)

  const state = isEmbedding ? 'routing' : embedReady ? 'ready' : 'loading'
  const text = state === 'routing'
    ? 'routing…'
    : state === 'ready'
      ? 'ready'
      : embedProgress > 0 ? `loading ${embedProgress}%` : 'loading…'

  return (
    <div className={styles.status} data-state={state}>
      <span aria-hidden="true">◈</span> MiniLM skill router · {text}
    </div>
  )
}
