import { BODY_CHIP_ID, FULL_CHIP_ID } from '../chipIds'
import { FragmentChip } from '../FragmentChip/FragmentChip'
import styles from './FragmentChipRow.module.css'

interface Props {
  fragments: string[]
  allFragments: string[]
  activeChipId: string
  onSelectChip: (id: string) => void
  onToggleFragment: (name: string) => void
}

/** Horizontal, horizontally-scrollable row: Skill body chip, one chip per fragment, Full composed chip. */
export function FragmentChipRow({
  fragments,
  allFragments,
  activeChipId,
  onSelectChip,
  onToggleFragment,
}: Props): JSX.Element {
  return (
    <div className={styles.row}>
      <FragmentChip
        kind="body"
        label="Skill body"
        included
        active={activeChipId === BODY_CHIP_ID}
        onSelect={() => onSelectChip(BODY_CHIP_ID)}
      />
      {allFragments.map((name) => (
        <FragmentChip
          key={name}
          kind="fragment"
          label={name}
          included={fragments.includes(name)}
          active={activeChipId === name}
          onSelect={() => onSelectChip(name)}
          onToggle={() => onToggleFragment(name)}
        />
      ))}
      <FragmentChip
        kind="full"
        label="Full composed"
        included
        active={activeChipId === FULL_CHIP_ID}
        onSelect={() => onSelectChip(FULL_CHIP_ID)}
      />
      {allFragments.length === 0 && <span className={styles.emptyNote}>No fragments found</span>}
    </div>
  )
}
