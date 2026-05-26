import { pipeline, FeatureExtractionPipeline } from '@xenova/transformers'
import type { Skill } from './skillsManifest'
import type { MatchResult } from '../store/chatStore'
import { useChatStore } from '../store/chatStore'

let embedder: FeatureExtractionPipeline | null = null
let embeddedSkills: Skill[] = []

async function getEmbedder(): Promise<FeatureExtractionPipeline> {
  if (!embedder) {
    embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2') as FeatureExtractionPipeline
  }
  return embedder
}

async function embed(text: string): Promise<number[]> {
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

export async function preEmbedSkills(skills: Skill[]): Promise<void> {
  const ext = await getEmbedder()
  for (const skill of skills) {
    const output = await ext(skill.description, { pooling: 'mean', normalize: true })
    skill.vector = Array.from(output.data as Float32Array)
  }
  embeddedSkills = skills
  useChatStore.getState().setEmbedReady(true)
}

export async function matchIntent(input: string): Promise<MatchResult[]> {
  const inputVec = await embed(input)
  const scored = embeddedSkills
    .filter((s) => s.vector !== undefined)
    .map((s) => ({
      skill: s.name,
      confidence: cosineSim(inputVec, s.vector!),
      command: s.command,
    }))
    .sort((a, b) => b.confidence - a.confidence)
  return scored.slice(0, 3)
}
