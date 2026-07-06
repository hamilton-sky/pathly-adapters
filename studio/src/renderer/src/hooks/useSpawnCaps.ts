import { useTerminalStore } from '../store/terminalStore'
import { persistCaps } from '../components/CliMonitorBar/SpawnQueuePanel'

// Shared CLI spawn caps — one source of truth for two surfaces. The live values come from the
// main-process scheduler (terminalStore.spawnQueue.caps, pushed via the spawn:state IPC); the
// setter writes through the SAME set-caps IPC + localStorage the monitor's queue panel uses. So
// editing the caps in Settings or in the monitor stays in sync, and the choice persists.
export function useSpawnCaps(): { caps: SpawnCaps; setCap: (patch: Partial<SpawnCaps>) => void } {
  const caps = useTerminalStore((s) => s.spawnQueue.caps)

  function setCap(patch: Partial<SpawnCaps>): void {
    persistCaps({ ...caps, ...patch })
    void window.pathly?.terminal?.queueControl?.({ type: 'set-caps', caps: patch })
  }

  return { caps, setCap }
}
