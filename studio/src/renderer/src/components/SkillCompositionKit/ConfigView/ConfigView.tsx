import { useState } from 'react'
import type { ConfigLayout, FragmentVM } from '../types'
import { fragmentPurpose, fragmentTokens } from '../data/fragmentMeta'
import { useExpandedRows } from '../hooks/useExpandedRows'
import { FragmentTable } from '../FragmentTable/FragmentTable'
import { FragmentSplit } from '../FragmentSplit/FragmentSplit'
import styles from './ConfigView.module.css'

interface Props {
  skill: string
  included: FragmentVM[]
  allFragments: string[]
  totalTokens: number
  onToggleFragment: (name: string) => void
}

/** The Config view: a read-at-a-glance map of how a skill is assembled from fragments,
 *  with two interchangeable layouts (Table / Split) and inline expand-to-inspect rows. */
export function ConfigView({ skill, included, allFragments, totalTokens, onToggleFragment }: Props): JSX.Element {
  const [layout, setLayout] = useState<ConfigLayout>('table')
  const expand = useExpandedRows(skill)

  const includedNames = new Set(included.map((f) => f.name))
  const available: FragmentVM[] = allFragments
    .filter((n) => !includedNames.has(n))
    .map((name) => ({ order: 0, name, purpose: fragmentPurpose(name), tokens: fragmentTokens(name) }))

  return (
    <div>
      <div className={styles.head}>
        <span className={styles.label}>Assembly order</span>
        <span className={styles.spacer} />
        <span className={styles.layoutLabel}>layout</span>
        <div className={styles.seg} role="tablist">
          <button type="button" role="tab" aria-selected={layout === 'table'} data-active={layout === 'table'} className={styles.segBtn} onClick={() => setLayout('table')}>Table</button>
          <button type="button" role="tab" aria-selected={layout === 'split'} data-active={layout === 'split'} className={styles.segBtn} onClick={() => setLayout('split')}>Split</button>
        </div>
      </div>

      {layout === 'table' ? (
        <FragmentTable included={included} expand={expand} onToggleFragment={onToggleFragment} />
      ) : (
        <FragmentSplit included={included} available={available} expand={expand} onToggleFragment={onToggleFragment} />
      )}
    </div>
  )
}
