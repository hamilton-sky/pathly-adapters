export { DraftDiffViewer } from './DraftDiffViewer/DraftDiffViewer'
export type { DraftDiffViewerProps } from './DraftDiffViewer/DraftDiffViewer'

// Layout components
export { DraftHunkList } from './DraftHunkList/DraftHunkList'
export { DraftHunkCard } from './DraftHunkCard/DraftHunkCard'
export { DraftTriageList } from './DraftTriageList/DraftTriageList'
export { DraftTriageRow } from './DraftTriageRow/DraftTriageRow'
export { DraftPreviewPanel } from './DraftPreviewPanel/DraftPreviewPanel'
export { DraftDiffFooter } from './DraftDiffFooter/DraftDiffFooter'
export { DiffCodeBlock } from './DiffCodeBlock/DiffCodeBlock'
export { default as MarkdownRenderer } from './MarkdownRenderer/MarkdownRenderer'

// Reusable atoms
export { StatusBadge } from './StatusBadge/StatusBadge'
export { AcceptToggleChip } from './AcceptToggleChip/AcceptToggleChip'
export { ViewToggle } from './ViewToggle/ViewToggle'
export { CardsIcon, ListIcon, Chevron } from './icons/Icons'

// Hooks
export { useDraftDiff, reconstruct } from './useDraftDiff'
export type { DiffHunk, HunkStatus, UseDraftDiff } from './useDraftDiff'
export { useViewMode } from './useViewMode'
export type { ViewMode } from './useViewMode'

// Diff + label utilities
export { computeWordDiff, computeLineDiff, countWordChanges } from './diffUtils'
export type { DiffLine, WordToken, DiffOpType, WordChangeCount } from './diffUtils'
export { statusBadgeLabel, acceptChipLabel, displayHeading, previewText } from './hunkLabels'
