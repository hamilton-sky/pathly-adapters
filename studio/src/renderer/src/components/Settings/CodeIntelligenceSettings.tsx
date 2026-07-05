import { RadioCard } from './RadioCard'
import { useCodeContextSettings } from './hooks/useCodeContextSettings'
import s from './CodeIntelligenceSettings.module.css'
import ss from './Settings.module.css'

export function CodeIntelligenceSettings(): JSX.Element {
  const { backend, reindex, tool, setBackend, setReindex, setTool } = useCodeContextSettings()

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Code Intelligence</div>

      <div className={s.subLabel}>Backend</div>
      <div className={ss.radioGroup}>
        <RadioCard
          active={backend === 'off'}
          label="Off"
          description="No code graph"
          onClick={() => setBackend('off')}
        />
        <RadioCard
          active={backend === 'cli'}
          label="On"
          description="CLI-backed code graph"
          onClick={() => setBackend('cli')}
        />
      </div>

      <div className={s.subLabel}>Re-index</div>
      <div className={ss.hint}>How often Pathly refreshes the code graph</div>
      <div className={ss.radioGroup}>
        <RadioCard
          active={reindex === 'off'}
          label="Off"
          description="Never re-index"
          onClick={() => setReindex('off')}
        />
        <RadioCard
          active={reindex === 'stage'}
          label="After every stage"
          description="Re-index at stage end"
          onClick={() => setReindex('stage')}
        />
        <RadioCard
          active={reindex === 'auto'}
          label="Auto"
          description="Re-index when files change"
          onClick={() => setReindex('auto')}
        />
      </div>

      <div className={s.subLabel}>Tool</div>
      <div className={ss.radioGroup}>
        <RadioCard
          active={tool === 'codebase-memory-mcp'}
          label="codebase-memory-mcp"
          description="Code knowledge graph — symbols, callers/callees, impact (158 languages)"
          onClick={() => setTool('codebase-memory-mcp')}
        />
      </div>
    </div>
  )
}
