import s from './RadioCard.module.css'

interface Props {
  active: boolean
  label: string
  description: string
  onClick: () => void
}

export function RadioCard({ active, label, description, onClick }: Props): JSX.Element {
  return (
    <div className={`${s.radioCard}${active ? ` ${s.active}` : ''}`} onClick={onClick}>
      <span className={`${s.radioLabel}${active ? ` ${s.active}` : ''}`}>
        <span>{active ? '●' : '○'}</span> {label}
      </span>
      <span className={s.radioDesc}>{description}</span>
    </div>
  )
}
