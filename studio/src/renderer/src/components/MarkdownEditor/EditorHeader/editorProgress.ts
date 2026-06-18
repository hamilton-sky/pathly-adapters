// Moved to shared/RunPill/progress.ts — re-exported here so imports in
// EditorHeader and SplitPill need no path changes.
export {
  type ActionProgress,
  lastMeaningfulLine,
  fmtElapsed,
  attachProgress,
  useElapsedProgress,
} from '../../shared/RunPill/progress'
