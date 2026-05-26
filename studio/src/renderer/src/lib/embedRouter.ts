import { pipeline, FeatureExtractionPipeline, env } from '@xenova/transformers'
import type { Skill } from './skillsManifest'
import type { MatchResult } from '../types/chat'

// Force transformers.js to fetch from HuggingFace CDN directly,
// not through the Vite dev server (which returns HTML for unknown paths).
env.allowLocalModels = false
env.useBrowserCache = true

// Clear corrupted cache entries (HTML pages stored instead of model weights).
// Runs once at module load — harmless if cache is clean.
async function purgeBadCache(): Promise<void> {
  try {
    const cacheNames = await caches.keys()
    for (const name of cacheNames) {
      if (!name.includes('transformers')) continue
      const cache = await caches.open(name)
      const keys = await cache.keys()
      for (const req of keys) {
        const res = await cache.match(req)
        const ct = res?.headers.get('content-type') ?? ''
        if (ct.includes('text/html')) {
          await cache.delete(req)
        }
      }
    }
  } catch { /* cache API unavailable — skip */ }
}
purgeBadCache()

export type EmbedProgressCallback = (progress: number) => void

let embedder: FeatureExtractionPipeline | null = null
let embeddedSkills: Skill[] = []

async function getEmbedder(onProgress?: EmbedProgressCallback): Promise<FeatureExtractionPipeline> {
  if (!embedder) {
    embedder = await pipeline(
      'feature-extraction',
      'Xenova/all-MiniLM-L6-v2',
      {
        progress_callback: (p: { status: string; progress?: number }) => {
          // @xenova/transformers fires status='progress' (not 'downloading')
          if (p.status === 'progress' && typeof p.progress === 'number') {
            onProgress?.(Math.round(p.progress))
          } else if (p.status === 'done' || p.status === 'ready') {
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
