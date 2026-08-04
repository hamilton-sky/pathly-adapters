import s from './KindBadge.module.css'

interface Props {
  /** flow | single | loop | decompose. */
  kind: string
}

// Tinted uppercase mono label for a run's KIND (how it runs). Mirrors Monitor's CategoryBadge
// recipe (data-* → color-mix tint), but LOCAL to the run page so it can carry 'decompose' without
// widening Monitor's EngineCategory union (HANDOFF §E / AC-7: don't touch Monitor).
export function KindBadge({ kind }: Props): JSX.Element {
  return (
    <span className={s.badge} data-kind={kind}>
      {kind}
    </span>
  )
}
