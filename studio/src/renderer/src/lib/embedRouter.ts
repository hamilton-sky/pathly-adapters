import { pipeline, FeatureExtractionPipeline, env } from '@xenova/transformers'
import type { Skill } from './skillsManifest'
import type { MatchResult } from '../types/chat'

// Explicit CDN — never resolve relative to localhost (Vite dev server returns HTML for unknown paths)
env.allowLocalModels = false
env.useBrowserCache = false   // disable cache entirely to avoid stale/corrupt entries in dev

export type EmbedProgressCallback = (progress: number) => void

let embedder: FeatureExtractionPipeline | null = null
let embeddedSkills: Skill[] = []

async function getEmbedder(onProgress?: EmbedProgressCallback): Promise<FeatureExtractionPipeline> {
  if (!embedder) {
    embedder = await pipeline(
      'feature-extraction',
      'Xenova/all-MiniLM-L6-v2',
      {
        progress_callback: (p: Record<string, unknown>) => {
          const progress = typeof p.progress === 'number' ? p.progress : null
          if (progress !== null) {
            onProgress?.(Math.round(progress))
          } else if (p.status === 'ready') {
            onProgress?.(100)
          }
        },
      }
    ) as FeatureExtractionPipeline
  }
  return embedder
}

export async function embed(text: string): Promise<number[]> {
  const ext = await getEmbedder()
  const output = await ext(text, { pooling: 'mean', normalize: true })
  return Array.from(output.data as Float32Array)
}

export function cosineSim(a: number[], b: number[]): number {
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  return denom === 0 ? 0 : dot / denom
}

export async function preEmbedSkills(skills: Skill[], onProgress?: EmbedProgressCallback): Promise<void> {
  const ext = await getEmbedder(onProgress)
  for (const skill of skills) {
    const output = await ext(skill.description, { pooling: 'mean', normalize: true })
    skill.vector = Array.from(output.data as Float32Array)
  }
  embeddedSkills = skills
}

export async function matchIntent(input: string): Promise<MatchResult[]> {
  const inputVec = await embed(input)
  const scored = embeddedSkills
    .filter((s) => s.vector !== undefined)
    .map((s) => ({
      skill: s.name,
      confidence: cosineSim(inputVec, s.vector!),
      command: s.command,
      description: s.description,
    }))
    .sort((a, b) => b.confidence - a.confidence)
  return scored.slice(0, 3)
}
