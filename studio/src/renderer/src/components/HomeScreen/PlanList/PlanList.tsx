import type { PlanRow } from '../types'
import { FlowTypeBadge } from '../FlowTypeBadge/FlowTypeBadge'
import { FsmBadge } from '../FsmBadge/FsmBadge'
import styles from './PlanList.module.css'

interface PlanListProps {
  plans: PlanRow[]
  onPlanClick: (plan: PlanRow, evt: React.MouseEvent) => void
}

export function PlanList({ plans, onPlanClick }: PlanListProps): JSX.Element {
  if (plans.length === 0) {
    return <div className={styles.empty}>No active topics</div>
  }

  return (
    <div className={styles.list}>
      {plans.map((plan) => (
        <div
          key={`${plan.flowType}:${plan.name}`}
          className={`${styles.row} ${plan.state.toUpperCase() === 'BLOCKED' ? styles.blocked : ''}`}
          onClick={(e) => onPlanClick(plan, e)}
          title={`Open ${plan.name}`}
        >
          <span className={`${styles.planName} ${plan.state.toUpperCase() === 'BLOCKED' ? styles.blockedText : ''}`}>
            {plan.name}
          </span>
          <span className={styles.badges}>
            <FlowTypeBadge flowType={plan.flowType} />
            <FsmBadge state={plan.state} />
          </span>
        </div>
      ))}
    </div>
  )
}
