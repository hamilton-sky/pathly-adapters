import type { ChiefSession } from '../../../../services/chiefApi'
import { tierLabel, tierSummary } from '../chiefLauncherUtils'
import s from './OpenChiefCard.module.css'

type OpenSession = Extract<ChiefSession, { open: true }>

interface Props {
  session: OpenSession
  busy: boolean
  onShowTab: () => void
  onClose: () => void
}

/** What the launcher shows while the project already has a chief: one per project. */
export function OpenChiefCard({ session, busy, onShowTab, onClose }: Props): JSX.Element {
  const runs = `${session.runs_started} of ${session.max_runs_per_session} runs started`
  return (
    <div className={s.card}>
      <div className={s.title}>
        Chief · {tierLabel(session.tier)} is open ({session.engine})
      </div>
      <div className={s.detail}>{tierSummary(session.tier)}</div>
      {session.tier === 'operator' && <div className={s.detail}>{runs}</div>}
      <div className={s.actions}>
        <button type="button" className={s.secondary} onClick={onShowTab}>
          Show tab
        </button>
        <button type="button" className={s.danger} disabled={busy} onClick={onClose}>
          Close chief
        </button>
      </div>
    </div>
  )
}
