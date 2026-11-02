import type { ChiefNotice } from '../../../../services/chiefApi'
import s from './ChiefNotices.module.css'

interface Props {
  notices: ChiefNotice[]
}

function questionsLine(n: number): string {
  return `${n} question${n === 1 ? '' : 's'} waiting`
}

/** The chief's runs that ended since the person last looked: run, status, error, cost, questions. */
export function ChiefNotices({ notices }: Props): JSX.Element {
  return (
    <section className={s.notices}>
      <div className={s.heading}>Finished runs</div>
      <ul className={s.list} aria-label="Finished chief runs">
        {notices.map((n) => (
          <li key={n.run_id} className={s.item}>
            <div className={s.row}>
              <span className={s.run} title={n.run_id}>
                {n.kind} · {n.run_id}
              </span>
              <span className={s.status} data-status={n.status}>{n.status}</span>
            </div>
            <div className={s.meta}>
              <span>${n.cost_usd.toFixed(2)}</span>
              {n.open_questions > 0 && (
                <span className={s.questions}>{questionsLine(n.open_questions)}</span>
              )}
            </div>
            {n.error && <div className={s.error}>{n.error}</div>}
          </li>
        ))}
      </ul>
    </section>
  )
}
