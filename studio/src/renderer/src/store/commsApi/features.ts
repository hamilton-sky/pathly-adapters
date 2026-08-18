// The feature list and its per-feature enrichment, read DB-first (state-one-authority):
// /db/features rows are the authority, the on-disk tree is only a discovery fallback.

import type { Feature, FeatureStatus, Stage, AgentId } from '../../components/CommandCenter/types'
import { listDir, listDirs } from '../../services/pathlyApi'
import { apiFetch } from '../../lib/config'


interface FeatureState {
  current?: string
}

// FSM state name → kit Stage (the card's 6-stage colour vocabulary).
const STAGE_MAP: Record<string, Stage> = {
  STORM: 'PLANNING', STORMING: 'PLANNING',
  PLAN: 'PLANNING', PLANNING: 'PLANNING',
  DESIGN: 'PLANNING', DESIGNING: 'PLANNING',
  BUILD: 'BUILDING', BUILDING: 'BUILDING',
  REVIEW: 'REVIEWING', REVIEWING: 'REVIEWING',
  TEST: 'TESTING', TESTING: 'TESTING',
  RETRO: 'RETRO', RETROSPECTIVE: 'RETRO',
  DONE: 'DONE',
}

function toStage(current: string | undefined): Stage {
  if (!current) return 'PLANNING'
  return STAGE_MAP[current.toUpperCase()] ?? 'PLANNING'
}

const STAGE_AGENT: Record<Stage, AgentId> = {
  PLANNING: 'architect',
  BUILDING: 'builder',
  REVIEWING: 'reviewer',
  TESTING: 'tester',
  RETRO: 'retro',
  DONE: 'retro',
}

// An open feedback file means the stage is blocked on a human/agent response.
const BLOCKER_FILES = new Set([
  'REVIEW_FAILURES.md', 'TEST_FAILURES.md',
  'HUMAN_QUESTIONS.md', 'IMPL_QUESTIONS.md', 'DESIGN_QUESTIONS.md',
])

// ── DB-first feature map (state-one-authority) ────────────────────────
// One /db/features fetch per burst — replaces the per-feature STATE.json /
// EVENTS.jsonl mirror reads. The short TTL dedupes loadFeatures' Promise.all
// fan-out into a single HTTP call; pass { fresh: true } to bypass it.
let dbFeatureMapCache: { root: string; at: number; map: Promise<Map<string, DbFeature>> } | null = null
const DB_FEATURE_MAP_TTL_MS = 2000

export function fetchDbFeatureMap(
  projectRoot: string,
  opts?: { fresh?: boolean },
): Promise<Map<string, DbFeature>> {
  const now = Date.now()
  if (
    !opts?.fresh &&
    dbFeatureMapCache &&
    dbFeatureMapCache.root === projectRoot &&
    now - dbFeatureMapCache.at < DB_FEATURE_MAP_TTL_MS
  ) {
    return dbFeatureMapCache.map
  }
  const map = window.pathly.db
    .features(projectRoot)
    .then((rows) => new Map((rows ?? []).map((r) => [r.feature, r])))
    .catch(() => new Map<string, DbFeature>())
  dbFeatureMapCache = { root: projectRoot, at: now, map }
  return map
}

/** Resolve the storage path for a feature. Mirrors _resolve_storage_path in fsm_ops.py:
 *  the feature-centric home pathly/features/<id>/ wins, then new-style pathly/<id>/.
 *  Existence is probed via container listings — never a STATE.json mirror read
 *  (state-one-authority: runtime state lives in the DB). */
export async function resolveFeaturePath(projectPath: string, featureId: string): Promise<string> {
  const featureDir = `${projectPath}/pathly/features/${featureId}`
  const featureNames = await listDirs(`${projectPath}/pathly/features`).catch(() => [] as string[])
  if (featureNames.includes(featureId)) return featureDir
  const topLevelNames = await listDirs(`${projectPath}/pathly`).catch(() => [] as string[])
  if (topLevelNames.includes(featureId)) return `${projectPath}/pathly/${featureId}`
  // Default to the feature-centric home (legacy pathly/plans/<id>/ fallback removed post-migration).
  return featureDir
}

/** A feature's current stage — from its DB-first /db/features row (state-one-authority). */
export async function fetchFeatureState(projectPath: string, featureId: string): Promise<FeatureState | null> {
  const row = (await fetchDbFeatureMap(projectPath)).get(featureId)
  if (!row) return null
  return { current: row.state !== 'UNKNOWN' ? row.state : undefined }
}

/** A feature is blocked when its feedback/ folder holds an open failure/question file. */
export async function featureBlocked(projectPath: string, featureId: string): Promise<boolean> {
  try {
    const base = await resolveFeaturePath(projectPath, featureId)
    const files = await listDir(`${base}/feedback`).catch(() => [] as string[])
    return files.some((f) => BLOCKER_FILES.has(f))
  } catch {
    return false
  }
}

function summarize(agent: string | undefined, summary: string): string {
  const clean = summary.replace(/\s+/g, ' ').trim()
  const text = clean.length > 160 ? `${clean.slice(0, 159)}…` : clean
  return agent ? `${agent}: ${text}` : text
}

/** Latest AGENT_DONE summary — from the DB row's last_summary (state-one-authority);
 *  the card's "last activity" line. */
export async function fetchLastSummary(projectPath: string, featureId: string): Promise<string> {
  const row = (await fetchDbFeatureMap(projectPath)).get(featureId)
  if (!row?.last_summary?.trim()) return ''
  return summarize(undefined, row.last_summary)
}

export function buildFeature(
  id: string,
  state?: FeatureState | null,
  blocked = false,
  last = '',
): Feature {
  const stage = toStage(state?.current)
  const status: FeatureStatus = stage === 'DONE' ? 'done' : blocked ? 'blocked' : 'idle'
  return {
    id,
    stage,
    status,
    agent: STAGE_AGENT[stage],
    last,
    scope: { feature: true, project: true, global: true },
  }
}
