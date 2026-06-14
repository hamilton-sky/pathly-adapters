export { DraftDiffViewer } from './DraftDiffViewer/DraftDiffViewer'
export type { DraftDiffViewerProps } from './DraftDiffViewer/DraftDiffViewer'

// Layout components
export { DraftHunkList } from './DraftHunkList/DraftHunkList'
export { DraftHunkCard } from './DraftHunkCard/DraftHunkCard'
export { DraftTriageList } from './DraftTriageList/DraftTriageList'
export { DraftTriageRow } from './DraftTriageRow/DraftTriageRow'
export { DraftPreviewPanel } from './DraftPreviewPanel/DraftPreviewPanel'
export { CodeDiffView } from './CodeDiffView/CodeDiffView'
export { DraftEditView } from './DraftEditView/DraftEditView'
export { SplitDiff } from './SplitDiff/SplitDiff'
export { UnifiedDiff } from './UnifiedDiff/UnifiedDiff'
export { DraftDiffFooter } from './DraftDiffFooter/DraftDiffFooter'
export { DiffCodeBlock } from './DiffCodeBlock/DiffCodeBlock'
export { default as MarkdownRenderer } from './MarkdownRenderer/MarkdownRenderer'

// Reusable atoms
export { StatusBadge } from './StatusBadge/StatusBadge'
export { AcceptToggleChip } from './AcceptToggleChip/AcceptToggleChip'
export { ViewToggle } from './ViewToggle/ViewToggle'
export { CardsIcon, ListIcon, CodeDiffIcon, EditIcon, Chevron } from './icons/Icons'

// Hooks
export { useDraftDiff, reconstruct } from './useDraftDiff'
export type { DiffHunk, HunkStatus, UseDraftDiff } from './useDraftDiff'
export { useViewMode } from './useViewMode'
export type { ViewMode } from './useViewMode'

// Diff + label utilities
export { computeWordDiff, computeLineDiff, countWordChanges } from './diffUtils'
export type { DiffLine, WordToken, DiffOpType, WordChangeCount } from './diffUtils'
export { statusBadgeLabel, acceptChipLabel, displayHeading, previewText } from './hunkLabels'
export {
  buildDocument,
  fileDiffOps,
  diffStats,
  toSplitRows,
  toUnifiedRows,
} from './fileDiffUtils'
export type { SplitRow, UnifiedRow, FileDiffStats, DocSide, SplitCellType } from './fileDiffUtils'
