import { useState } from 'react'
import { CardHeader } from '../CardHeader/CardHeader'
import { PlanList } from '../PlanList/PlanList'
import { CardFooter } from '../CardFooter/CardFooter'
import { getCardStatus } from '../utils'
import type { ProjectEntry } from '../../../types'
import type { PlanRow } from '../types'
import styles from './ProjectCard.module.css'

interface ProjectCardProps {
  project: ProjectEntry
  plans: PlanRow[]
  allPlans: PlanRow[]
  index: number
  onOpen: (topicName?: string, evt?: React.MouseEvent) => void
  onPin: () => void
  onRemove: () => void
}

export function ProjectCard({ project, plans, allPlans, index, onOpen, onPin, onRemove }: ProjectCardProps): JSX.Element {
  const [isCardHovered, setIsCardHovered] = useState(false)
  const status = getCardStatus(allPlans)

  return (
    <div
      data-testid="homescreen-project-card"
      className={styles.card}
      data-status={status}
      style={{ '--anim-delay': `${80 + index * 55}ms` } as React.CSSProperties}
      onMouseEnter={() => setIsCardHovered(true)}
      onMouseLeave={() => setIsCardHovered(false)}
    >
      <CardHeader
        project={project}
        hasBorder={plans.length > 0}
        isCardHovered={isCardHovered}
        onPin={onPin}
        onRemove={onRemove}
      />
      <PlanList
        plans={plans}
        onPlanClick={(plan, e) => onOpen(plan.name, e)}
      />
      <CardFooter
        topicCount={allPlans.length}
        lastOpened={project.lastOpened}
        onOpen={(e) => onOpen(undefined, e)}
      />
    </div>
  )
}
