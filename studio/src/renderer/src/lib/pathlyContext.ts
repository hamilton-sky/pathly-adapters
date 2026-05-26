export interface PathlyContext {
  fsmStage: string
  featureName: string
  skills: string[]
}

const KNOWN_SKILLS = [
  'plan', 'po', 'storm', 'build', 'review', 'test', 'retro',
  'explore', 'debug', 'design', 'fix', 'status', 'log', 'end',
]

export async function buildPathlyContext(): Promise<PathlyContext> {
  try {
    const res = await fetch('http://127.0.0.1:8765/status')
    const data = await res.json() as { current_state?: string; feature?: string }
    return {
      fsmStage: data.current_state ?? 'unknown',
      featureName: data.feature ?? '',
      skills: KNOWN_SKILLS,
    }
  } catch {
    return { fsmStage: 'unknown', featureName: '', skills: KNOWN_SKILLS }
  }
}
