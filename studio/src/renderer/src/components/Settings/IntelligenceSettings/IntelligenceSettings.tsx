import { AiTargetSelector } from '../../shared/AiTargetSelector/AiTargetSelector'
import { useDefaultSummaryTarget } from '../hooks/useDefaultSummaryTarget'
import { CodeIntelligenceSettings } from '../CodeIntelligenceSettings'
import s from '../Settings.module.css'

export function IntelligenceSettings(): JSX.Element {
  const { selection, setSelection } = useDefaultSummaryTarget()

  return (
    <>
      <div className={s.section}>
        <div className={s.sectionTitle}>Summaries</div>
        <div className={s.hint}>Default model or CLI engine used to summarize .md artifacts added to boards.</div>
        <div className={s.summaryTarget}>
          <AiTargetSelector
            id="settings-summary-target"
            ariaLabel="Default summary AI target"
            value={selection}
            onChange={setSelection}
            allowOff
          />
        </div>
      </div>

      <CodeIntelligenceSettings />
    </>
  )
}
