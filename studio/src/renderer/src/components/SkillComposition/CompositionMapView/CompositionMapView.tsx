import { Badge } from '../../ui'
import { BODY_CHIP_ID, FULL_CHIP_ID } from '../chipIds'
import { CompositionStep } from './CompositionStep/CompositionStep'
import { fragmentPurpose } from './fragmentMeta'
import styles from './CompositionMapView.module.css'

interface Props {
  skill: string
  included: string[]
  allFragments: string[]
  source: 'manifest' | 'override'
  composedTokens: number
  onToggleFragment: (name: string) => void
  onInspect: (chipId: string) => void
}

/**
 * The "Config" view — a stylish, read-at-a-glance map of how a skill is assembled from
 * fragments (the composition.yaml row for this skill, rendered as a recipe rather than raw
 * YAML). Shows the ordered stack (body → included fragments → composed prompt) plus the
 * available-to-add fragments, each toggleable inline.
 */
export function CompositionMapView({
  skill,
  included,
  allFragments,
  source,
  composedTokens,
  onToggleFragment,
  onInspect,
}: Props): JSX.Element {
  const available = allFragments.filter((f) => !included.includes(f))

  return (
    <div className={styles.root}>
      <div className={styles.intro}>
        <span className={styles.introLabel}>Assembly order</span>
        <Badge variant={source === 'override' ? 'integration' : 'neutral'} label={source} />
        <span className={styles.count}>
          {included.length} of {allFragments.length} fragments
        </span>
      </div>

      <div className={styles.stack}>
        <CompositionStep kind="body" name="Skill body" included onSelect={() => onInspect(BODY_CHIP_ID)} />
        {included.map((name, i) => (
          <CompositionStep
            key={name}
            kind="fragment"
            order={i + 1}
            name={name}
            purpose={fragmentPurpose(name)}
            included
            onToggle={() => onToggleFragment(name)}
            onSelect={() => onInspect(name)}
          />
        ))}
        <CompositionStep
          kind="result"
          name="Composed prompt"
          included
          tokensLabel={`≈ ${composedTokens} tokens`}
          onSelect={() => onInspect(FULL_CHIP_ID)}
        />
      </div>

      {available.length > 0 && (
        <>
          <div className={styles.subhead}>Available to add</div>
          <div className={styles.stack} data-available="true">
            {available.map((name) => (
              <CompositionStep
                key={name}
                kind="fragment"
                name={name}
                purpose={fragmentPurpose(name)}
                included={false}
                onToggle={() => onToggleFragment(name)}
                onSelect={() => onInspect(name)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
