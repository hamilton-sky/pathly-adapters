import { Check } from 'lucide-react'
import type { FlowDef } from '../flowCatalog'
import s from './FlowDiagram.module.css'

interface Props {
  flow: FlowDef
}

// Read-only preview of a flow: a one-line blurb + the ordered stage pipeline
// (state · role · the skill/agent that runs it), drawn as a connected rail.
export function FlowDiagram({ flow }: Props): JSX.Element {
  return (
    <section className={s.diagram} aria-label={`${flow.label} preview`}>
      <p className={s.blurb}>{flow.blurb}</p>
      <ol className={s.nodes}>
        {flow.nodes.map((n) => (
          <li key={n.state} className={s.node}>
            <span className={s.dot} data-role={n.role} />
            <div className={s.main}>
              <span className={s.state}>{n.state}</span>
              <span className={s.role}>{n.terminal ? 'complete' : n.role}</span>
            </div>
            {n.terminal
              ? <Check size={12} className={s.doneIcon} />
              : n.agent ? <code className={s.agent}>{n.agent}</code> : null}
          </li>
        ))}
      </ol>
      {flow.loops ? <p className={s.loops}>↻ {flow.loops}</p> : null}
    </section>
  )
}
