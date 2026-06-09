import type { FeatureData } from '../dbExplorerData'
import { FeatureCard } from '../FeatureCard'
import styles from './FeatureGrid.module.css'

interface FeatureGridProps {
  features: FeatureData[]
  onCardClick: (feature: FeatureData) => void
}

export function FeatureGrid({ features, onCardClick }: FeatureGridProps): JSX.Element {
  return (
    <div className={styles.grid}>
      {features.map((feature) => (
        <FeatureCard
          key={feature.name}
          feature={feature}
          onClick={() => onCardClick(feature)}
        />
      ))}
    </div>
  )
}
