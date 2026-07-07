import type { BandKey } from '../gridBands'
import s from './BandHeader.module.css'

interface Props {
  kind: BandKey
  label: string
  count: number
  hint?: string
}

// Sticky band label: a kind-coloured square, the label, an optional muted hint,
// and a right-aligned mono count badge (consistent across every band).
export function BandHeader({ kind, label, count, hint }: Props): JSX.Element {
  return (
    <div className={s.header}>
      <span className={s.dot} data-kind={kind} />
      <span className={s.label}>{label}</span>
      {hint ? <span className={s.hint}>{hint}</span> : null}
      <span className={s.count}>{count}</span>
    </div>
  )
}
