import type { HqActionCard } from '../../../store/chatStore'
import { canRun, cancelActionCard, runActionCard } from '../actionCards'
import { ActionCard } from './ActionCard/ActionCard'
import styles from './ActionCards.module.css'

/** The confirm cards an HQ answer proposed, in order (local-operator). */
export function ActionCards({ messageId, cards }: { messageId: string; cards: HqActionCard[] }): JSX.Element {
  return (
    <div className={styles.list}>
      {cards.map((card, i) => (
        <ActionCard
          key={card.id}
          card={card}
          runnable={canRun(cards, i)}
          onRun={() => { void runActionCard(messageId, card) }}
          onCancel={() => cancelActionCard(messageId, card)}
        />
      ))}
    </div>
  )
}
