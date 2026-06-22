import { useEffect, useState } from 'react'
import { apiGetSummaryBackend, apiSetSummaryBackend } from '../../store/commsApi'
import { RadioCard } from './RadioCard'
import ss from './Settings.module.css'

const OPTIONS: Array<{ value: string; label: string; description: string }> = [
  { value: 'minilm', label: 'Off',   description: 'Keep filename/title only' },
  { value: 'ollama', label: 'Local', description: 'Ollama (runs on-device)' },
  { value: 'haiku',  label: 'Haiku', description: 'claude-haiku (API call)' },
]

export function SummarySettings(): JSX.Element {
  const [backend, setBackend] = useState<string>('minilm')

  useEffect(() => {
    void apiGetSummaryBackend().then(setBackend)
  }, [])

  function handleSelect(value: string): void {
    setBackend(value)
    void apiSetSummaryBackend(value)
  }

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Summaries</div>
      <div className={ss.hint}>
        Auto-summarize .md artifacts added to comms boards. Local = Ollama, Haiku = claude-haiku. Off keeps only the filename/title.
      </div>
      <div className={ss.radioGroup}>
        {OPTIONS.map((opt) => (
          <RadioCard
            key={opt.value}
            active={backend === opt.value}
            label={opt.label}
            description={opt.description}
            onClick={() => handleSelect(opt.value)}
          />
        ))}
      </div>
    </div>
  )
}
